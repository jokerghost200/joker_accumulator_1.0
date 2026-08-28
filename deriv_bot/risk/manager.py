import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class RiskManager:
    def __init__(
        self,
        sizing_method: str = "fixed", # "fixed" or "percent"
        fixed_stake: float = 10.0,
        risk_percent: float = 0.02,   # 2%
        max_daily_loss: float = 50.0,
        daily_profit_target: float = 100.0,
        max_consecutive_losses: int = 3
    ):
        self.sizing_method = sizing_method
        self.fixed_stake = fixed_stake
        self.risk_percent = risk_percent
        self.max_daily_loss = max_daily_loss
        self.daily_profit_target = daily_profit_target
        self.max_consecutive_losses = max_consecutive_losses
        
        self.reset_daily_stats()
        
        # Tracking averages
        self.total_winning_ticks = 0
        self.winning_trades_count = 0
        
    def reset_daily_stats(self):
        self.daily_profit = 0.0
        self.consecutive_losses = 0
        self.is_trading_blocked = False
        
    def check_trade_allowed(self) -> bool:
        if self.is_trading_blocked:
            return False
            
        if self.daily_profit <= -self.max_daily_loss:
            logger.warning("Max daily loss reached. Trading blocked for today.")
            self.is_trading_blocked = True
            return False
            
        if self.daily_profit >= self.daily_profit_target:
            logger.info("Daily profit target reached. Trading blocked for today.")
            self.is_trading_blocked = True
            return False
            
        if self.consecutive_losses >= self.max_consecutive_losses:
            logger.warning(f"Max consecutive losses ({self.max_consecutive_losses}) reached. Trading blocked.")
            self.is_trading_blocked = True
            return False
            
        return True

    def calculate_stake(self, current_capital: float) -> float:
        if self.sizing_method == "fixed":
            return self.fixed_stake
        elif self.sizing_method == "percent":
            # Ensure we don't bet an absurd amount if capital is huge, or too little if it's small
            calculated = current_capital * self.risk_percent
            return max(0.35, min(calculated, self.fixed_stake * 5)) # Deriv minimum stake is around 0.35 USD
        else:
            return self.fixed_stake
            
    def update_post_trade(self, profit_loss: float, tick_count: int = None):
        self.daily_profit += profit_loss
        if profit_loss < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0
            if tick_count:
                self.total_winning_ticks += tick_count
                self.winning_trades_count += 1
                avg_ticks = self.total_winning_ticks / self.winning_trades_count
                logger.info(f"[STATS] Moyenne de duree d'un trade gagnant : {avg_ticks:.1f} ticks (secondes)")
