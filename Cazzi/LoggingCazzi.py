import os
import logging
from logging.handlers import RotatingFileHandler
from telegram import Update

from Cazzi.CostantiCazzi import LOG_LEVEL, SPREADSHEET_URL, WORKSHEET_NAME

# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)

def setup_logging():
    """Setup comprehensive logging configuration"""
    # Convert string log level to logging constant
    log_level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    
    # Create logger
    logger = logging.getLogger()
    logger.setLevel(log_level)
    
    # Clear any existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Log format
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File handler with rotation (max 10MB per file, keep 5 backup files)
    file_handler = RotatingFileHandler(
        'logs/bot.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    
    # Console handler (suppressed because it was annoying)
    # console_handler = logging.StreamHandler()
    # console_handler.setLevel(log_level)
    # console_handler.setFormatter(formatter)

    # Suppressing polling logs
    httpx_logger = logging.getLogger('httpx')
    httpx_logger.setLevel(logging.WARNING)
    
    # Add handlers to logger
    logger.addHandler(file_handler)
    # logger.addHandler(console_handler)
    
    # Log startup information
    logging.info("=" * 50)
    logging.info("Telegram Bot Starting Up")
    logging.info("=" * 50)
    logging.info(f"Log level: {LOG_LEVEL}")
    logging.info(f"Spreadsheet: {SPREADSHEET_URL}")
    logging.info(f"Worksheet: {WORKSHEET_NAME}")

def log_user_activity(update: Update, action: str, details: str = ""):
    """Helper function to log user activities"""
    user = update.effective_user
    user_info = f"User {user.id} ({user.username or 'no-username'})"
    logging.info("-" * 50)
    logging.info(f"USER_ACTIVITY - {user_info} - {action} - {details}")