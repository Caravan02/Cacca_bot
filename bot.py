import os
import logging
import LoggingCazzi
import GoogleSheetsCazzi
from telegram import Update, ReactionTypeEmoji
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackContext
from dotenv import load_dotenv
import re

import cagatori # file con i membri del gruppo

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

# /add
async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Aggiungi riga al foglio google"""
    try:
        if not context.args:
            LoggingCazzi.log_user_activity(update, "ADD_COMMAND", "No data provided")
            await update.message.reply_text("Please provide data to add. Example: /add John,25,Engineer")
            return
        
        # Join arguments and split by comma
        data_text = ' '.join(context.args)
        data = [item.strip() for item in data_text.split(',')]
        
        LoggingCazzi.log_user_activity(update, "ADD_COMMAND", f"Data: {data}")
        
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

# /view
async def view_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View all data from Google Sheets"""
    try:
        LoggingCazzi.log_user_activity(update, "VIEW_COMMAND")
        
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

            if (cagatori.cagatori[user_id]):
                chi=cagatori.cagatori[user_id]
            else:
                logging.error(f"Cagatore non trovato.")
                await update.message.reply_text("Cagatore non trovato, inserirlo con /aggiungi.")
                return

            # giorno e ora
            if f"Giorno: " in user_message:
                value = user_message.split(f"Giorno: ")[1]
                giorno=re.split(r'[,;\n]+',value)[0]
            else:
                giorno = update.message.date.date().strftime('%d/%m/%y')
            if f"Ora: " in user_message:
                value = user_message.split(f"Ora: ")[1]
                ora=re.split(r'[,;\n]+',value)[0]
            else:
                ora = update.message.date.time().strftime('%H:%M')

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

            data=[chi, giorno, ora, citta, provincia, regione, stato, altitudine, velocita]

            logging.info(f"Data to be inserted: {data}")

            success = sheets_handler.append_data(data)

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
/rimuovi - Rimuovi cagatore

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

# /aggiungi  NOTA: sostituire questo obbrobrio con un db sql fatto bene
async def aggiungi_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Aggiungi cagatore"""
    LoggingCazzi.log_user_activity(update, "AGGIUNGI_COMMAND")

    # Sintassi /aggiungi <user_id> <nome_sullo_spreadsheet> 

    if context.args:
        if(context.args[1] and context.args[1][0]!="="):

            # NOTA: cagatori.cagatori è un dizionario in cui ci sono coppie {user_id, nome nello spreadsheet}.
            # Per aggiornarlo, lo aggiorno in memoria e poi ristampo il contenuto del file cagatori.py.
            # È una merda e va cambiato con qualcosa di sensato, tipo un database sql.
            # Anche perché boh vorrei vedere anche i nomi delle persone, cosa che al momento è impossibile.

            cagatori.cagatori[context.args[0]]=context.args[1]
            with open('cagatori.py', 'w') as file:
                print(f"# user id dei membri del gruppo\n\ncagatori={cagatori.cagatori}", file=file)
            await update.message.reply_text(f"Aggiunto il cagatore {context.args[1]} con user_id {context.args[0]}")
            logging.info(f"Aggiunto cagatore {context.args[1]} con user_id {context.args[0]}")
        else:
            await update.message.reply_text("Sintassi: /aggiungi <user_id> <nome_sullo_spreadsheet>")
            logging.info("Spiegata la sintassi di /rimuovi")
    else:
        await update.message.reply_text("Sintassi: /aggiungi <user_id> <nome_sullo_spreadsheet>")
        logging.info("Spiegata la sintassi di /rimuovi")

# /rimuovi  NOTA: sostituire questo obbrobrio con un db sql fatto bene
async def rimuovi_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Rimuovi cagatore"""
    LoggingCazzi.log_user_activity(update, "RIMUOVI_COMMAND")

    # Sintassi: /rimuovi <user_id>

    if context.args:
        if cagatori.cagatori[context.args[0]]:

            # NOTA: cagatori.cagatori è un dizionario in cui ci sono coppie {user_id, nome nello spreadsheet}.
            # Per aggiornarlo, lo aggiorno in memoria e poi ristampo il contenuto del file cagatori.py.
            # È una merda e va cambiato con qualcosa di sensato, tipo un database sql.
            # Anche perché boh vorrei vedere anche i nomi delle persone, cosa che al momento è impossibile.

            del cagatori.cagatori[context.args[0]]
            with open('cagatori.py', 'w') as file:
                print(f"# user id dei membri del gruppo\n\ncagatori={cagatori.cagatori}", file=file)
            await update.message.reply_text(f"Rimosso il cagatore con user_id {context.args}")
            logging.info("Rimosso cagatore con user_id {context.args}")
        else:
            logging.info(f"Il cagatore con user_id {context.args} non esiste")
            await update.message.reply_text(f"Il cagatore con user_id {context.args} non esiste")
    else:
        await update.message.reply_text("Sintassi: /rimuovi <user_id>")
        logging.info("Spiegata la sintassi di /rimuovi")

# /logs
async def show_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra i log recenti"""
    try:
        user_id = update.message.from_user.id
        
        # Check if user is admin (if ADMIN_USER_ID is set)
        if ADMIN_USER_ID and str(user_id) != ADMIN_USER_ID:
            LoggingCazzi.log_user_activity(update, "LOGS_COMMAND", "Unauthorized access attempt")
            await update.message.reply_text("❌ You are not authorized to use this command.")
            return
        
        LoggingCazzi.log_user_activity(update, "LOGS_COMMAND", "Requested logs")
        
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

# error_handler - viene eseguito quando c'è un qualche errore
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
        application.add_handler(CommandHandler("add", add_command))
        application.add_handler(CommandHandler("view", view_command))

        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("sintassi", sintassi_command))
        application.add_handler(CommandHandler("aggiungi", aggiungi_command))
        application.add_handler(CommandHandler("rimuovi", rimuovi_command))

        application.add_handler(CommandHandler("logs", show_logs))
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