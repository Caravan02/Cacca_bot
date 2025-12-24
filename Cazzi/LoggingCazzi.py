import os
import logging
from logging.handlers import RotatingFileHandler
from telegram import Update

from Cazzi.CostantiCazzi import LOG_LEVEL, SPREADSHEET_URL, WORKSHEET_NAME

# Crea cartella logs/ se non esiste
os.makedirs('logs', exist_ok=True)

def setup_logging():
    """Definisce e fa partire il logger"""
    # Prende il livello di logging
    log_level = getattr(logging, LOG_LEVEL.upper())
    
    # Crea logger
    logger = logging.getLogger()
    logger.setLevel(log_level)
    
    # Toglie Handler preesistenti
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Formato
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File handler con rotazione (max 10MB per file, con 2 file di backup)
    file_handler = RotatingFileHandler(
        'logs/bot.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=2,
        encoding='utf-8'
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    
    # Console handler (soppresso perché era una rottura)
    # console_handler = logging.StreamHandler()
    # console_handler.setLevel(log_level)
    # console_handler.setFormatter(formatter)

    # Toglie i logging pallosi
    httpx_logger = logging.getLogger('httpx')
    httpx_logger.setLevel(logging.WARNING)
    
    # Aggiunge handler al logger
    logger.addHandler(file_handler)
    # logger.addHandler(console_handler)
    
    # Il log parte
    logging.info("=" * 50)
    logging.info("Il bot sta partendo")
    logging.info("=" * 50)
    logging.info(f"Log level: {LOG_LEVEL}")
    logging.info(f"Spreadsheet: {SPREADSHEET_URL}")
    logging.info(f"Worksheet: {WORKSHEET_NAME}")

def log_user_activity(update: Update, action: str, details: str = ""):
    """Log per azioni dell'utente"""
    user = update.effective_user
    user_info = f"Utente {user.id} ({user.username or 'no-username'})"
    logging.info("-" * 50)
    logging.info(f"USER_ACTIVITY - {user_info} - {action} - {details}")