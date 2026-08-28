import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
import joblib
import os
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

class MLFilter:
    def __init__(self, model_path: str = "models/rf_model.joblib"):
        self.model_path = model_path
        self.model = None
        self.is_trained = False
        self._load_model()
        
    def _load_model(self):
        if os.path.exists(self.model_path):
            try:
                self.model = joblib.load(self.model_path)
                self.is_trained = True
                logger.info(f"Loaded ML model from {self.model_path}")
            except Exception as e:
                logger.error(f"Failed to load ML model: {e}")
        else:
            logger.info("No trained ML model found. ML Filter will return neutral probabilities.")
            
    def prepare_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Extracts relevant features for the ML model from the enriched DataFrame.
        """
        # Select the columns that the model will use for prediction
        # (Must match the columns used during training)
        features = [
            'ema_9', 'ema_20', 'ema_50', 'tick_rsi_14', 
            'macd', 'macd_signal', 'macd_hist',
            'bb_upper', 'bb_mid', 'bb_lower', 'bb_width',
            'dist_bb_mid', 'dist_bb_upper', 'dist_bb_lower',
            'tick_volatility_14', 'volatility_variation',
            'roc_5', 'roc_10', 'price_change_1'
        ]
        
        # Only return existing features and drop NaNs
        available_features = [f for f in features if f in data.columns]
        return data[available_features].fillna(0) # In production, handle NaNs properly

    def predict_probability(self, current_data: pd.DataFrame) -> Tuple[float, float]:
        """
        Returns the probability of (SAFE, DANGER).
        If model is not trained, returns (0.5, 0.5) to neutralize the filter.
        """
        if not self.is_trained or self.model is None:
            return 0.5, 0.5
            
        try:
            X = self.prepare_features(current_data.iloc[[-1]])
            
            # predict_proba returns [[prob_0, prob_1]]
            # 0 is SAFE, 1 is DANGER
            probs = self.model.predict_proba(X)[0]
            
            if len(probs) == 2:
                prob_safe, prob_danger = probs[0], probs[1]
                return prob_safe, prob_danger
            else:
                logger.warning(f"Unexpected predict_proba output shape: {probs}")
                return 0.5, 0.5
                
        except Exception as e:
            logger.error(f"ML prediction error: {e}")
            return 0.5, 0.5
            
    def train(self, historical_data: pd.DataFrame, target_duration: int = 10):
        """
        Trains the model on historical data.
        Target is 1 (DANGER) if the price touches the CURRENT Bollinger bands 
        within the next `target_duration` ticks.
        Target is 0 (SAFE) otherwise.
        """
        logger.info("Starting ML model training for Accumulator on Ticks...")
        
        # Create target variable
        df = historical_data.copy()
        
        # Calculate future max and min close over the next N ticks
        # rolling(window) looks backward, so we shift it backwards by target_duration
        df['future_max_close'] = df['close'].rolling(window=target_duration, min_periods=1).max().shift(-target_duration)
        df['future_min_close'] = df['close'].rolling(window=target_duration, min_periods=1).min().shift(-target_duration)
        
        # 1 = DANGER (Touches or breaks current Bollinger Bands within N ticks), 0 = SAFE
        # To be safe, we add a slight margin of 85% to be realistic about "reaching" the bands
        # (bb_upper - bb_mid) * 0.85
        margin_upper = df['bb_mid'] + (df['bb_upper'] - df['bb_mid']) * 0.85
        margin_lower = df['bb_mid'] - (df['bb_mid'] - df['bb_lower']) * 0.85
        
        danger_condition = (df['future_max_close'] >= margin_upper) | (df['future_min_close'] <= margin_lower)
        df['target'] = danger_condition.astype(int)
        
        # Drop rows where we don't have future data or have NaNs in indicators
        df = df.dropna()
        
        X = self.prepare_features(df)
        y = df['target']
        
        if len(X) < 100:
            logger.warning("Not enough data to train ML model.")
            return
            
        # Train a simple Random Forest
        self.model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
        self.model.fit(X, y)
        self.is_trained = True
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        joblib.dump(self.model, self.model_path)
        
        # Basic accuracy log
        y_pred = self.model.predict(X)
        
        # Calculate metrics
        from sklearn.metrics import confusion_matrix
        
        cm = confusion_matrix(y, y_pred)
        if cm.shape == (2, 2):
            tn, fp, fn, tp = cm.ravel()
            
            total_samples = len(y)
            # Signal means the model predicted SAFE (0)
            total_signals = tn + fn # Actual safe predicted safe (TN) + Actual danger predicted safe (FN)
            signal_rate = total_signals / total_samples
            
            # False Positive in trading terms: Predicted SAFE (0) but actually DANGER (1) -> this is FN in sklearn terms since target 1 is Positive
            # Let's define them explicitly based on trading logic:
            # Positive for model is DANGER (1).
            # Model predicts 0 (SAFE) -> Bot enters trade.
            # If Actual is 1 (DANGER), and Model predicted 0 (SAFE) -> False Safe (Trading False Positive)
            false_safe = fn
            false_safe_rate = false_safe / total_signals if total_signals > 0 else 0
            
            # Model predicts 1 (DANGER) -> Bot skips trade.
            # If Actual is 0 (SAFE), and Model predicted 1 (DANGER) -> Missed Opportunity
            missed_opp = fp
            missed_opp_rate = missed_opp / (tn + fp) if (tn + fp) > 0 else 0
            
            logger.info("--- TRADING METRICS ---")
            logger.info(f"Signal Rate (Trades taken): {signal_rate:.2%} ({total_signals}/{total_samples})")
            logger.info(f"False Positives (Dangerous trades taken): {false_safe_rate:.2%} ({false_safe}/{total_signals})")
            logger.info(f"Missed Opportunities (Safe trades skipped): {missed_opp_rate:.2%} ({missed_opp}/{(tn + fp)})")
        else:
            accuracy = self.model.score(X, y)
            logger.info(f"ML Model trained successfully. In-sample accuracy: {accuracy:.2%}")
