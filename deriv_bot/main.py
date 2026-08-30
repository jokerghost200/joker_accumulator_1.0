import asyncio
import os
import logging
import math
from dotenv import load_dotenv

from api.websocket import DerivWebSocket
from api.authentication import DerivAuthenticator
from api.deriv_rest import DerivREST
from api.market_data import MarketDataSubscription
from api.execution import ExecutionEngine
from brain.feature_engine import FeatureEngine
from brain.ml_filter import MLFilter
from brain.auto_learning import AutoLearner

from data.collector import DataEngine
from data.cache import MarketDataCache

from risk.manager import RiskManager
from utils.logger import setup_logger

async def main(ui_queue=None, bot_settings=None):
    # 1. Setup Environment and Logger
    load_dotenv()
    logger = setup_logger()
    logger.info("Starting Deriv Bot on TICKS...")
    app_id = os.getenv("DERIV_APP_ID", "1089")
    api_token = os.getenv("DERIV_PAT")
    account_type = os.getenv("DERIV_ACCOUNT_TYPE", "demo")
    
    if not api_token:
        logger.error("DERIV_PAT not found in .env")
        return
        
    # 2. Initialize Core API components
    ws = DerivWebSocket(app_id=app_id)
    rest_api = DerivREST(app_id=app_id, pat=api_token)
    auth = DerivAuthenticator(ws, rest_api, account_type=account_type)
    market_sub = MarketDataSubscription(ws)
    execution = ExecutionEngine(ws)
    
    # 3. Initialize Data & Brain components
    feature_engine = FeatureEngine()
    ml_filter = MLFilter()
    auto_learner = AutoLearner()
    risk_manager = RiskManager(
        sizing_method="fixed", 
        fixed_stake=5.0, 
        max_daily_loss=200.0,
        daily_profit_target=50.0
    )
    
    # Configuration
    SYMBOL = os.getenv("DERIV_SYMBOL", "R_10")
    GROWTH_RATE = float(os.getenv("DERIV_GROWTH_RATE", "0.05"))
    TAKE_PROFIT_PERCENT = float(os.getenv("TAKE_PROFIT_PERCENT", "25.0"))
        
    is_trading = False
    
    is_retraining = False
    
    async def background_retrain(historical_df):
        nonlocal is_retraining
        if is_retraining:
            logger.info("Un ré-entraînement est déjà en cours, on ignore la requête.")
            return
            
        try:
            is_retraining = True
            logger.info("Extracting live history for background retraining...")
            if historical_df.empty or len(historical_df) < 500:
                logger.warning("Not enough data to retrain on the fly.")
                return
            enriched = feature_engine.enrich_data(historical_df)
            
            def run_training():
                ml_filter.train(enriched)
                
            await asyncio.to_thread(run_training)
            logger.info("Re-entrainement termine avec succes ! Le bot a appris de son erreur.")
        except Exception as e:
            logger.error(f"Erreur lors du ré-entraînement en tâche de fond: {e}")
        finally:
            is_retraining = False
            
    import time
    last_eval_time = 0
    
    latest_bbu = None
    latest_bbl = None
    latest_bbm = None
    
    dynamic_ml_threshold = 0.80
    latest_row_data = None
    
    if bot_settings is None:
        bot_settings = {
            "profit_threshold": 5.0, 
            "cooldown_minutes": 60.0,
            "initial_stake": 5.0,
            "max_loss": 20.0,
            "growth_rate": 0.05
        }
        
    session_profit = 0.0
    is_in_cooldown = False
    emergency_stop = False
    current_balance = 0.0
    consecutive_losses = 0
    
    # 4. Define the Trading Loop Callback for Ticks
    async def process_new_tick(df):
        nonlocal is_trading, last_eval_time, latest_bbu, latest_bbl, latest_bbm, dynamic_ml_threshold, latest_row_data, is_in_cooldown, session_profit, emergency_stop, current_balance, consecutive_losses
        
        if is_trading or is_in_cooldown or emergency_stop:
            return
            
        # Limit evaluations slightly to avoid overloading the CPU, e.g. every 2 seconds max
        current_time = time.time()
        if current_time - last_eval_time < 2:
            return
        last_eval_time = current_time
            
        if not risk_manager.check_trade_allowed():
            return
            
        if len(df) < 50:
            return
            
        # 4a. Features calculation on TICKS
        enriched = feature_engine.enrich_data(df)
        
        latest_row = enriched.iloc[-1]
        latest_row_data = latest_row
        close_price = float(latest_row['close'])
        
        # --- AUTO-LEARNING: Update Virtual Trades ---
        new_outcomes = auto_learner.update_with_tick(close_price)
        if auto_learner.collected_outcomes >= 100:
            logger.info(f"Auto-Learning: 100 nouvelles expériences collectées. Déclenchement du ré-entraînement...")
            asyncio.create_task(background_retrain(df.copy()))
            auto_learner.reset_counter()
        # --------------------------------------------
        latest_bbm = float(latest_row['bb_mid'])
        latest_bbu = float(latest_row['bb_upper'])
        latest_bbl = float(latest_row['bb_lower'])
        dist_bb_mid = abs(float(latest_row['dist_bb_mid'])) # % distance to middle
        tick_momentum = abs(float(latest_row['roc_10']))
        tick_volatility = float(latest_row['tick_volatility_14'])
        
        # 4b. Strategy Engine (Entry Logic - PURE AI)
        stake = float(bot_settings.get("initial_stake", 5.0))
        
        growth_rate_setting = bot_settings.get('growth_rate_str', 'Auto')
        if growth_rate_setting == 'Auto':
            growth_rates_to_test = [0.01, 0.02, 0.03, 0.04, 0.05]
        else:
            growth_rates_to_test = [float(growth_rate_setting.replace('%','')) / 100.0]
            
        # LOCAL AI PRE-FILTERING (No API calls yet!)
        best_local_rate = None
        best_local_prob = 0.0
        
        for rate in growth_rates_to_test:
            # Approximate the barrier like in backtest to save API limits
            # based on API responses: 1% -> 0.0000613, 5% -> 0.0000486
            # We make it slightly tighter (subtract 0.0000010) to avoid false positives locally
            approx_barrier = 0.0000645 - (0.0003175 * rate) - 0.0000010
            target_ticks = math.ceil(math.log(1 + (TAKE_PROFIT_PERCENT / 100.0)) / math.log(1 + rate))
            
            # Predict using XGBoost
            prob = ml_filter.predict_survival(enriched, target_ticks, approx_barrier)
            if prob > best_local_prob:
                best_local_prob = prob
                best_local_rate = rate
                
        signal_detected = False
        
        # Apply Dynamic Prudence Mode
        # RULE: Never go below 80% AI confidence minimum (Quality over Quantity)
        dynamic_ml_threshold = max(0.80, dynamic_ml_threshold)
        current_threshold = dynamic_ml_threshold
        if session_profit > 0:
            prudence_bonus = session_profit * 0.015 # +1.5% for every $1 profit
            current_threshold = min(0.95, dynamic_ml_threshold + prudence_bonus)
            
        if best_local_prob > current_threshold:
            signal_detected = True
        
        # 4. Fetch Proposals and AI Filter Confirmation
        if signal_detected:
            # --- VERROU (LOCK) ---
            # On bloque immédiatement les autres ticks pour éviter OpenPositionLimitExceeded
            is_trading = True 
            
            # We want to check all rates if Auto, or just one if specific
            growth_rate_setting = bot_settings.get('growth_rate_str', 'Auto')
            if growth_rate_setting == 'Auto':
                growth_rates_to_test = [0.01, 0.02, 0.03, 0.04, 0.05]
            else:
                growth_rates_to_test = [float(growth_rate_setting.replace('%','')) / 100.0]
            
            logger.info("Signal detecté! Récupération des propositions pour analyser la probabilité de survie...")
            
            best_rate = None
            best_prob = 0.0
            best_contract_id = None
            best_ask_price = None
            best_tp_amount = None
            best_stake = None
            
            # Fetch balance if missing
            if current_balance == 0.0 and auth.account_info:
                current_balance = float(auth.account_info.get('balance', 0.0))
                
            base_stake = float(bot_settings.get("initial_stake", 5.0))
                
            # Request all proposals in parallel with dynamic TP based on UI stake
            tasks = []
            for rate in growth_rates_to_test:
                if rate >= 0.04:
                    # Very risky: We reduce the user's stake by half to be safe, min $1
                    rate_stake = max(1.0, base_stake * 0.5)
                    rate_tp_percent = 10.0
                else:
                    # Normal: We use the user's full stake
                    rate_stake = base_stake
                    rate_tp_percent = 15.0
                    
                rate_tp_amount = rate_stake * (rate_tp_percent / 100.0)
                
                tasks.append(execution.get_proposal(
                    symbol=SYMBOL, 
                    contract_type="ACCU", 
                    stake=round(rate_stake, 2), 
                    growth_rate=rate,
                    limit_order={"take_profit": round(rate_tp_amount, 2)}
                ))
            
            proposals = await asyncio.gather(*tasks)
            
            log_msg = f"""
[TICK]
Prix: {close_price:.4f}
BB Middle: {latest_bbm:.4f}
Distance BB Middle: {dist_bb_mid:.4f}%
BB Width: {float(latest_row['bb_width']):.4f}
Momentum: {tick_momentum:.4f}
RSI: {float(latest_row.get('tick_rsi_14', 0)):.2f}
Volatilité: {tick_volatility:.4f}
État du Squeeze: Pure AI Mode

[STRATEGY]
Signal détecté : OUI

[AI ACCUMULATOR PROBABILITIES]
"""
            
            # Now we use the new ML engine for predictions
            for rate, prop_resp in zip(growth_rates_to_test, proposals):
                if 'error' in prop_resp:
                    log_msg += f"Growth {int(rate*100)}%: ERREUR ({prop_resp['error'].get('message')})\n"
                    continue
                
                prop = prop_resp.get('proposal', {})
                contract_id = prop.get('id')
                ask_price = prop.get('ask_price')
                
                # Extract barrier
                contract_details = prop.get('contract_details', {})
                barrier_str = contract_details.get('tick_size_barrier_percentage', '0')
                barrier_percentage = float(barrier_str.replace('%', '')) / 100.0 if isinstance(barrier_str, str) else float(barrier_str)
                
                if barrier_percentage == 0:
                    log_msg += f"Growth {int(rate*100)}%: ERREUR (Barrière manquante)\n"
                    continue
                
                # Calculate dynamic TP and Stake again for this rate
                if rate >= 0.04:
                    rate_stake = max(1.0, base_stake * 0.5)
                    rate_tp_percent = 10.0
                else:
                    rate_stake = base_stake
                    rate_tp_percent = 15.0
                rate_tp_amount = rate_stake * (rate_tp_percent / 100.0)

                # Calculate target ticks based on the target profit formula
                target_ticks = math.ceil(math.log(1 + (rate_tp_percent / 100.0)) / math.log(1 + rate))
                
                # Request survival probability from ML engine
                prob_survive = ml_filter.predict_survival(enriched, target_ticks, barrier_percentage)
                
                # Auto-Learning: Start tracking this simulated position
                auto_learner.start_tracking(
                    features=latest_row.to_dict(),
                    start_price=close_price,
                    target_ticks=target_ticks,
                    barrier_pct=barrier_percentage,
                    rate=rate
                )
                
                status_str = "(BUY)" if prob_survive > current_threshold else "(WARN)"
                log_msg += f"Growth {int(rate*100)}% -> {prob_survive:.2%} {status_str} [Ticks:{target_ticks}, Barrière:{barrier_percentage}%]\n"
                
                # Update best rate logic
                if prob_survive > best_prob:
                    best_prob = prob_survive
                    
                    if prob_survive > current_threshold:
                        best_rate = rate
                        best_contract_id = contract_id
                        best_ask_price = ask_price
                        best_tp_amount = rate_tp_amount
                        best_stake = rate_stake
            
            log_msg += "\n[DECISION]\n"
            
            final_prob = best_prob if best_prob > 0 else best_local_prob
            # Envoyer les metrics à l'interface
            if ui_queue:
                ui_queue.put({
                    "type": "metrics",
                    "price": close_price,
                    "bb_mid": latest_bbm,
                    "dist": dist_bb_mid,
                    "volatility": tick_volatility,
                    "momentum": tick_momentum,
                    "rsi": float(latest_row.get('tick_rsi_14', 0)),
                    "squeeze": "Pure AI Mode",
                    "signal": signal_detected,
                    "prob_safe": final_prob,
                    "prob_danger": 1.0 - final_prob
                })
                
            result = None
            if best_contract_id:
                log_msg += f"Le bot choisit: {int(best_rate*100)}% offre le meilleur compromis avec une survie estimée de {best_prob:.2%}.\n"
                logger.info(log_msg)
                logger.info(f"*** EXECUTING ACCUMULATOR TRADE on {SYMBOL} for {best_stake:.2f} USD (TP: {best_tp_amount:.2f}$) ***")
                result = await execution.buy_contract(best_contract_id, best_ask_price)
                if not result:
                    # En cas d'erreur API lors de l'achat, on relâche le verrou
                    is_trading = False
            else:
                log_msg += "HOLD (Aucun taux ne dépasse le seuil de sécurité de l'IA)\n"
                logger.info(log_msg)
                is_trading = False
                return
        else:
            # Send metrics to UI even if no signal
            if ui_queue:
                ui_queue.put({
                    "type": "metrics",
                    "price": close_price,
                    "bb_mid": latest_bbm,
                    "dist": dist_bb_mid,
                    "volatility": tick_volatility,
                    "momentum": tick_momentum,
                    "rsi": float(latest_row.get('tick_rsi_14', 0)),
                    "squeeze": "Pure AI Mode",
                    "signal": False,
                    "prob_safe": best_local_prob,
                    "prob_danger": 1.0 - best_local_prob
                })
            return # Wait for AI confidence
                
        if result:
            contract_id = result.get('contract_id')
            if result.get('balance_after'):
                current_balance = float(result.get('balance_after'))
                
            logger.info(f"Trade successfully placed. Bot will now wait for settlement. Contract ID: {contract_id}")
            is_trading = True
            contract_settled = False
            sell_requested = False
            
            def on_contract_update(poc):
                nonlocal is_trading, contract_settled, dynamic_ml_threshold, session_profit, is_in_cooldown, emergency_stop
                nonlocal current_balance, consecutive_losses, sell_requested
                
                is_sold = poc.get('is_sold')
                is_expired = poc.get('is_expired')
                status = poc.get('status')
                profit = poc.get('profit')
                # Accumulators return max ticks in 'tick_count'. Actual ticks are in 'tick_passed'
                actual_ticks = poc.get('tick_passed', poc.get('tick_count', 0))
                current_spot = poc.get('current_spot')
                
                # Smart Exit Logic
                if not is_sold and not is_expired and status == 'open' and not sell_requested:
                    profit_val = float(profit) if profit else 0.0
                    profit_pct = profit_val / best_stake if best_stake > 0 else 0
                    
                    if best_rate >= 0.04 and profit_pct >= 0.03 and actual_ticks >= 4:
                        logger.info(f"Smart Exit [FAST RATE]: Profit {profit_pct:.2%} >= 3% after {actual_ticks} ticks. Selling!")
                        sell_requested = True
                        asyncio.create_task(execution.sell_contract(contract_id=poc.get('contract_id')))
                    elif best_rate < 0.04 and profit_pct >= 0.05 and actual_ticks >= 6:
                        logger.info(f"Smart Exit [SLOW RATE]: Profit {profit_pct:.2%} >= 5% after {actual_ticks} ticks. Selling!")
                        sell_requested = True
                        asyncio.create_task(execution.sell_contract(contract_id=poc.get('contract_id')))
                        
                if is_sold or is_expired or status in ['won', 'lost']:
                    if contract_settled:
                        return
                    contract_settled = True
                    
                    if poc.get('balance_after'):
                        current_balance = float(poc.get('balance_after'))
                        
                    # API sometimes sends intermediate 'open' status even when sold
                    if status == 'open':
                        status = 'won' if float(profit) > 0 else 'lost'
                        
                    if status == 'won':
                        logger.info(f"[RESULT]\nTP (Contract Settled WON, Profit: {profit}, Ticks: {actual_ticks})")
                    else:
                        logger.info(f"[RESULT]\n{status.upper()} (Profit: {profit}, Ticks: {actual_ticks})")
                    
                    if status == 'lost':
                        consecutive_losses += 1
                        # Diagnostics
                        if latest_row_data is not None:
                            dist_bb = latest_row_data.get('dist_bb_mid', 0)
                            t_mom = latest_row_data.get('roc_10', 0)
                            t_vol = latest_row_data.get('tick_volatility_14', 0)
                            logger.info(f"[LOSS DIAGNOSTICS] Dist_BB={dist_bb:.4f}%, Tick_Mom={t_mom:.4f}, Tick_Vol={t_vol:.4f}")
                        
                        # Dynamic ML Threshold Update (Stricter)
                        dynamic_ml_threshold = min(0.90, dynamic_ml_threshold + 0.02)
                        logger.warning(f"[BOT LOST] Becoming more strict! New Danger Threshold: {dynamic_ml_threshold:.2%} (Losses: {consecutive_losses}/3)")
                        
                        logger.info("Déclenchement du ré-entraînement de l'IA en tâche de fond...")
                        asyncio.create_task(background_retrain(df.copy()))
                        
                        if consecutive_losses >= 3:
                            logger.error(f"3 PERTES CONSÉCUTIVES. PAUSE D'UNE HEURE POUR ANALYSER LE MARCHÉ.")
                            if ui_queue:
                                ui_queue.put({"type": "status_update", "status": "3 LOSSES (1H COOLDOWN)"})
                            is_in_cooldown = True
                            
                            async def wait_long_cooldown():
                                nonlocal is_in_cooldown, consecutive_losses
                                await asyncio.sleep(3600)
                                consecutive_losses = 0
                                is_in_cooldown = False
                                logger.info("Fin de la pause de 1 heure suite aux pertes. Reprise !")
                                if ui_queue:
                                    ui_queue.put({"type": "status_update", "status": "RUNNING"})
                                    
                            asyncio.create_task(wait_long_cooldown())
                    
                    elif status == 'won':
                        consecutive_losses = 0
                        # Regain confidence (Relax threshold slightly)
                        dynamic_ml_threshold = max(0.80, dynamic_ml_threshold - 0.01)
                        logger.info(f"[BOT WON] Regaining confidence. New Danger Threshold: {dynamic_ml_threshold:.2%}")
                    
                    try:
                        risk_manager.update_post_trade(float(profit), actual_ticks)
                        session_profit += float(profit)
                        
                        if ui_queue:
                            ui_queue.put({"type": "profit_update", "profit": session_profit})
                            ui_queue.put({"type": "trade_result", "status": status})
                            
                        # Max Loss check
                        max_loss = float(bot_settings.get("max_loss", 20.0))
                        if session_profit <= -max_loss:
                            logger.error(f"PERTE MAXIMALE ATTEINTE (${session_profit:.2f} <= -${max_loss:.2f}). ARRET D'URGENCE DU TRADING.")
                            if ui_queue:
                                ui_queue.put({"type": "status_update", "status": "MAX LOSS REACHED"})
                            is_trading = False
                            emergency_stop = True
                            return
                            
                        # Cooldown check
                        target = float(bot_settings.get("profit_threshold", 5.0))
                        if session_profit >= target:
                            cooldown_mins = float(bot_settings.get("cooldown_minutes", 60.0))
                            logger.warning(f"Objectif de profit atteint (${session_profit:.2f} >= ${target:.2f}). Pause (Cooldown) pendant {cooldown_mins} minutes.")
                            if ui_queue:
                                ui_queue.put({"type": "status_update", "status": f"COOLDOWN ({cooldown_mins}m)"})
                            
                            is_in_cooldown = True
                            
                            async def wait_cooldown():
                                nonlocal session_profit, is_in_cooldown
                                await asyncio.sleep(cooldown_mins * 60)
                                session_profit = 0.0
                                is_in_cooldown = False
                                logger.info("Cooldown termine ! Reprise du trading. Profit de session reinitialise a 0.")
                                if ui_queue:
                                    ui_queue.put({"type": "profit_update", "profit": session_profit})
                                    ui_queue.put({"type": "status_update", "status": "RUNNING"})

                            asyncio.create_task(wait_cooldown())
                            
                    except (ValueError, TypeError):
                        pass
                    is_trading = False
                    
            await execution.subscribe_to_open_contract(contract_id, on_contract_update)
                
    def on_new_tick(df):
        asyncio.create_task(process_new_tick(df))
        
    # 5. Connect and Run
    data_engine = DataEngine(market_sub, max_cache_size=5000)
    data_engine.add_tick_callback(on_new_tick)
    
    # Auto-reconnect loop
    while True:
        try:
            logger.info("Attempting connection...")
            if await auth.authenticate():
                await ws.connect()
                
                # Cleanup leftover open positions
                logger.info("Checking for leftover open positions...")
                portfolio_resp = await ws.send_request({"portfolio": 1})
                if 'portfolio' in portfolio_resp:
                    contracts = portfolio_resp['portfolio'].get('contracts', [])
                    if contracts:
                        logger.warning(f"Found {len(contracts)} open position(s) from previous sessions. Closing them now...")
                        for contract in contracts:
                            cid = contract.get('contract_id')
                            if cid:
                                await execution.sell_contract(contract_id=cid)
                                await asyncio.sleep(0.5)
                        logger.info("All leftover positions closed.")
                
                is_trading = False
                
                # Subscribe to ticks and fetch initial history (5000 ticks)
                await market_sub.subscribe_ticks_history(symbol=SYMBOL, count=5000)
                
                while ws.connected:
                    await asyncio.sleep(1)
                    
                logger.warning("WebSocket disconnected. Reconnecting in 5 seconds...")
            else:
                logger.error("Authentication failed. Retrying in 10 seconds...")
                await asyncio.sleep(10)
                continue
                
        except asyncio.CancelledError:
            logger.info("Bot shutting down...")
            break
        except Exception as e:
            logger.error(f"Unexpected error: {e}. Reconnecting in 5 seconds...")
            
        await ws.disconnect()
        await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
