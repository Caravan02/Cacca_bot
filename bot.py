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

conn = sqlite3.connect('cagatori.db')
cursor = conn.cursor()

# Davvero con tutti i pacchetti di figa che ha python questa funzione non c'è?

def is_integer(string):
    try:
        int(string)
        return True
    except ValueError:
        return False

# import cagatori # file con i membri del gruppo

# Load environment variables from .env file
load_dotenv()

# Configuration from environment variables
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
GOOGLE_SHEETS_CREDENTIALS_FILE = os.getenv('GOOGLE_SHEETS_CREDENTIALS_FILE')
SPREADSHEET_NAME = os.getenv('SPREADSHEET_NAME')
WORKSHEET_NAME = os.getenv('WORKSHEET_NAME', 'Sheet1')
ADMIN_USER_ID = os.getenv('ADMIN_USER_ID')

# Validate required environment variables
required_vars = ['TELEGRAM_BOT_TOKEN', 'GOOGLE_SHEETS_CREDENTIALS_FILE', 'SPREADSHEET_NAME']
missing_vars = [var for var in required_vars if not os.getenv(var)]
if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

# Initialize logging
LoggingCazzi.setup_logging()

# Initialize Google Sheets handler
sheets_handler = GoogleSheetsCazzi.GoogleSheetsHandler(GOOGLE_SHEETS_CREDENTIALS_FILE, SPREADSHEET_NAME)

# Comandi Bot

# /start
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/start (attualmente non operativo)."""
    LoggingCazzi.log_user_activity(update, "START_COMMAND")

# Handler dei messaggi - viene eseguito ogni volta che qualcuno scrive un messaggio
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestione dei messaggi"""
    try:
        user_message = update.message.text
        user_id = update.message.from_user.id
        
        LoggingCazzi.log_user_activity(update, "TEXT_MESSAGE", f"Message: {user_message[:50]}...")

        if user_message.startswith("💩"):
            # Preparare dati da mettere nella tabella

            # tabella per converire i nomi di telegram nei nomi sul google sheets. Uso lo user_id per determinarlo.
            try:
                cursor.execute("select nome, fuso_orario from cagatori where user_id=  ?", (user_id,))
                dati=cursor.fetchone()
                # if (cagatori.cagatori[user_id]):
                #     chi=cagatori.cagatori[user_id]
                chi=dati[0]

                # giorno e ora


                # assumo che nessuno metta il giorno senza mettere l'ora
                # else:
                #   giorno = update.message.date.date().strftime('%d/%m/%y')
                if f"Ora: " in user_message:
                    value = user_message.split(f"Ora: ")[1]
                    ora=re.split(r'[,;\n]+',value)[0]
                    if f"Giorno: " in user_message:
                        value = user_message.split(f"Giorno: ")[1]
                        giorno=re.split(r'[,;\n]+',value)[0]
                    else:
                        giorno = update.message.date.date().strftime('%d/%m/%y')
                else:
                    # user_tz = pytz.timezone(update.message.from_user.timezone)
                    data=update.message.date + timedelta(hours=dati[1])
                    giorno=data.date().strftime('%d/%m/%y')
                    ora=data.time().strftime('%H:%M')
                    # Prova a prendere il fuso orario, ma non funziona.

                    # if hasattr(update.message.from_user, 'timezone') and update.message.from_user.timezone:
                    #     user_tz = pytz.timezone(update.message.from_user.timezone)
                    #     local_time = update.message.date.astimezone(user_tz)
                    #     logging.info("Presa l'ora locale")
                    # else:
                    #     # Fallback: usa UTC
                    #     local_time = update.message.date  # Rimane in UTC
                    #     logging.info("Ora locale non presa. Prendo l'orario UTC")
                    # ora = local_time.time().strftime('%H:%M')

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

                logging.info(f"Data to be inserted: {roba}")

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
                    logging.error(f"Qualcosa è andato storto.")
            except sqlite3.Error as e:
                await update.message.reply_text("Errore. Probabilmente non sei nel database.")
                logging.error(f"Errore. Cagatore non trovato.")
        else:
            logging.info(f"Messaggio ricevuto, ma ignorato perché non inizia con 💩")
            
    except Exception as e:
        logging.error(f"Errore in handle_message: {e}", exc_info=True)
        await update.message.reply_text("Errore in handle_message")

