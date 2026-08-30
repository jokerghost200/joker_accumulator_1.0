import pandas as pd
from brain.ml_filter import MLFilter

ml = MLFilter()

# Let's load the model
# We know the model has 26 features. Let's just create a dummy with all 26.
features = ['ema_9', 'ema_20', 'ema_50', 'tick_rsi_14', 'macd', 'macd_signal', 'macd_hist', 'bb_upper', 'bb_mid', 'bb_lower', 'bb_width', 'dist_bb_mid', 'dist_bb_upper', 'dist_bb_lower', 'tick_volatility_14', 'volatility_variation', 'roc_5', 'roc_10', 'price_change_1', 'instant_volatility', 'up_freq_10', 'up_freq_20', 'avg_move_10', 'avg_move_20', 'target_ticks', 'barrier_threshold']
row = {f: 0.01 for f in features}

df = pd.DataFrame([row])

print("Local Call:")
approx_barrier = 0.0000645 - (0.0003175 * 0.04)
prob1 = ml.predict_survival(df, 6, approx_barrier)
print(prob1)

print("Real Call:")
prob2 = ml.predict_survival(df, 6, 0.0000511)
print(prob2)
