import logging
import sys
import os
from datetime import datetime

def setup_logger(log_dir: str = "logs") -> logging.Logger:
    """
    Sets up the main logger for the application.
    Logs are written to the console and a file.
    """
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    logger = logging.getLogger() # root logger
    logger.setLevel(logging.INFO)
    
    # We don't want to clear all handlers because the GUI attaches a QueueLoggingHandler.
    # Instead, we just ensure we only add our stream/file handlers once.
    has_console = any(isinstance(h, logging.StreamHandler) and not hasattr(h, 'log_queue') for h in logger.handlers)
    
    if not has_console:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Console Handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # File Handler
        log_filename = f"deriv_bot_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(os.path.join(log_dir, log_filename))
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger
