import os
import sqlite3
import logging
from telegram import Update
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration from environment variables
# TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
# GOOGLE_SHEETS_CREDENTIALS_FILE = os.getenv('GOOGLE_SHEETS_CREDENTIALS_FILE')
# SPREADSHEET_URL = os.getenv('SPREADSHEET_URL')
# WORKSHEET_NAME = os.getenv('WORKSHEET_NAME')
GRUPPO_CACCA = int(os.getenv('GRUPPO_CACCA'))

# Validate required environment variables
required_vars = ['GRUPPO_CACCA']
missing_vars = [var for var in required_vars if not os.getenv(var)]
if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

# Funzione per vedere chi è admin
def is_admin(user_id, cursor: sqlite3.Cursor) -> bool:
    cursor.execute("select admin from cagatori where user_id=?", (user_id,))
    ans=cursor.fetchone()
    if (ans and ans[0]):
        logging.info("Comando eseguito come admin.")
        return True
    else:
        return False

# Davvero con tutti i pacchetti di figa che ha python questa funzione non c'è?
def is_integer(s: str) -> bool:
    if s[0] in ('-', '+'):
        return s[1:].isdigit()
    return s.isdigit()

# Controlla se l'utente è in GRUPPO_CACCA oppure se è un admin
def check_gruppo_o_admin(update: Update, cursor: sqlite3.Cursor) -> bool:
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    if (chat_id == GRUPPO_CACCA) or is_admin(user_id, cursor):
        return True
    else:
        logging.info("L'utente non sta messaggiando dal gruppo giusto e non è un admin.")
        return False

# Controlla se l'utente è in GRUPPO_CACCA ed è all'interno del database, oppure se è un admin (che implica essere nel database)
async def check_cagatore_o_admin(update: Update, cursor: sqlite3.Cursor) -> bool:
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    ans=is_admin(user_id, cursor)
    if ((chat_id == GRUPPO_CACCA) or ans):
        if(ans or cursor.execute("select user_id from cagatori where user_id=?", (user_id,)).fetchone()):
            return True
        else:
            await update.message.reply_text("Non sei un cagatore. Fare /join per unirsi.")
            logging.info("L'utente non è un cagatore.")
            return False
    else:
        logging.info("L'utente non sta messaggiando dal gruppo giusto e non è un admin.")

# Controlla se l'utente è un admin (True), se non lo è ma è un cagatore, oppure se non è un cagatore (False), e manda un messaggio diverso nei tre casi.
async def check_admin(update: Update, cursor: sqlite3.Cursor) -> bool:
    user_id = update.effective_user.id
    if (is_admin(user_id, cursor)):
        return True  # Admin
    else:
        if(update.effective_chat.id == GRUPPO_CACCA):
            if(cursor.execute("select user_id from cagatori where user_id=?", (user_id,)).fetchone()):
                await update.message.reply_text("Errore: non sei un admin.")
                logging.info("L'utente non è un admin.")
                return 1  # Cagatore
            else:
                await update.message.reply_text("Non sei un cagatore. Fare /join per unirsi.")
                logging.info("L'utente non è un cagatore.")
                return -1 # Non cagatore
        else:
            logging.info("L'utente non sta messaggiando dal gruppo giusto e non è un admin.")
        

# def is_valid_date(date_string):
#     try:
#         datetime.strptime(date_string, "%d/%m/%y")
#         return True
#     except ValueError:
#         return False

# def is_valid_hour(date_string):
#     try:
#         datetime.strptime(date_string, "%H")
#         return True
#     except ValueError:
#         return False