# /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manda un messaggio di aiuto"""
    LoggingCazzi.log_user_activity(update, "HELP_COMMAND")



    await update.message.reply_text("""
Lista dei comandi:

/help - Visualizza questo messaggio
/sintassi - Visualizza sintassi dei messaggi di cacca
/aggiungi - Aggiungi cagatore
/join - Diventa un cagatore
/rimuovi - Rimuovi cagatore
/abbandona - Smetti di essere un cagatore
/setfuso - Aggiorna il tuo fuso orario
/cagatori - Lista tutti i cagatori

""")
    logging.info("Messaggio di aiuto mandato")

# /sintassi
async def sintassi_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra sintassi per i messaggi di cacca"""
    LoggingCazzi.log_user_activity(update, "SINTASSI_COMMAND")
    await update.message.reply_text("""
Sintassi per i messaggi di cacca:
· Il messaggio deve iniziare con "💩", altrimenti non verrà contato.
· Il messaggio può contenere informazioni extra, basta metterla all'interno del messaggio nella seguente forma: "Keyword: valore".
Le keyword accettate sono: Giorno, Ora, Città, Provincia, Regione, Stato, Altitudine, Velocità, e le coppie "Keyword: valore" devono essere separate da "," ";" o "\n" (a capo).
Occhio alle maiuscole! Le keyword non riconosciute saranno ignorate.
Esempio:
"💩
Ora: 04:20
Città: Sale Marasino
Provincia: Brescia
Velocità: 1000000000
"
""")
    logging.info("Mandato messaggio con la sintassi")

# /aggiungi - aggiungi nuovo utente, se c'è già dà errore
async def aggiungi_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Aggiungi cagatore"""
    LoggingCazzi.log_user_activity(update, "AGGIUNGI_COMMAND")

    # Sintassi /aggiungi <user_id> <nome_sullo_spreadsheet> <fuso_orario UTC>

    if (len(context.args)==3 and is_integer(context.args[0]) and is_integer(context.args[2])):

        # Tutto implementato con un bel database sql

        try:
            user_id=(int)(context.args[0])
            nome=context.args[1]
            fuso_orario=(int)(context.args[2])
            cursor.execute("insert into cagatori values (?, ?, ?)", (user_id, nome, fuso_orario))
            await update.message.reply_text(f"Aggiunto il cagatore {nome} con user_id {user_id} e fuso orario {fuso_orario}")
            logging.info(f"Aggiunto il cagatore {nome} con user_id {user_id} e fuso orario {fuso_orario}")
            conn.commit()
        except sqlite3.Error as e:
            await update.message.reply_text("Errore nell'inserimento nel database. Probabilmente c'è già un cagatore con lo stesso nome o user_id")
            logging.error(f"Errore nell'inserimento nel database. {e}")

    else:
        await update.message.reply_text("Sintassi: /aggiungi <user_id> <nome_sullo_spreadsheet> <fuso_orario UTC>")
        logging.info("Spiegata la sintassi di /aggiungi")

# join - Unisciti alla cacca
async def join_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Joina la cacca"""
    LoggingCazzi.log_user_activity(update, "JOIN_COMMAND")

    # Sintassi /join <nome_sullo_spreadsheet> <fuso_orario UTC>

    if (len(context.args)==2 and is_integer(context.args[1])):

        # Tutto implementato con un bel database sql
        try:
            user_id = update.message.from_user.id
            nome=context.args[0]
            fuso_orario=(int)(context.args[1])
            cursor.execute("insert into cagatori values (?, ?, ?)", (user_id, nome, fuso_orario))
            await update.message.reply_text(f"Complementi {nome}! Ora sei anche tu un cagatore! Il tuo fuso orario UTC è {fuso_orario}")
            logging.info(f"Aggiunto cagatore {nome} con user_id {nome} e fuso orario {fuso_orario}")
            conn.commit()
        except sqlite3.Error as e:
            await update.message.reply_text("Errore nell'inserimento nel database. Forse sei già nel database o qualcuno ha il tuo stesso nome")
            logging.error(f"Errore nell'inserimento nel database. {e}")
    else:
        await update.message.reply_text("Sintassi: /join <nome_sullo_spreadsheet> <fuso_orario UTC>")
        logging.info("Spiegata la sintassi di /join")

# /rimuovi
async def rimuovi_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Rimuovi cagatore"""
    LoggingCazzi.log_user_activity(update, "RIMUOVI_COMMAND")

    # Sintassi: /rimuovi <nome>

    if (len(context.args)==1):

        # Tutto implementato con un bel database sql
        try:
            nome=context.args[0]
            cursor.execute("delete from cagatori where nome=?", (nome,))
            await update.message.reply_text(f"Rimosso il cagatore {nome}")
            logging.info(f"Rimosso cagatore {nome}")
            conn.commit()
        except sqlite3.Error as e:
            await update.message.reply_text(f"Errore nella rimozione. Probabilmente non c'è nessun cagatore con questo nome.")
            logging.error(f"Errore nella rimozione. {e}")
        
    else:
        await update.message.reply_text("Sintassi: /rimuovi <user_id>")
        logging.info("Spiegata la sintassi di /rimuovi")

