import os
import logging
import LoggingCazzi
import GoogleSheetsCazzi
from telegram import Update, ReactionTypeEmoji
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
import re
from datetime import timedelta 
import sqlite3

# Load environment variables from .env file
load_dotenv()

# Configuration from environment variables
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
GOOGLE_SHEETS_CREDENTIALS_FILE = os.getenv('GOOGLE_SHEETS_CREDENTIALS_FILE')
SPREADSHEET_URL = os.getenv('SPREADSHEET_URL')
WORKSHEET_NAME = os.getenv('WORKSHEET_NAME')
GRUPPO_CACCA = (int)(os.getenv('GRUPPO_CACCA'))

# Validate required environment variables
required_vars = ['TELEGRAM_BOT_TOKEN', 'GOOGLE_SHEETS_CREDENTIALS_FILE', 'SPREADSHEET_URL', 'WORKSHEET_NAME', 'GRUPPO_CACCA']
missing_vars = [var for var in required_vars if not os.getenv(var)]
if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

# Initialize logging
LoggingCazzi.setup_logging()

# Connessione al database
# CREATE TABLE cagatori(
# user_id int NOT NULL,
# nome varchar(100) NOT NULL UNIQUE, 
# fuso_orario int NOT NULL,
# admin bool NOT NULL DEFAULT 0,
# PRIMARY KEY (user_id))
try:
    conn = sqlite3.connect('cagatori.db')
    cursor = conn.cursor()
    logging.info("Connesso al database.")
except sqlite3.Error as e:
    logging.error(f"Errore nella connessione al database: {e}")

# Initialize Google Sheets handler
sheets_handler = GoogleSheetsCazzi.GoogleSheetsHandler(GOOGLE_SHEETS_CREDENTIALS_FILE, SPREADSHEET_URL)

# Funzione per vedere chi è admin
def is_admin(user_id):
    cursor.execute("select admin from cagatori where user_id=?", (user_id,))
    ans=cursor.fetchone()
    if (ans and ans[0]):
        logging.info("Comando eseguito come admin.")
        return True
    else:
        return False

# Davvero con tutti i pacchetti di figa che ha python questa funzione non c'è?
def is_integer(s):
    if s[0] in ('-', '+'):
        return s[1:].isdigit()
    return s.isdigit()

# Comandi Bot

# /start
# async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     """/start (attualmente non operativo)."""
#     chat_id = update.effective_chat.id
#     user_id = update.effective_user.id
#     if (chat_id == GRUPPO_CACCA) or is_admin(user_id):
#         LoggingCazzi.log_user_activity(update, "START_COMMAND")
    

