import os
import logging
from logging.handlers import RotatingFileHandler
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv
import datetime

# Load environment variables from .env file
load_dotenv()

# Configuration from environment variables
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
GOOGLE_SHEETS_CREDENTIALS_FILE = os.getenv('GOOGLE_SHEETS_CREDENTIALS_FILE')
SPREADSHEET_NAME = os.getenv('SPREADSHEET_NAME')
WORKSHEET_NAME = os.getenv('WORKSHEET_NAME', 'Sheet1')
ADMIN_USER_ID = os.getenv('ADMIN_USER_ID')
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# Validate required environment variables
required_vars = ['TELEGRAM_BOT_TOKEN', 'GOOGLE_SHEETS_CREDENTIALS_FILE', 'SPREADSHEET_NAME']
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

# Initialize logging
setup_logging()

class GoogleSheetsHandler:
    def __init__(self, creds_file, spreadsheet_name):
        self.creds_file = creds_file
        self.spreadsheet_name = spreadsheet_name
        self.client = None
        self.sheet = None
        self.logger = logging.getLogger(__name__)
        self._setup_client()
    
    def _setup_client(self):
        """Initialize Google Sheets client"""
        try:
            # Check if credentials file exists
            if not os.path.exists(self.creds_file):
                error_msg = f"Google Sheets credentials file not found: {self.creds_file}"
                self.logger.error(error_msg)
                raise FileNotFoundError(error_msg)
            
            scopes = [
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive"
            ]
            creds = Credentials.from_service_account_file(self.creds_file, scopes=scopes)
            self.client = gspread.authorize(creds)
            self.sheet = self.client.open(self.spreadsheet_name).worksheet(WORKSHEET_NAME)
            self.logger.info("Google Sheets client initialized successfully")
        except Exception as e:
            self.logger.error(f"Error setting up Google Sheets client: {e}", exc_info=True)
            raise
    
    def append_data(self, data):
        """Append data to the spreadsheet"""
        try:
            self.sheet.append_row(data)
            self.logger.info(f"Data appended to sheet: {data}")
            return True
        except Exception as e:
            self.logger.error(f"Error appending data: {e}", exc_info=True)
            return False
    
    def get_all_data(self):
        """Get all data from the spreadsheet"""
        try:
            data = self.sheet.get_all_records()
            self.logger.info(f"Retrieved {len(data)} records from spreadsheet")
            return data
        except Exception as e:
            self.logger.error(f"Error getting data: {e}", exc_info=True)
            return []

# Initialize Google Sheets handler
sheets_handler = GoogleSheetsHandler(GOOGLE_SHEETS_CREDENTIALS_FILE, SPREADSHEET_NAME)

def log_user_activity(update: Update, action: str, details: str = ""):
    """Helper function to log user activities"""
    user = update.effective_user
    user_info = f"User {user.id} ({user.username or 'no-username'})"
    
    logging.info(f"USER_ACTIVITY - {user_info} - {action} - {details}")

# Telegram Bot Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    log_user_activity(update, "START_COMMAND")
    
    # welcome_text = """
    # Welcome to the Google Sheets Bot!
    
    # Available commands:
    # /start - Show this help message
    # /add <data> - Add data to spreadsheet (comma-separated)
    # /view - View all data in spreadsheet
    # /help - Show help
    # /logs - Get recent logs (admin only)
    
    # You can also just send text to add it to the spreadsheet.
    # """
    # await update.message.reply_text(welcome_text)
    # logging.info("Start command response sent")

