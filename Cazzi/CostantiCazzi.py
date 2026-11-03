import os
from dotenv import load_dotenv

# Prende le costanti definite in .env
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
GOOGLE_SHEETS_CREDENTIALS_FILE = os.getenv('GOOGLE_SHEETS_CREDENTIALS_FILE')
SPREADSHEET_URL = os.getenv('SPREADSHEET_URL')
WORKSHEET_NAME = os.getenv('WORKSHEET_NAME')
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
GRUPPO_CACCA = int(os.getenv('GRUPPO_CACCA'))
FREQUENZA_CHECK = int(os.getenv('FREQUENZA_CHECK', '60'))
TEMPO_PER_RMCACCA = int(os.getenv('TEMPO_PER_RMCACCA', '1440'))

# Controlla che tutte siano definite
required_vars = ['TELEGRAM_BOT_TOKEN', 'GOOGLE_SHEETS_CREDENTIALS_FILE', 'SPREADSHEET_URL', 'WORKSHEET_NAME', 'GRUPPO_CACCA']
missing_vars = [var for var in required_vars if not os.getenv(var)]
if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")