# Handler dei messaggi - viene eseguito ogni volta che qualcuno scrive un messaggio
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestione dei messaggi"""
    if(update.message):
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        LoggingCazzi.log_user_activity(update, "TEXT_MESSAGE", f"Message: {update.message.text[:50]}...")
        if (chat_id == GRUPPO_CACCA) or is_admin(user_id):
            try:
                user_message = update.message.text
                user_id = update.message.from_user.id

                if user_message.startswith("💩"):
                    logging.info("Messaggio inizia con 💩.")

                    # Preparare dati da mettere nella tabella

                    # tabella per converire i nomi di telegram nei nomi sul google sheets. Uso lo user_id per determinarlo.
                    cursor.execute("select nome, fuso_orario from cagatori where user_id=?", (user_id,))
                    dati=cursor.fetchone()
                    if(not dati):
                        # await update.message.reply_text("Errore. Probabilmente non sei nel database.")
                        logging.info("Utente non nel database. Input ignorato.")
                    else:
                        chi=dati[0]

                        # giorno e ora

                        # assumo che nessuno metta il giorno senza mettere l'ora
                        if f"Ora: " in user_message:
                            value = user_message.split(f"Ora: ")[1]
                            ora=re.split(r'[,;\n]+',value)[0]
                            if f"Giorno: " in user_message:
                                value = user_message.split(f"Giorno: ")[1]
                                giorno=re.split(r'[,;\n]+',value)[0]
                            else:
                                giorno = update.message.date.date().strftime('%d/%m/%y')
                        else:
                            # Fa lo shift in base al fuso orario 
                            data=update.message.date + timedelta(hours=dati[1])
                            giorno=data.date().strftime('%d/%m/%y')
                            ora=data.time().strftime('%H:%M')

                        # altri dati, se forniti
                        if f"Città: " in user_message:
                            value = user_message.split(f"Città: ")[1]
                            citta=re.split(r'[,;\n]+',value)[0]
                        else:
                            citta=""
                        if f"Provincia: " in user_message:
                            value = user_message.split(f"Provincia: ")[1]
                            provincia=re.split(r'[,;\n]+',value)[0]
                        else:
                            provincia=""
                        if f"Regione: " in user_message:
                            value = user_message.split(f"Regione: ")[1]
                            regione=re.split(r'[,;\n]+',value)[0]
                        else:
                            regione=""
                        if f"Stato: " in user_message:
                            value = user_message.split(f"Stato: ")[1]
                            stato=re.split(r'[,;\n]+',value)[0]
                        else:
                            stato=""
                        if f"Altitudine: " in user_message:
                            value = user_message.split(f"Altitudine: ")[1]
                            altitudine=re.split(r'[,;\n]+',value)[0]
                        else:
                            altitudine=""
                        if f"Velocità: " in user_message:
                            value = user_message.split(f"Velocità: ")[1]
                            velocita=re.split(r'[,;\n]+',value)[0]
                        else:
                            velocita=""

                        # Inserimento dati in google spreadsheets

                        roba=[chi, giorno, ora, citta, provincia, regione, stato, altitudine, velocita]

                        logging.info(f"Data da inserire: {roba}")

                        success = sheets_handler.append_data(roba)

                        # Se tutto va bene, reagire con "👍"

                        if success:
                            await context.bot.set_message_reaction(
                                chat_id=update.message.chat_id,
                                message_id=update.message.message_id,
                                reaction=[ReactionTypeEmoji("👍")]
                            )
                            logging.info(f"Dati cacca salvati")
                        else:
                            await update.message.reply_text("Qualcosa è andato storto. Riprova.")
                            logging.error(f"Dati cacca non salvati.")
                else:
                    logging.info(f"Messaggio ricevuto, ma ignorato perché non inizia con 💩.")

            except Exception as e:
                logging.error(f"Errore in handle_message: {e}", exc_info=True)
                await update.message.reply_text("Errore: riprovare.")
        else:
            logging.info("L'utente non sta messaggiando dal gruppo giusto e non è un admin.")
        logging.info("-"*50)

# /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manda un messaggio di aiuto"""
    if(update.message):
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        LoggingCazzi.log_user_activity(update, "HELP_COMMAND")
        if (chat_id == GRUPPO_CACCA) or is_admin(user_id):
            await update.message.reply_text("""
Lista dei comandi:

/help - Visualizza questo messaggio
/sintassi - Visualizza sintassi dei messaggi di cacca
/aggiungi - Aggiungi cagatore (admin only)
/join - Diventa un cagatore
/rimuovi - Rimuovi cagatore (admin only)
/abbandona - Smetti di essere un cagatore
/setfuso - Aggiorna il tuo fuso orario
/cagatori - Lista tutti i cagatori
/addadmin - Nomina admin (admin only)
/rmadmin - Rimuovi admin (admin only)
        """)
            logging.info("Messaggio di aiuto mandato")
        else:
            logging.info("L'utente non sta messaggiando dal gruppo giusto e non è un admin.")
        logging.info("-"*50)

# /sintassi
async def sintassi_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra sintassi per i messaggi di cacca"""
    if(update.message):
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        LoggingCazzi.log_user_activity(update, "SINTASSI_COMMAND")
        ans=is_admin(user_id)
        if ((chat_id == GRUPPO_CACCA) or ans):
            if(ans or cursor.execute("select user_id from cagatori where user_id=?", (user_id,)).fetchone()):
                await update.message.reply_text("""
Sintassi per i messaggi di cacca:

· Il messaggio deve iniziare con "💩", altrimenti non verrà contato.
· Il messaggio può contenere informazioni extra, basta metterla all'interno del messaggio nella seguente forma: "Keyword: valore".
Le keyword accettate sono: Giorno, Ora, Città, Provincia, Regione, Stato, Altitudine, Velocità, e le coppie "Keyword: valore" devono essere separate da "," ";" o "<a capo>".
Occhio alle maiuscole! Le keyword non riconosciute saranno ignorate.
Esempio:
"💩
Ora: 04:20
Città: Sale Marasino
Provincia: Brescia
Velocità: 1000000000"
        """)
                logging.info("Mandato messaggio con la sintassi")
            else:
                await update.message.reply_text("Non sei un cagatore. Fare /join per unirsi.")
                logging.info("L'utente non è un cagatore.")
        else:
            logging.info("L'utente non sta messaggiando dal gruppo giusto e non è un admin.")
        logging.info("-"*50)

# /aggiungi - aggiungi nuovo utente, se c'è già dà errore
async def aggiungi_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Aggiungi cagatore"""
    if(update.message):
        user_id = update.effective_user.id
        LoggingCazzi.log_user_activity(update, "AGGIUNGI_COMMAND", f"args: {context.args}")
        if (is_admin(user_id)):

            # Sintassi /aggiungi <user_id> <nome_spreadsheet> <fuso_orario UTC>

            if (len(context.args)==3 and is_integer(context.args[0]) and is_integer(context.args[2])):

                # Tutto implementato con un bel database sql

                try:
                    user_id=(int)(context.args[0])
                    nome=context.args[1]
                    fuso_orario=(int)(context.args[2])
                    cursor.execute("insert into cagatori values (?, ?, ?, 0)", (user_id, nome, fuso_orario)) # Inserisce come non_admin.
                    await update.message.reply_text(f"Aggiunto il cagatore {nome} con user_id {user_id} e fuso orario {fuso_orario}")
                    logging.info(f"Aggiunto il cagatore {nome} con user_id {user_id} e fuso orario {fuso_orario}")
                    conn.commit()
                except sqlite3.Error as e:
                    await update.message.reply_text("Errore nell'inserimento nel database. Probabilmente c'è già un cagatore con lo stesso nome o user_id")
                    logging.error(f"Errore nell'inserimento nel database. {e}")

            else:
                await update.message.reply_text("Sintassi: /aggiungi <user_id> <nome_spreadsheet> <fuso_orario UTC>")
                logging.info("Spiegata la sintassi di /aggiungi")
        else:
            if(update.effective_chat.id == GRUPPO_CACCA):
                if(cursor.execute("select user_id from cagatori where user_id=?", (user_id,)).fetchone()):
                    await update.message.reply_text("Errore: non sei un admin.")
                    logging.info("L'utente non è un admin.")
                else:
                    await update.message.reply_text("Non sei un cagatore. Fare /join per unirsi.")
                    logging.info("L'utente non è un cagatore.")
            else:
                logging.info("L'utente non sta messaggiando dal gruppo giusto e non è un admin.")
        logging.info("-"*50)