async def add_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add data to Google Sheets"""
    try:
        if not context.args:
            log_user_activity(update, "ADD_COMMAND", "No data provided")
            await update.message.reply_text("Please provide data to add. Example: /add John,25,Engineer")
            return
        
        # Join arguments and split by comma
        data_text = ' '.join(context.args)
        data = [item.strip() for item in data_text.split(',')]
        
        log_user_activity(update, "ADD_COMMAND", f"Data: {data}")
        
        success = sheets_handler.append_data(data)
        
        if success:
            response = f"✅ Data added successfully: {', '.join(data)}"
            await update.message.reply_text(response)
            logging.info(f"Data added successfully: {data}")
        else:
            await update.message.reply_text("❌ Failed to add data to spreadsheet")
            logging.error(f"Failed to add data: {data}")
            
    except Exception as e:
        logging.error(f"Error in add_data: {e}", exc_info=True)
        await update.message.reply_text("❌ An error occurred while adding data")

async def view_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View all data from Google Sheets"""
    try:
        log_user_activity(update, "VIEW_COMMAND")
        
        data = sheets_handler.get_all_data()
        
        if not data:
            await update.message.reply_text("📊 The spreadsheet is empty")
            return
        
        response = "📊 Spreadsheet Data:\n\n"
        for i, row in enumerate(data, 1):
            row_text = ", ".join([f"{k}: {v}" for k, v in row.items()])
            response += f"{i}. {row_text}\n"
        
        # Telegram has a message length limit, so truncate if necessary
        if len(response) > 4096:
            response = response[:4090] + "..."
            
        await update.message.reply_text(response)
        logging.info(f"View command completed. Sent {len(data)} records")
        
    except Exception as e:
        logging.error(f"Error in view_data: {e}", exc_info=True)
        await update.message.reply_text("❌ An error occurred while fetching data")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle regular text messages and add to spreadsheet"""
    try:
        user_message = update.message.text
        user_id = update.message.from_user.id
        username = update.message.from_user.username or "Unknown"
        
        log_user_activity(update, "TEXT_MESSAGE", f"Message: {user_message[:50]}...")


        if user_message.startswith("💩"):
            # Prepare data for spreadsheet

            import cagatori # file con i membri del gruppo

            # tabella per converire i nomi di telegram nei nomi sul google sheets. Uso lo user_id per determinarlo.

            if (user_id == cagatori.CARAVAN02):
                chi = "Nicola"
            # elif (user_id == cagatori. ...): 
            # inserire qui nuovi membri
            else:
                logging.error(f"Cagatore non trovato, inserirlo nel file.")
                return

            # giorno e ora
            if f"Giorno: " in user_message:
                value = user_message.split(f"Giorno: ")[1].split()[0]
                giorno=value
            else:
                giorno = update.message.date.date()
            if f"Ora: " in user_message:
                value = user_message.split(f"Ora: ")[1].split()[0]
                ora=value
            else:
                ora = update.message.date.time()

            # altri dati, se forniti
            if f"Città: " in user_message:
                value = user_message.split(f"Città: ")[1].split()[0]
                citta=value
            else:
                citta=""
            if f"Provincia: " in user_message:
                value = user_message.split(f"Provincia: ")[1].split()[0]
                provincia=value
            else:
                provincia=""
            if f"Regione: " in user_message:
                value = user_message.split(f"Regione: ")[1].split()[0]
                regione=value
            else:
                regione=""
            if f"Stato: " in user_message:
                value = user_message.split(f"Stato: ")[1].split()[0]
                stato=value
            else:
                stato=""
            if f"Altitudine: " in user_message:
                value = user_message.split(f"Altitudine: ")[1].split()[0]
                altitudine=value
            else:
                altitudine=""
            if f"Velocità: " in user_message:
                value = user_message.split(f"Velocità: ")[1].split()[0]
                velocita=value
            else:
                velocita=""

            # Inserimento dati in google spreadsheets

            data=[chi, giorno, ora, citta, provincia, regione, stato, altitudine, velocita]


            logging.info(f"Data to be inserted: {data}")

            success = sheets_handler.append_data(data)

            if success:
                await update.message.reply_text("✅ Your message has been saved to the spreadsheet!")
                logging.info(f"Message saved to spreadsheet: {user_message[:100]}...")
            else:
                await update.message.reply_text("❌ Failed to save your message")
                logging.error(f"Failed to save message: {user_message[:100]}...")
        else:
            logging.info(f"Message received, but not saved to spreadsheet: {user_message[:100]}...")
            
    except Exception as e:
        logging.error(f"Error in handle_message: {e}", exc_info=True)
        await update.message.reply_text("❌ An error occurred while saving your message")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a help message"""
    log_user_activity(update, "HELP_COMMAND")
    
    # help_text = """
    # Commands:
    # /start - Start the bot
    # /add <data> - Add comma-separated data to spreadsheet
    # /view - View all data in spreadsheet
    # /help - Show this help message
    # /logs - Get recent logs (admin only)
    
    # Examples:
    # /add John Doe,30,Developer
    # /add Product A,25.99,2024-01-01
    
    # You can also send regular messages to log them in the spreadsheet.
    # """

    help_text = """
    Lista dei comandi:

    /help - Visualizza questo messaggio
    /sintassi - Visualizza sintassi dei messaggi di cacca
    /ultime - Visualizza ultime 10 cacche 

    """

    await update.message.reply_text(help_text)
    logging.info("Help command response sent")