# /abbandona
async def abbandona_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Abbandona la cacca"""
    LoggingCazzi.log_user_activity(update, "ABBANDONA_COMMAND")

    # Sintassi: /abbandona

    try:
        user_id = update.message.from_user.id
        cursor.execute("delete from cagatori where user_id=?", (user_id,))
        await update.message.reply_text(f"Addio, ci mancherai! 😢")
        logging.info(f"Rimosso cagatore con user_id {user_id}")
        conn.commit()
    except sqlite3.Error as e:
        await update.message.reply_text(f"Errore nella rimozione. Probabilmente non sei nel database.")
        logging.error(f"Errore nella rimozione. {e}")

# /setfuso
async def setfuso_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Modifica il fuso orario"""

    # Sintassi: /setfuso <nuovo_fuso UTC> 
    if(len(context.args)==1 and is_integer(context.args[0])):
        try:
            user_id = update.message.from_user.id
            fuso=(int)(context.args[0])
            cursor.execute("update cagatori set fuso_orario=? where user_id=?", (fuso, user_id))
            await update.message.reply_text(f"Fuso orario aggiornato a UTC {fuso}")
            logging.info(f"Fuso orario aggiornato a UTC {fuso}")
            conn.commit()
        except sqlite3.Error as e:
            await update.message.reply_text(f"Errore. Probabilmente non sei nel database.")
            logging.error(f"Errore. {e}")
    else:
        await update.message.reply_text("Sintassi: /setfuso <nuovo_fuso UTC>")
        logging.info("Spiegata la sintassi di /setfuso")

# /cagatori
async def cagatori_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Visualizza tutti i cagatori"""

    try:
        cursor.execute("select nome from cagatori")
        await update.message.reply_text(f"Lista cagatori:\n{cursor.fetchall()}")
        logging.info("Mandata lista dei cagatori")
        conn.commit()
    except sqlite3.Error as e:
        await update.message.reply_text(f"Errore.")
        logging.error(f"Errore. {e}")

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
    """Fai partire il bot."""
    try:
        # Create the Application
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

        # Add handlers
        application.add_handler(CommandHandler("start", start_command))


# help - Visualizza questo messaggio
# sintassi - Visualizza sintassi dei messaggi di cacca
# aggiungi - Aggiungi cagatore
# join - Diventa un cagatore
# rimuovi - Rimuovi cagatore
# abbandona - Smetti di essere un cagatore
# setfuso - Aggiorna il tuo fuso orario
# cagatori - Lista tutti i cagatori

        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("sintassi", sintassi_command))
        application.add_handler(CommandHandler("aggiungi", aggiungi_command))
        application.add_handler(CommandHandler("join", join_command))
        application.add_handler(CommandHandler("rimuovi", rimuovi_command))
        application.add_handler(CommandHandler("abbandona", abbandona_command))
        application.add_handler(CommandHandler("setfuso", setfuso_command))
        application.add_handler(CommandHandler("cagatori", cagatori_command))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        # Add error handler
        application.add_error_handler(error_handler)

        # Start the Bot
        logging.info("Bot partito...")
        application.run_polling()
        
    except Exception as e:
        logging.critical(f"Errore: bot non partito: {e}", exc_info=True)
        raise

if __name__ == '__main__':
    main()