# /join - Unisciti alla cacca
async def join_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Joina la cacca"""
    if(update.message):
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        LoggingCazzi.log_user_activity(update, "JOIN_COMMAND", f"args: {context.args}")
        if ((chat_id == GRUPPO_CACCA) or is_admin(user_id)):

            # Sintassi /join <nome_spreadsheet> <fuso_orario UTC>

            if (len(context.args)==2 and is_integer(context.args[1])):

                # Tutto implementato con un bel database sql
                try:
                    user_id = update.message.from_user.id
                    nome=context.args[0]
                    fuso_orario=(int)(context.args[1])
                    cursor.execute("insert into cagatori values (?, ?, ?, 0)", (user_id, nome, fuso_orario))
                    await update.message.reply_text(f"Complementi {nome}! Ora sei anche tu un cagatore! Il tuo fuso orario UTC è {fuso_orario}")
                    logging.info(f"Aggiunto cagatore {nome} con user_id {nome} e fuso orario {fuso_orario}")
                    conn.commit()
                except sqlite3.Error as e:
                    await update.message.reply_text("Errore nell'inserimento nel database. Forse sei già nel database o qualcuno ha il tuo stesso nome")
                    logging.error(f"Errore nell'inserimento nel database. {e}")
            else:
                await update.message.reply_text("Sintassi: /join <nome_spreadsheet> <fuso_orario UTC>")
                logging.info("Spiegata la sintassi di /join")
        else:
            logging.info("L'utente non sta messaggiando dal gruppo giusto e non è un admin.")
        logging.info("-"*50)


# /rimuovi - Rimuovi un cagatore
async def rimuovi_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Rimuovi cagatore"""
    if(update.message):
        user_id = update.effective_user.id
        LoggingCazzi.log_user_activity(update, "RIMUOVI_COMMAND", f"args: {context.args}")
        if is_admin(user_id):

            # Sintassi: /rimuovi <nome>

            if (len(context.args)==1):

                # Tutto implementato con un bel database sql
                try:
                    nome=context.args[0]
                    cursor.execute("delete from cagatori where nome=?", (nome,))
                    await update.message.reply_text(f"Rimosso il cagatore {nome} (oppure già non c'era).")
                    logging.info(f"Rimosso cagatore {nome} (o già non c'era).")
                    conn.commit()
                except sqlite3.Error as e:
                    await update.message.reply_text(f"Errore nella rimozione.")
                    logging.error(f"Errore nella rimozione. {e}")
                
            else:
                await update.message.reply_text("Sintassi: /rimuovi <nome>")
                logging.info("Spiegata la sintassi di /rimuovi")
        else:
            if(update.effective_chat.id == GRUPPO_CACCA):
                if(cursor.execute("select user_id from cagatori where user_id=?", (user_id,)).fetchone()):
                    await update.message.reply_text("Errore: non sei un admin.")
                    logging.info("L'utente non è un admin.")
                else:
                    await update.message.reply_text("Non sei un cagatore. Fare /join per unirsi.")
                    logging.info("L'utente non è un cagatore.")
            else:
                logging.info("L'utente non sta messaggiando dal gruppo giusto e non è un admin.")
        logging.info("-"*50)

# /abbandona - Abbandona
async def abbandona_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Abbandona la cacca"""
    if(update.message):
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        LoggingCazzi.log_user_activity(update, "ABBANDONA_COMMAND")
        ans=is_admin(user_id)
        if ((chat_id == GRUPPO_CACCA) or ans):
            if(ans or cursor.execute("select user_id from cagatori where user_id=?", (user_id,)).fetchone()):

            # Sintassi: /abbandona

                try:
                    user_id = update.message.from_user.id
                    cursor.execute("delete from cagatori where user_id=?", (user_id,))
                    await update.message.reply_text(f"Addio, ci mancherai! 😢")
                    logging.info(f"Rimosso cagatore con user_id {user_id} (oppure non c'era)")
                    conn.commit()
                except sqlite3.Error as e:
                    await update.message.reply_text(f"Errore nella rimozione.")
                    logging.error(f"Errore nella rimozione. {e}")
            else:
                await update.message.reply_text("Non sei un cagatore. Fare /join per unirsi.")
                logging.info("L'utente non è un cagatore.")
        else:
            logging.info("L'utente non sta messaggiando dal gruppo giusto e non è un admin.")
        logging.info("-"*50)

# /setfuso
async def setfuso_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Modifica il fuso orario"""
    # Sintassi: /setfuso <nuovo_fuso UTC>
    if(update.message):
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        LoggingCazzi.log_user_activity(update, "SETFUSO_COMMAND", f"args: {context.args}")
        ans=is_admin(user_id)
        if ((chat_id == GRUPPO_CACCA) or ans):
            if(ans or cursor.execute("select user_id from cagatori where user_id=?", (user_id,)).fetchone()):
                if(len(context.args)==1 and is_integer(context.args[0])):
                    try:
                        user_id = update.message.from_user.id
                        fuso=(int)(context.args[0])
                        cursor.execute("update cagatori set fuso_orario=? where user_id=?", (fuso, user_id))
                        await update.message.reply_text(f"Fuso orario aggiornato a UTC {fuso}")
                        logging.info(f"Fuso orario aggiornato a UTC {fuso}")
                        conn.commit()
                    except sqlite3.Error as e:
                        await update.message.reply_text(f"Errore nell'update.")
                        logging.error(f"Errore. {e}")
                else:
                    await update.message.reply_text("Sintassi: /setfuso <nuovo_fuso UTC>")
                    logging.info("Spiegata la sintassi di /setfuso")
            else:
                await update.message.reply_text("Non sei un cagatore. Fare /join per unirsi.")
                logging.info("L'utente non è un cagatore.")
        else:
            logging.info("L'utente non sta messaggiando dal gruppo giusto e non è un admin.")
        logging.info("-"*50)

