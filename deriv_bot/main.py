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
    cache = MarketDataCache(max_size=5000)
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
    
    import time
    last_eval_time = 0
    
    latest_bbu = None
    latest_bbl = None
    latest_bbm = None
    
    dynamic_ml_threshold = 0.50
    latest_row_data = None
    
    if bot_settings is None:
        bot_settings = {
            "profit_threshold": 5.0, 
            "cooldown_minutes": 60.0,
            "initial_stake": 5.0,
            "growth_rate": 0.05
        }
        
    session_profit = 0.0
    is_in_cooldown = False
    
    # 4. Define the Trading Loop Callback for Ticks
    async def process_new_tick(df):
        nonlocal is_trading, last_eval_time, latest_bbu, latest_bbl, latest_bbm, dynamic_ml_threshold, latest_row_data, is_in_cooldown, session_profit
        
        if is_trading or is_in_cooldown:
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
            ml_filter.retrain_live(auto_learner.csv_path)
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
            approx_barrier = 0.0005 - (rate * 0.001)
            target_ticks = math.ceil(math.log(1 + (TAKE_PROFIT_PERCENT / 100.0)) / math.log(1 + rate))
            
            # Predict using XGBoost
            prob = ml_filter.predict_survival(enriched, target_ticks, approx_barrier)
            if prob > best_local_prob:
                best_local_prob = prob
                best_local_rate = rate
                
        signal_detected = False
        if best_local_prob > dynamic_ml_threshold:
            signal_detected = True
        
        # 4. Fetch Proposals and AI Filter Confirmation
        if signal_detected:
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
            
            # Request all proposals in parallel
            tp_amount = stake * (TAKE_PROFIT_PERCENT / 100.0)
            
            tasks = []
            for rate in growth_rates_to_test:
                tasks.append(execution.get_proposal(
                    symbol=SYMBOL, 
                    contract_type="ACCU", 
                    stake=stake, 
                    growth_rate=rate,
                    limit_order={"take_profit": tp_amount}
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
                
                # Calculate target ticks based on the target profit formula
                target_ticks = math.ceil(math.log(1 + (TAKE_PROFIT_PERCENT / 100.0)) / math.log(1 + rate))
                
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
                
                decision = "BUY" if prob_survive > dynamic_ml_threshold else "WARN"
                log_msg += f"Growth {int(rate*100)}% -> {prob_survive:.2%} ({decision}) [Ticks:{target_ticks}, Barrière:{barrier_percentage}%]\n"
                
                # Update best rate logic
                if prob_survive > dynamic_ml_threshold and prob_survive > best_prob:
                    best_prob = prob_survive
                    best_rate = rate
                    best_contract_id = contract_id
                    best_ask_price = ask_price
                    best_tp_amount = tp_amount
            
            log_msg += "\n[DECISION]\n"
            
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
                    "prob_safe": best_local_prob,
                    "prob_danger": 1.0 - best_local_prob
                })

            if best_contract_id:
                log_msg += f"Le bot choisit: {int(best_rate*100)}% offre le meilleur compromis avec une survie estimée de {best_prob:.2%}.\n"
                logger.info(log_msg)
                logger.info(f"*** EXECUTING ACCUMULATOR TRADE on {SYMBOL} for {stake} USD (TP: {best_tp_amount}$) ***")
                result = await execution.buy_contract(best_contract_id, best_ask_price)
            else:
                log_msg += "HOLD (Aucun taux ne dépasse le seuil de sécurité de l'IA)\n"
                logger.info(log_msg)
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
            logger.info(f"Trade successfully placed. Bot will now wait for settlement. Contract ID: {contract_id}")
            is_trading = True
            contract_settled = False
            
            def on_contract_update(poc):
                nonlocal is_trading
                nonlocal dynamic_ml_threshold
                nonlocal contract_settled
                nonlocal session_profit
                nonlocal is_in_cooldown
                
                is_sold = poc.get('is_sold')
                is_expired = poc.get('is_expired')
                status = poc.get('status')
                profit = poc.get('profit')
                # Accumulators return max ticks in 'tick_count'. Actual ticks are in 'tick_passed'
                actual_ticks = poc.get('tick_passed', poc.get('tick_count', 0))
                current_spot = poc.get('current_spot')
                
                # Exit Logic: Let it ride to TP or crash (Pure AI Mode)
                # (Accumulators cannot be sold unless sell_price > stake anyway)
                
                if is_sold or is_expired or status in ['won', 'lost']:
                    if contract_settled:
                        return
                    contract_settled = True
                    
                    # API sometimes sends intermediate 'open' status even when sold
                    if status == 'open':
                        status = 'won' if float(profit) > 0 else 'lost'
                        
                    if status == 'won':
                        logger.info(f"[RESULT]\nTP (Contract Settled WON, Profit: {profit}, Ticks: {actual_ticks})")
                    else:
                        logger.info(f"[RESULT]\n{status.upper()} (Profit: {profit}, Ticks: {actual_ticks})")
                    
                    if status == 'lost':
                        # Diagnostics
                        if latest_row_data is not None:
                            dist_bb = latest_row_data.get('dist_bb_mid', 0)
                            t_mom = latest_row_data.get('roc_10', 0)
                            t_vol = latest_row_data.get('tick_volatility_14', 0)
                            logger.info(f"[LOSS DIAGNOSTICS] Dist_BB={dist_bb:.4f}%, Tick_Mom={t_mom:.4f}, Tick_Vol={t_vol:.4f}")
                        
                        # Dynamic ML Threshold Update (Stricter)
                        dynamic_ml_threshold = max(0.35, dynamic_ml_threshold - 0.05)
                        logger.warning(f"[BOT LOST] Becoming more strict! New Danger Threshold: {dynamic_ml_threshold:.2%}")
                    
                    elif status == 'won':
                        # Regain confidence (Relax threshold slightly)
                        dynamic_ml_threshold = min(0.55, dynamic_ml_threshold + 0.01)
                        logger.info(f"[BOT WON] Regaining confidence. New Danger Threshold: {dynamic_ml_threshold:.2%}")
                    
                    try:
                        risk_manager.update_post_trade(float(profit), actual_ticks)
                        session_profit += float(profit)
                        
                        if ui_queue:
                            ui_queue.put({"type": "profit_update", "profit": session_profit})
                            
                        # Cooldown check
                        target = float(bot_settings.get("profit_threshold", 5.0))
                        if session_profit >= target:
                            cooldown_mins = float(bot_settings.get("cooldown_minutes", 60.0))
                            logger.warning(f"🎯 Objectif de profit atteint (${session_profit:.2f} >= ${target:.2f}). Pause (Cooldown) pendant {cooldown_mins} minutes.")
                            if ui_queue:
                                ui_queue.put({"type": "status_update", "status": f"COOLDOWN ({cooldown_mins}m)"})
                            
                            is_in_cooldown = True
                            
                            async def wait_cooldown():
                                nonlocal session_profit, is_in_cooldown
                                await asyncio.sleep(cooldown_mins * 60)
                                session_profit = 0.0
                                is_in_cooldown = False
                                logger.info("✅ Cooldown terminé ! Reprise du trading. Profit de session réinitialisé à 0.")
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
