import customtkinter as ctk
import threading
import asyncio
import os
import subprocess
import pandas as pd
import logging
from typing import Dict, Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

from brain.backtest_engine import Backtester
from brain.ml_filter import MLFilter

# Configuration de base CustomTkinter
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class LaboratoryGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Deriv AI - Laboratoire & Tests")
        self.geometry("800x600")
        
        # Load ML Model for simulator
        model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "rf_model.joblib")
        try:
            self.ml_filter = MLFilter(model_path=model_path)
            self.model_loaded = True
        except Exception as e:
            self.ml_filter = None
            self.model_loaded = False
            
        self.backtester = Backtester()

        # Titre principal
        self.label_title = ctk.CTkLabel(self, text="🧪 Laboratoire de Tests IA", font=ctk.CTkFont(size=24, weight="bold"))
        self.label_title.pack(pady=20)

        # Onglets
        self.tabview = ctk.CTkTabview(self, width=750, height=500)
        self.tabview.pack(padx=20, pady=10, fill="both", expand=True)

        self.tab_sim = self.tabview.add("1. Simulateur")
        self.tab_backtest = self.tabview.add("2. Backtesting")
        self.tab_train = self.tabview.add("3. Entraînement Historique")

        self.setup_simulator_tab()
        self.setup_backtest_tab()
        self.setup_training_tab()

    # ==========================================
    # ONGLET 1 : SIMULATEUR
    # ==========================================
    def setup_simulator_tab(self):
        if not self.model_loaded:
            ctk.CTkLabel(self.tab_sim, text="❌ Modèle introuvable. Veuillez lancer un entraînement.", text_color="red").pack(pady=20)
            return
            
        frame_sliders = ctk.CTkFrame(self.tab_sim)
        frame_sliders.pack(pady=10, padx=20, fill="x")
        
        self.sliders = {}
        
        # Define basic features we want to simulate
        features_to_simulate = {
            'tick_rsi_14': (0, 100, 50),
            'tick_volatility_14': (0, 0.05, 0.01),
            'roc_10': (-0.5, 0.5, 0),
            'bb_width': (0, 0.01, 0.002)
        }
        
        row = 0
        for feat, (min_v, max_v, default_v) in features_to_simulate.items():
            label = ctk.CTkLabel(frame_sliders, text=f"{feat} ({default_v})")
            label.grid(row=row, column=0, padx=10, pady=5, sticky="w")
            
            slider = ctk.CTkSlider(frame_sliders, from_=min_v, to=max_v, command=lambda v, f=feat, l=label: self.update_slider_label(v, f, l))
            slider.set(default_v)
            slider.grid(row=row, column=1, padx=10, pady=5, sticky="ew")
            
            self.sliders[feat] = slider
            row += 1
            
        # Target configuration
        frame_target = ctk.CTkFrame(self.tab_sim)
        frame_target.pack(pady=10, padx=20, fill="x")
        
        ctk.CTkLabel(frame_target, text="Barrière (%) :").grid(row=0, column=0, padx=10, pady=5)
        self.barrier_entry = ctk.CTkEntry(frame_target)
        self.barrier_entry.insert(0, "0.005") # 5% default
        self.barrier_entry.grid(row=0, column=1, padx=10, pady=5)
        
        ctk.CTkLabel(frame_target, text="Ticks Cibles :").grid(row=1, column=0, padx=10, pady=5)
        self.ticks_entry = ctk.CTkEntry(frame_target)
        self.ticks_entry.insert(0, "10")
        self.ticks_entry.grid(row=1, column=1, padx=10, pady=5)
        
        self.btn_simulate = ctk.CTkButton(self.tab_sim, text="🔮 Calculer la Probabilité", command=self.run_simulation)
        self.btn_simulate.pack(pady=20)
        
        self.result_label = ctk.CTkLabel(self.tab_sim, text="Probabilité de survie : --%", font=ctk.CTkFont(size=20, weight="bold"))
        self.result_label.pack(pady=10)

    def update_slider_label(self, value, feat, label):
        label.configure(text=f"{feat} ({value:.4f})")

    def run_simulation(self):
        # Create a mock dataframe with simulated values
        # Fill non-simulated features with zeroes or defaults
        mock_data = {
            'ema_9': [10000], 'ema_20': [10000], 'ema_50': [10000],
            'tick_rsi_14': [self.sliders['tick_rsi_14'].get()],
            'macd': [0], 'macd_signal': [0], 'macd_hist': [0],
            'bb_lower': [9990], 'bb_mid': [10000], 'bb_upper': [10010],
            'bb_width': [self.sliders['bb_width'].get()],
            'dist_bb_mid': [0], 'dist_bb_upper': [0], 'dist_bb_lower': [0],
            'tick_volatility_14': [self.sliders['tick_volatility_14'].get()],
            'volatility_variation': [0],
            'roc_5': [0], 'roc_10': [self.sliders['roc_10'].get()],
            'price_change_1': [0],
            'instant_volatility': [0],
            'up_freq_10': [0.5], 'up_freq_20': [0.5],
            'avg_move_10': [0.001], 'avg_move_20': [0.001]
        }
        
        df = pd.DataFrame(mock_data)
        barrier = float(self.barrier_entry.get()) / 100.0 # Convert % to decimal
        target_ticks = int(self.ticks_entry.get())
        
        prob = self.ml_filter.predict_survival(df, target_ticks, barrier)
        
        color = "green" if prob > 0.6 else "orange" if prob > 0.4 else "red"
        self.result_label.configure(text=f"Probabilité de survie : {prob:.2%}", text_color=color)

    # ==========================================
    # ONGLET 2 : BACKTESTING
    # ==========================================
    def setup_backtest_tab(self):
        self.bt_btn = ctk.CTkButton(self.tab_backtest, text="🚀 Lancer Backtest (3000 derniers ticks)", command=self.start_backtest)
        self.bt_btn.pack(pady=20)
        
        self.bt_log = ctk.CTkTextbox(self.tab_backtest, width=700, height=300)
        self.bt_log.pack(pady=10)
        self.bt_log.insert("0.0", "Prêt pour le backtest...\n")
        
    def start_backtest(self):
        self.bt_btn.configure(state="disabled", text="Backtest en cours...")
        self.bt_log.insert("end", "Téléchargement de l'historique R_10...\n")
        threading.Thread(target=self._run_backtest_thread, daemon=True).start()
        
    def _run_backtest_thread(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            df = loop.run_until_complete(self.backtester.fetch_history(count=3000))
            
            self.bt_log.insert("end", f"Téléchargé {len(df)} ticks.\nEnrichissement et simulation tick-by-tick...\n")
            
            results = self.backtester.run_backtest(df, initial_balance=100.0, stake=5.0)
            
            if "error" in results:
                self.bt_log.insert("end", f"Erreur: {results['error']}\n")
            else:
                self.bt_log.insert("end", "\n=== RESULTATS DU BACKTEST ===\n")
                self.bt_log.insert("end", f"Balance initiale : {results['initial_balance']}$\n")
                self.bt_log.insert("end", f"Balance finale   : {results['final_balance']:.2f}$\n")
                self.bt_log.insert("end", f"Profit Net       : {results['net_profit']:.2f}$\n")
                self.bt_log.insert("end", f"Trades pris      : {results['trades']}\n")
                self.bt_log.insert("end", f"Victoires        : {results['wins']}\n")
                self.bt_log.insert("end", f"Défaites         : {results['losses']}\n")
                self.bt_log.insert("end", f"Winrate          : {results['winrate']:.2f}%\n")
                self.bt_log.insert("end", "=============================\n")
                
        except Exception as e:
            self.bt_log.insert("end", f"Erreur critique lors du backtest : {e}\n")
            
        self.bt_btn.configure(state="normal", text="🚀 Lancer Backtest (3000 derniers ticks)")

    # ==========================================
    # ONGLET 3 : ENTRAÎNEMENT HISTORIQUE
    # ==========================================
    def setup_training_tab(self):
        self.train_btn = ctk.CTkButton(self.tab_train, text="📚 Démarrer l'Entraînement Massif", command=self.start_training)
        self.train_btn.pack(pady=20)
        
        self.train_log = ctk.CTkTextbox(self.tab_train, width=700, height=300)
        self.train_log.pack(pady=10)
        self.train_log.insert("0.0", "Attention: Cette opération va recréer le modèle de base rf_model.joblib.\n")
        
    def start_training(self):
        self.train_btn.configure(state="disabled", text="Entraînement en cours...")
        self.train_log.insert("end", "Lancement du script scripts/train_model.py...\n")
        threading.Thread(target=self._run_training_thread, daemon=True).start()
        
    def _run_training_thread(self):
        try:
            # Run the training script in a subprocess and capture output
            process = subprocess.Popen(
                ["python", "scripts/train_model.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=os.path.dirname(os.path.abspath(__file__))
            )
            
            for line in iter(process.stdout.readline, ''):
                self.train_log.insert("end", line)
                self.train_log.see("end")
                
            process.stdout.close()
            process.wait()
            
            if process.returncode == 0:
                self.train_log.insert("end", "\n✅ Entraînement terminé avec succès !\n")
                # Reload model in simulator
                model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "rf_model.joblib")
                self.ml_filter = MLFilter(model_path=model_path)
                self.model_loaded = True
            else:
                self.train_log.insert("end", f"\n❌ Échec de l'entraînement (Code: {process.returncode})\n")
                
        except Exception as e:
            self.train_log.insert("end", f"\n❌ Erreur d'exécution: {e}\n")
            
        self.train_btn.configure(state="normal", text="📚 Démarrer l'Entraînement Massif")

if __name__ == "__main__":
    app = LaboratoryGUI()
    app.mainloop()