# /cagatori
async def cagatori_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Visualizza tutti i cagatori"""
    if(update.message):
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        LoggingCazzi.log_user_activity(update, "CAGATORI_COMMAND")
        if (chat_id == GRUPPO_CACCA) or is_admin(user_id):
            try:
                cursor.execute("select nome, fuso_orario, admin from cagatori")
                messaggio = 'Lista cagatori:\n\n'
                lista_cagatori=cursor.fetchall()
                # Si itera su tutti i cagatori
                for lista in lista_cagatori:
                    if(lista[2]): # Se è admin
                        messaggio += f"<b>{lista[0]}</b>, Fuso: {lista[1]}\n"
                    else:
                        messaggio += f"{lista[0]}, Fuso: {lista[1]}\n"
                await update.message.reply_text(messaggio, parse_mode='HTML') # Per scrivere in grassetto gli admin
                logging.info("Mandata lista dei cagatori")
                conn.commit()
            except sqlite3.Error as e:
                await update.message.reply_text(f"Errore nel recuperare la lista dei cagatori.")
                logging.error(f"Errore. {e}")
        else:
            logging.info("L'utente non sta messaggiando dal gruppo giusto e non è un admin.")
        logging.info("-"*50)

# /addadmin
async def addadmin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Nomina admin"""
    # Sintassi: /addadmin <nome>
    if(update.message):
        user_id = update.effective_user.id
        LoggingCazzi.log_user_activity(update, "ADDADMIN_COMMAND", f"args: {context.args}")
        if is_admin(user_id):
            if(len(context.args)==1):
                try:
                    nome=context.args[0]
                    cursor.execute("update cagatori set admin=1 where nome=?", (nome,))
                    await update.message.reply_text(f"Ora {nome} è un admin.")
                    logging.info(f"Ora {nome} è un admin.")
                    conn.commit()
                except sqlite3.Error as e:
                    await update.message.reply_text(f"Errore.")
                    logging.error(f"Errore. {e}")
            else:
                await update.message.reply_text("Sintassi: /addadmin <nome>")
                logging.info("Spiegata la sintassi di /addadmin")
        else:
            if(update.effective_chat.id == GRUPPO_CACCA):
                if(cursor.execute("select user_id from cagatori where user_id=?", (user_id,)).fetchone()):
                    await update.message.reply_text("Errore: non sei un admin.")
                    logging.info("L'utente non è un admin.")
                else:
                    await update.message.reply_text("Non sei un cagatore. Fare /join per unirsi.")
                    logging.info("L'utente non è un cagatore.")
            else:
                logging.info("L'utente non sta messaggiando dal gruppo giusto e non è un admin.")
        logging.info("-"*50)

