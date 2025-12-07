import sqlite3
import logging
from telegram import Update
import re

from Cazzi.CostantiCazzi import GRUPPO_CACCA

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
        logging.warning("L'utente non sta messaggiando dal gruppo giusto e non è un admin.")
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
            logging.warning("L'utente non è un cagatore.")
            return False
    else:
        logging.warning("L'utente non sta messaggiando dal gruppo giusto e non è un admin.")

# Controlla se l'utente è un admin (True), se non lo è ma è un cagatore, oppure se non è un cagatore (False), e manda un messaggio diverso nei tre casi.
async def check_admin(update: Update, cursor: sqlite3.Cursor) -> bool:
    user_id = update.effective_user.id
    if (is_admin(user_id, cursor)):
        return True  # Admin
    else:
        if(update.effective_chat.id == GRUPPO_CACCA):
            if(cursor.execute("select user_id from cagatori where user_id=?", (user_id,)).fetchone()):
                await update.message.reply_text("Errore: non sei un admin.")
                logging.warning("L'utente non è un admin.")
                return 1  # Cagatore
            else:
                await update.message.reply_text("Non sei un cagatore. Fare /join per unirsi.")
                logging.warning("L'utente non è un cagatore.")
                return -1 # Non cagatore
        else:
            logging.warning("L'utente non sta messaggiando dal gruppo giusto e non è un admin.")
        
# Restituisce il giorno nel formato standard se è stato inserito bene (più o meno), None altrimenti. Formato standard: gg/mm/aa
def valid_day(date_string: str) -> str:
    if(re.compile(r"^[0-3]\d\/(0\d|1[0-2])\/(\d{2})( )*$").match(date_string)):
        return date_string[0:9]
    else:
        return

# Restituituisce l'ora nel formato standard se è stata inserita in modo sensato, None altrimenti. Formato standard: hh.mm
def valid_hour(date_string: str) -> str:
    if(re.compile(r"^([01]\d|2[0-3])[.:][0-5]\d( )*$").match(date_string)):
        date=date_string[0:5]
        return date.replace(':', '.')
    else:
        return