async def sintassi_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra sintassi per i messaggi di cacca"""
    log_user_activity(update, "SINTASSI_COMMAND")

    help_text = """
Sintassi per i messaggi di cacca:
· Il messaggio deve iniziare con "💩", altrimenti non verrà contato.
· Il messaggio può contenere informazioni extra, basta metterla all'interno del messaggio nella seguente forma: "Keyword: valore".
Le keyword accettate sono: Giorno, Ora, Città, Provincia, Regione, Stato, Altitudine, Velocità.
Occhio alle maiuscole! Le keyword non riconosciute saranno ignorate.
Esempio:
"💩
Ora: 04:20
Città: Sale Marasino
Provincia: Brescia
Velocità: 1000000000
"
"""
    await update.message.reply_text(help_text)
    logging.info("Sintassi command response sent")

async def show_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show recent logs (admin only)"""
    try:
        user_id = update.message.from_user.id
        
        # Check if user is admin (if ADMIN_USER_ID is set)
        if ADMIN_USER_ID and str(user_id) != ADMIN_USER_ID:
            log_user_activity(update, "LOGS_COMMAND", "Unauthorized access attempt")
            await update.message.reply_text("❌ You are not authorized to use this command.")
            return
        
        log_user_activity(update, "LOGS_COMMAND", "Requested logs")
        
        # Read the last few lines from the log file
        log_file_path = 'logs/telegram_bot.log'
        if not os.path.exists(log_file_path):
            await update.message.reply_text("📝 No log file found.")
            return
        
        with open(log_file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()
        
        # Get the last 50 lines (adjust as needed)
        recent_logs = lines[-50:]
        log_text = "".join(recent_logs)
        
        # Telegram message limit is 4096 characters
        if len(log_text) > 4096:
            log_text = "...\n" + log_text[-4090:]
        
        await update.message.reply_text(f"📝 Recent logs:\n```\n{log_text}\n```", 
                                      parse_mode='MarkdownV2')
        logging.info("Logs sent to admin user")
        
    except Exception as e:
        logging.error(f"Error in show_logs: {e}", exc_info=True)
        await update.message.reply_text("❌ An error occurred while reading logs")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors caused by Updates."""
    logging.error(f"Exception while handling an update: {context.error}", exc_info=True)
    
    # Notify admin user if ADMIN_USER_ID is set
    if ADMIN_USER_ID:
        try:
            await context.bot.send_message(
                chat_id=ADMIN_USER_ID,
                text=f"🚨 Bot error occurred:\n{context.error}"
            )
        except Exception as e:
            logging.error(f"Failed to send error notification to admin: {e}")

def main():
    """Start the bot."""
    try:
        # Create the Application
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

        # Add handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("add", add_data))
        application.add_handler(CommandHandler("view", view_data))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("sintassi", sintassi_command))
        application.add_handler(CommandHandler("logs", show_logs))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        # Add error handler
        application.add_error_handler(error_handler)

        # Start the Bot
        logging.info("Bot is starting...")
        application.run_polling()
        
    except Exception as e:
        logging.critical(f"Failed to start bot: {e}", exc_info=True)
        raise

if __name__ == '__main__':
    main()