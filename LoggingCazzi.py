import os
import logging
from logging.handlers import RotatingFileHandler
from telegram import Update

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration from environment variables
SPREADSHEET_NAME = os.getenv('SPREADSHEET_NAME')
WORKSHEET_NAME = os.getenv('WORKSHEET_NAME', 'Sheet1')
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# Validate required environment variables
required_vars = ['WORKSHEET_NAME', 'SPREADSHEET_NAME']
missing_vars = [var for var in required_vars if not os.getenv(var)]
if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

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
        'logs/telegram_bot.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    
    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    # Log startup information
    logging.info("=" * 50)
    logging.info("Telegram Bot Starting Up")
    logging.info("=" * 50)
    logging.info(f"Log level: {LOG_LEVEL}")
    logging.info(f"Spreadsheet: {SPREADSHEET_NAME}")
    logging.info(f"Worksheet: {WORKSHEET_NAME}")

def log_user_activity(update: Update, action: str, details: str = ""):
    """Helper function to log user activities"""
    user = update.effective_user
    user_info = f"User {user.id} ({user.username or 'no-username'})"
    logging.info("-" * 50)
    logging.info(f"USER_ACTIVITY - {user_info} - {action} - {details}")