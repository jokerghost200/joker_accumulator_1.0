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
        latest_bbm = float(latest_row['bb_mid'])
        latest_bbu = float(latest_row['bb_upper'])
        latest_bbl = float(latest_row['bb_lower'])
        dist_bb_mid = abs(float(latest_row['dist_bb_mid'])) # % distance to middle
        tick_momentum = abs(float(latest_row['roc_10']))
        tick_volatility = float(latest_row['tick_volatility_14'])
        
        # 4b. Strategy Engine (Entry Logic)
        stake = float(bot_settings.get("initial_stake", 5.0))
        current_growth_rate = float(bot_settings.get("growth_rate", 0.05))
        
        # STRATEGY CONDITIONS:
        absolute_bb_width = latest_bbu - latest_bbl
        
        # 1. Proximity to BB Middle: Must be within 20% of the BB Width from the middle
        abs_dist_to_mid = abs(close_price - latest_bbm)
        is_near_mid = abs_dist_to_mid < (absolute_bb_width * 0.20)
        
        # 2. Acceptable Momentum: Not a massive spike in the last 10 ticks
        is_favorable_momentum = tick_momentum < 0.01
        
        # 3. Acceptable Volatility: Standard deviation of returns shouldn't be too wild
        is_favorable_volatility = tick_volatility < 0.003
        
        # 4. Anti-Immediate Danger: Ensure price is not in the outer 15% bands
        dist_to_upper = latest_bbu - close_price
        dist_to_lower = close_price - latest_bbl
        danger_threshold = absolute_bb_width * 0.15
        is_not_in_danger = (dist_to_upper > danger_threshold) and (dist_to_lower > danger_threshold)
        
        signal_detected = is_near_mid and is_favorable_momentum and is_favorable_volatility and is_not_in_danger
        
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
            
            import asyncio
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
État du Squeeze: {"Près du centre" if is_near_mid else "Loin du centre"}

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
                limit_order = prop.get('limit_order', {})
                barrier_percentage = float(limit_order.get('tick_size_barrier_percentage', 0))
                
                if barrier_percentage == 0:
                    log_msg += f"Growth {int(rate*100)}%: ERREUR (Barrière manquante)\n"
                    continue
                
                # Calculate target ticks based on the target profit formula
                import math
                target_ticks = math.ceil(math.log(1 + (TAKE_PROFIT_PERCENT / 100.0)) / math.log(1 + rate))
                
                # Request survival probability from ML engine
                prob_survive = ml_filter.predict_survival(enriched, target_ticks, barrier_percentage)
                
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
                    "squeeze": "Près du centre" if is_near_mid else "Loin du centre",
                    "signal": signal_detected,
                    "prob_safe": best_prob,
                    "prob_danger": 1.0 - best_prob
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
            # Not a signal, just log HOLD occasionally or quietly skip
            return # Wait for the perfect entry conditions
                
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
                tick_count = poc.get('tick_count')
                current_spot = poc.get('current_spot')
                
                # Exit Logic: Danger of Knockout (Close to BB)
                if not is_sold and not is_expired and current_spot is not None and latest_bbu and latest_bbl:
                    try:
                        current_spot_float = float(current_spot)
                        
                        dist_to_upper = latest_bbu - current_spot_float
                        dist_to_lower = current_spot_float - latest_bbl
                        band_width = latest_bbu - latest_bbl
                        
                        # If price is within 15% of either band, SELL immediately
                        threshold_dist = band_width * 0.15
                        
                        if dist_to_upper < threshold_dist or dist_to_lower < threshold_dist:
                            logger.warning(f"[RESULT]\nDANGER (Price {current_spot_float} is too close to bands). Closing manually.")
                            asyncio.create_task(execution.sell_contract(contract_id))
                            return
                    except (ValueError, TypeError):
                        pass
                
                if is_sold or is_expired or status in ['won', 'lost']:
                    if contract_settled:
                        return
                    contract_settled = True
                    
                    if status == 'won':
                        logger.info(f"[RESULT]\nTP (Contract Settled WON, Profit: {profit}, Ticks: {tick_count})")
                    else:
                        logger.info(f"[RESULT]\n{status.upper()} (Profit: {profit}, Ticks: {tick_count})")
                    
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
                        risk_manager.update_post_trade(float(profit), tick_count)
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
