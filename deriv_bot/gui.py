import threading
import queue
import asyncio
import logging
import customtkinter as ctk

from main import main as bot_main

# --- CustomTkinter Theme Setup ---
ctk.set_appearance_mode("Dark")  # Options: "System", "Dark", "Light"
ctk.set_default_color_theme("green")  # Options: "blue", "green", "dark-blue"

class QueueLoggingHandler(logging.Handler):
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        try:
            msg = self.format(record)
            self.log_queue.put({"type": "log", "message": msg})
        except Exception:
            self.handleError(record)

class DerivBotApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("Deriv Bot - Sniper Bollinger")
        self.geometry("900x700")
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        self.ui_queue = queue.Queue()
        self.bot_thread = None
        self.is_running = False
        
        # Shared settings dict for the bot
        self.bot_settings = {
            "profit_threshold": 5.0,
            "cooldown_minutes": 60.0,
            "initial_stake": 5.0,
            "growth_rate": 0.05
        }

        # --- Sidebar Controls ---
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, rowspan=2, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(4, weight=1)

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="Sniper Bot", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        # --- Settings Panel ---
        self.settings_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.settings_frame.grid(row=1, column=0, padx=10, pady=10, sticky="ew")
        
        ctk.CTkLabel(self.settings_frame, text="Mise Initiale ($):").pack(anchor="w", padx=10)
        self.entry_stake = ctk.CTkEntry(self.settings_frame, width=150)
        self.entry_stake.insert(0, str(self.bot_settings["initial_stake"]))
        self.entry_stake.pack(padx=10, pady=(0, 5))
        
        ctk.CTkLabel(self.settings_frame, text="Taux de Croissance:").pack(anchor="w", padx=10)
        
        # We store the initial value as a string (e.g. "Auto" or "5%")
        initial_growth = self.bot_settings.get("growth_rate_str", "Auto")
        self.combo_growth = ctk.CTkComboBox(self.settings_frame, values=["Auto", "1%", "2%", "3%", "4%", "5%"], width=150)
        self.combo_growth.set(initial_growth)
        self.combo_growth.pack(padx=10, pady=(0, 5))
        
        ctk.CTkLabel(self.settings_frame, text="Profit Target ($):").pack(anchor="w", padx=10)
        self.entry_profit = ctk.CTkEntry(self.settings_frame, width=150)
        self.entry_profit.insert(0, str(self.bot_settings["profit_threshold"]))
        self.entry_profit.pack(padx=10, pady=(0, 5))
        
        ctk.CTkLabel(self.settings_frame, text="Cooldown (mins):").pack(anchor="w", padx=10)
        self.entry_cooldown = ctk.CTkEntry(self.settings_frame, width=150)
        self.entry_cooldown.insert(0, str(self.bot_settings["cooldown_minutes"]))
        self.entry_cooldown.pack(padx=10, pady=(0, 10))
        
        self.apply_btn = ctk.CTkButton(self.settings_frame, text="Apply Settings", command=self.apply_settings, width=150)
        self.apply_btn.pack(padx=10)
        # ----------------------

        self.start_btn = ctk.CTkButton(self.sidebar_frame, text="START BOT", command=self.start_bot, fg_color="green", hover_color="darkgreen")
        self.start_btn.grid(row=2, column=0, padx=20, pady=10)

        self.stop_btn = ctk.CTkButton(self.sidebar_frame, text="STOP BOT", command=self.stop_bot, fg_color="red", hover_color="darkred", state="disabled")
        self.stop_btn.grid(row=3, column=0, padx=20, pady=10)
        
        self.status_label = ctk.CTkLabel(self.sidebar_frame, text="Status: OFFLINE", text_color="gray", font=ctk.CTkFont(weight="bold"))
        self.status_label.grid(row=4, column=0, padx=20, pady=5)
        
        self.profit_label = ctk.CTkLabel(self.sidebar_frame, text="Profit: $0.00", text_color="cyan", font=ctk.CTkFont(size=16, weight="bold"))
        self.profit_label.grid(row=5, column=0, padx=20, pady=(5, 20))

        # --- Main Content Area ---
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        self.main_frame.grid_columnconfigure((0, 1), weight=1)
        self.main_frame.grid_rowconfigure(2, weight=1)
        
        # 1. Market Metrics Card
        self.market_frame = ctk.CTkFrame(self.main_frame)
        self.market_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        ctk.CTkLabel(self.market_frame, text="Live Market (R_10)", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
        
        self.lbl_price = ctk.CTkLabel(self.market_frame, text="Price: -")
        self.lbl_price.pack(anchor="w", padx=20)
        self.lbl_bb_mid = ctk.CTkLabel(self.market_frame, text="BB Middle: -")
        self.lbl_bb_mid.pack(anchor="w", padx=20)
        self.lbl_volatility = ctk.CTkLabel(self.market_frame, text="Volatility: -")
        self.lbl_volatility.pack(anchor="w", padx=20)
        
        # 2. Strategy Metrics Card
        self.strategy_frame = ctk.CTkFrame(self.main_frame)
        self.strategy_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        ctk.CTkLabel(self.strategy_frame, text="Strategy & AI", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
        
        self.lbl_squeeze = ctk.CTkLabel(self.strategy_frame, text="Squeeze: -")
        self.lbl_squeeze.pack(anchor="w", padx=20)
        self.lbl_ai_favorable = ctk.CTkLabel(self.strategy_frame, text="AI Favorable: -")
        self.lbl_ai_favorable.pack(anchor="w", padx=20)
        self.lbl_signal = ctk.CTkLabel(self.strategy_frame, text="Signal: -")
        self.lbl_signal.pack(anchor="w", padx=20)
        
        # 3. Log Console
        self.console_frame = ctk.CTkFrame(self.main_frame)
        self.console_frame.grid(row=2, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")
        self.console_frame.grid_rowconfigure(1, weight=1)
        self.console_frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(self.console_frame, text="Console Output", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, sticky="w", padx=10, pady=5)
        
        self.textbox = ctk.CTkTextbox(self.console_frame, font=ctk.CTkFont(family="Consolas", size=12))
        self.textbox.grid(row=1, column=0, padx=10, pady=(0,10), sticky="nsew")
        
        # Setup custom logging
        self.setup_logging()
        
        # Start polling queue
        self.after(100, self.poll_queue)
        
    def setup_logging(self):
        handler = QueueLoggingHandler(self.ui_queue)
        handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
        
        # We attach this handler to the root logger so it catches everything
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        self.log_handler = handler

    def apply_settings(self):
        try:
            target = float(self.entry_profit.get())
            cooldown = float(self.entry_cooldown.get())
            stake = float(self.entry_stake.get())
            growth_str = self.combo_growth.get()
            self.bot_settings['growth_rate_str'] = growth_str
            if growth_str == "Auto":
                self.bot_settings['growth_rate'] = "Auto"
            else:
                self.bot_settings['growth_rate'] = float(growth_str.replace('%', '')) / 100.0
            
            self.bot_settings["profit_threshold"] = target
            self.bot_settings["cooldown_minutes"] = cooldown
            self.bot_settings["initial_stake"] = stake
            
            self.log_message(f"[Settings] Updated: Stake={stake}$, Growth={growth_str}, Target={target}$, Cooldown={cooldown}m")
        except ValueError:
            self.log_message("[Error] Invalid settings values. Please enter numbers.")

    def log_message(self, msg):
        self.textbox.insert("end", msg + "\n")
        self.textbox.see("end")

    def start_bot(self):
        if not self.is_running:
            self.is_running = True
            self.start_btn.configure(state="disabled")
            self.stop_btn.configure(state="normal")
            self.status_label.configure(text="Status: RUNNING", text_color="green")
            self.log_message("Starting bot in background thread...")
            
            self.bot_thread = threading.Thread(target=self.run_asyncio_bot, daemon=True)
            self.bot_thread.start()

    def run_asyncio_bot(self):
        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(bot_main(self.ui_queue, self.bot_settings))
        except Exception as e:
            self.ui_queue.put({"type": "log", "message": f"Bot crashed: {e}"})
        finally:
            loop.close()
            # If the bot ends, update UI
            self.ui_queue.put({"type": "bot_stopped"})

    def stop_bot(self):
        self.log_message("Stopping bot (Note: Hard termination requires restarting the app currently due to asyncio loop)")
        self.is_running = False
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.status_label.configure(text="Status: STOPPED", text_color="red")

    def poll_queue(self):
        try:
            while True:
                msg = self.ui_queue.get_nowait()
                if msg["type"] == "log":
                    self.log_message(msg["message"])
                elif msg["type"] == "metrics":
                    self.update_metrics(msg)
                elif msg["type"] == "profit_update":
                    profit = msg["profit"]
                    color = "green" if profit >= 0 else "red"
                    self.profit_label.configure(text=f"Profit: ${profit:.2f}", text_color=color)
                elif msg["type"] == "status_update":
                    # For Cooldown state
                    status = msg["status"]
                    self.status_label.configure(text=f"Status: {status}", text_color="orange")
                elif msg["type"] == "bot_stopped":
                    self.stop_bot()
        except queue.Empty:
            pass
        finally:
            self.after(100, self.poll_queue)
            
    def update_metrics(self, data):
        self.lbl_price.configure(text=f"Price: {data['price']:.4f}")
        self.lbl_bb_mid.configure(text=f"BB Middle: {data['bb_mid']:.4f}")
        self.lbl_volatility.configure(text=f"Volatility: {data['volatility']:.4f}%")
        
        sq = data["squeeze"]
        sq_color = "green" if sq == "Près du centre" else "gray"
        self.lbl_squeeze.configure(text=f"Squeeze: {sq}", text_color=sq_color)
        
        prob_safe = data["prob_safe"]
        prob_color = "green" if prob_safe > 0.50 else "red"
        self.lbl_ai_favorable.configure(text=f"AI Favorable: {prob_safe:.2%}", text_color=prob_color)
        
        sig = data["signal"]
        sig_color = "green" if sig else "gray"
        self.lbl_signal.configure(text=f"Signal Detected: {'YES' if sig else 'NO'}", text_color=sig_color)


if __name__ == "__main__":
    app = DerivBotApp()
    app.mainloop()