# /rmadmin
async def rmadmin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Rimuovi admin"""
    # Sintassi: /rmadmin <nome>
    if(update.message):
        user_id = update.effective_user.id
        LoggingCazzi.log_user_activity(update, "RMADMIN_COMMAND", f"args: {context.args}")
        if is_admin(user_id):
            if(len(context.args)==1):
                try:
                    nome=context.args[0]
                    cursor.execute("update cagatori set admin=0 where nome=?", (nome,))
                    await update.message.reply_text(f"Ora {nome} non è un admin")
                    logging.info(f"Ora {nome} non è un admin")
                    conn.commit()
                except sqlite3.Error as e:
                    await update.message.reply_text(f"Errore.")
                    logging.error(f"Errore. {e}")
            else:
                await update.message.reply_text("Sintassi: /rmadmin <nome>")
                logging.info("Spiegata la sintassi di /rmadmin")
        else:
            if(update.effective_chat.id == GRUPPO_CACCA):
                if(cursor.execute("select user_id from cagatori where user_id=?", (user_id,)).fetchone()):
                    await update.message.reply_text("Errore: non sei un admin.")
                    logging.info("L'utente non è un admin.")
                else:
                    await update.message.reply_text("Non sei un cagatore. Fare /join per unirsi.")
                    logging.info("L'utente non è un cagatore.")
            else:
                logging.info("L'utente non sta messaggiando dal gruppo giusto e non è un admin.")
        logging.info("-"*50)

# async def rmcacca_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     """Rimuovi ultima propria cacca, se è tra le ultime 10"""
#     chat_id = update.effective_chat.id
#     user_id = update.effective_user.id
#     if (chat_id == GRUPPO_CACCA) or is_admin(user_id):
#         LoggingCazzi.log_user_activity(update, "RMCACCA_COMMAND")
#         cursor.execute("select nome from cagatori where user_id=?", (user_id,))
#         x=cursor.fetchone()
#         if(x):
#             nome=x[0]
#             success = sheets_handler.remove_last_cacca(nome)

#             if success:
#                 await update.message.reply_text(f"Ultima cacca di {nome} rimossa: {success}")
#                 logging.info(f"Dati cacca rimossi")
#             else:
#                 await update.message.reply_text("Qualcosa è andato storto. Riprova.")
#                 logging.error(f"Qualcosa è andato storto.")
#         else:
#             await update.message.reply_text("Errore. Probabimente non sei un cagatore.")
#             logging.error(f"Probabilmente {nome} non è un cagatore.")

# async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     """Logga errori"""
#     logging.error(f"Exception while handling an update: {context.error}", exc_info=True)
#     curso
#     for user_id in ADMINS_USER_ID:
#         try:
#             await context.bot.send_message(
#                 chat_id=user_id,
#                 text=f"Errore del bot:\n{context.error}"
#             )
#         except Exception as e:
#             logging.error(f"Failed to send error notification to admin: {e}")

def main():
    """Fai partire il bot."""
    try:
        # Create the Application
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

        # Add handlers
        # application.add_handler(CommandHandler("start", start_command))


# help - Visualizza questo messaggio
# sintassi - Visualizza sintassi dei messaggi di cacca
# aggiungi - Aggiungi cagatore (admin only)
# join - Diventa un cagatore
# rimuovi - Rimuovi cagatore (admin only)
# abbandona - Smetti di essere un cagatore
# setfuso - Aggiorna il tuo fuso orario
# cagatori - Lista tutti i cagatori
# addadmin - Nomina admin (admin only)
# rmadmin - Rimuovi admin (admin only)

        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("sintassi", sintassi_command))
        application.add_handler(CommandHandler("aggiungi", aggiungi_command))
        application.add_handler(CommandHandler("join", join_command))
        application.add_handler(CommandHandler("rimuovi", rimuovi_command))
        application.add_handler(CommandHandler("abbandona", abbandona_command))
        application.add_handler(CommandHandler("setfuso", setfuso_command))
        application.add_handler(CommandHandler("cagatori", cagatori_command))
        application.add_handler(CommandHandler("addadmin", addadmin_command))
        application.add_handler(CommandHandler("rmadmin", rmadmin_command))
        # application.add_handler(CommandHandler("rmcacca", rmcacca_command))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        # Add error handler
        # application.add_error_handler(error_handler)

        # Start the Bot
        logging.info("Bot partito...")
        application.run_polling()
        
    except Exception as e:
        logging.critical(f"Errore: bot non partito: {e}", exc_info=True)
        raise

if __name__ == '__main__':
    main()