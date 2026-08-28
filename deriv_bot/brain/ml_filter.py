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
        features = [
            'ema_9', 'ema_20', 'ema_50', 'tick_rsi_14', 
            'macd', 'macd_signal', 'macd_hist',
            'bb_upper', 'bb_mid', 'bb_lower', 'bb_width',
            'dist_bb_mid', 'dist_bb_upper', 'dist_bb_lower',
            'tick_volatility_14', 'volatility_variation',
            'roc_5', 'roc_10', 'price_change_1',
            'instant_volatility', 'up_freq_10', 'up_freq_20',
            'avg_move_10', 'avg_move_20',
            'target_ticks', 'barrier_threshold'
        ]
        
        available_features = [f for f in features if f in data.columns]
        return data[available_features].fillna(0)

    def predict_survival(self, current_data: pd.DataFrame, target_ticks: int, barrier_threshold: float) -> float:
        """
        Returns the probability of SURVIVAL.
        """
        if not self.is_trained or self.model is None:
            return 0.5
            
        try:
            df = current_data.iloc[[-1]].copy()
            df['target_ticks'] = target_ticks
            df['barrier_threshold'] = barrier_threshold
            
            X = self.prepare_features(df)
            
            probs = self.model.predict_proba(X)[0]
            
            if len(probs) == 2:
                # Find the index for class '1' (Survival)
                if 1 in self.model.classes_:
                    idx = list(self.model.classes_).index(1)
                    return probs[idx]
                else:
                    return 0.0
            else:
                logger.warning(f"Unexpected predict_proba output shape: {probs}")
                return 0.5
                
        except Exception as e:
            logger.error(f"ML prediction error: {e}")
            return 0.5
            
    def train(self, historical_data: pd.DataFrame):
        """
        Trains the model on historical data using dynamic Accumulator scenarios.
        """
        logger.info("Starting ML model training for Accumulator Probability Engine...")
        
        df = historical_data.copy()
        df = df.dropna()
        
        if len(df) < 500:
            logger.warning("Not enough data to train ML model.")
            return
            
        # To simulate multiple scenarios, we will duplicate the dataset and assign random barriers & targets
        scenarios = []
        import random
        
        logger.info("Generating survival scenarios for training...")
        
        # Precompute the absolute pct change for efficiency
        df['abs_pct_change'] = df['close'].pct_change().abs()
        
        # We will create 3 scenarios per historical row
        for i in range(3):
            scenario_df = df.copy()
            
            # Random target ticks between 5 and 50
            scenario_df['target_ticks'] = np.random.randint(5, 50, size=len(scenario_df))
            
            # Random barrier threshold between 0.003% and 0.01%
            scenario_df['barrier_threshold'] = np.random.uniform(0.00003, 0.00010, size=len(scenario_df))
            
            scenarios.append(scenario_df)
            
        training_df = pd.concat(scenarios, ignore_index=True)
        
        # Now, calculate the target: Did it survive?
        # A contract survives if the MAX abs_pct_change in the NEXT 'target_ticks' is < 'barrier_threshold'
        # Because target_ticks varies per row, we can't use a simple rolling.
        # This is slow in pandas, so we'll use numpy arrays for speed
        
        closes = df['close'].values
        abs_pct = df['abs_pct_change'].values
        
        # We need the original index to map back to the timeline
        # Since training_df is concatenated, its index is 0 to 3*len-1
        # The true 'time' index within `abs_pct` is just `i % len(df)`
        n_orig = len(df)
        
        targets = np.zeros(len(training_df))
        
        target_ticks_arr = training_df['target_ticks'].values
        barrier_arr = training_df['barrier_threshold'].values
        
        logger.info(f"Computing survival for {len(training_df)} scenarios...")
        
        for i in range(len(training_df)):
            orig_idx = i % n_orig
            tt = target_ticks_arr[i]
            barrier = barrier_arr[i]
            
            # Check future ticks: from orig_idx + 1 to orig_idx + tt
            end_idx = min(orig_idx + 1 + tt, n_orig)
            
            if end_idx == n_orig:
                # Not enough future data to know if it survived
                targets[i] = np.nan
                continue
                
            future_pct_changes = abs_pct[orig_idx + 1 : end_idx]
            max_change = np.max(future_pct_changes)
            
            if max_change > barrier:
                targets[i] = 0 # Knockout
            else:
                targets[i] = 1 # Survived
                
        training_df['target'] = targets
        training_df = training_df.dropna(subset=['target'])
        
        X = self.prepare_features(training_df)
        y = training_df['target'].astype(int)
        
        logger.info(f"Training Random Forest on {len(X)} samples...")
        self.model = RandomForestClassifier(n_estimators=100, max_depth=8, random_state=42, n_jobs=-1)
        self.model.fit(X, y)
        self.is_trained = True
        
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        joblib.dump(self.model, self.model_path)
        
        # Accuracy metrics
        y_pred = self.model.predict(X)
        accuracy = self.model.score(X, y)
        survival_rate = y.mean()
        
        logger.info(f"--- ML MODEL TRAINING RESULTS ---")
        logger.info(f"Overall Accuracy: {accuracy:.2%}")
        logger.info(f"Dataset Baseline Survival Rate: {survival_rate:.2%}")
        
        from sklearn.metrics import classification_report
        report = classification_report(y, y_pred, target_names=["Knockout", "Survive"])
        logger.info(f"Classification Report:\n{report}")
