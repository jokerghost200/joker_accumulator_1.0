import pandas as pd

class PatternRecognizer:
    @staticmethod
    def get_pattern_hash(row_data: pd.Series) -> str:
        """
        Convertit les données brutes du marché en une signature unique (Hash).
        """
        # 1. RSI
        rsi = row_data.get('tick_rsi_14', 50)
        if rsi < 30:
            rsi_cat = "OVERSOLD"
        elif rsi > 70:
            rsi_cat = "OVERBOUGHT"
        else:
            rsi_cat = "NEUTRAL"

        # 2. Distance aux Bandes de Bollinger (dist_bb_mid est en pourcentage)
        dist_bb = row_data.get('dist_bb_mid', 0)
        if dist_bb < -0.05:
            bb_cat = "LOWER"
        elif dist_bb > 0.05:
            bb_cat = "UPPER"
        else:
            bb_cat = "CENTER"

        # 3. Momentum (Rate of Change 10 ticks)
        roc = row_data.get('roc_10', 0)
        if roc < -0.01:
            mom_cat = "NEG"
        elif roc > 0.01:
            mom_cat = "POS"
        else:
            mom_cat = "FLAT"

        # 4. Volatilité (écart-type des rendements)
        vol = row_data.get('tick_volatility_14', 0.02)
        if vol < 0.015:
            vol_cat = "LOW"
        elif vol > 0.035:
            vol_cat = "HIGH"
        else:
            vol_cat = "MED"
            
        # Création du hash final
        pattern_hash = f"RSI_{rsi_cat}|BB_{bb_cat}|MOM_{mom_cat}|VOL_{vol_cat}"
        return pattern_hash
