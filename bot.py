import signal
import sys
import logging
from telegram import Update, ReactionTypeEmoji, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, ConversationHandler, MessageHandler, filters, ContextTypes
import re
from datetime import timedelta
import sqlite3
from apscheduler.schedulers.background import BackgroundScheduler

from Cazzi import LoggingCazzi, GoogleSheetsCazzi, HelpersCazzi
from Cazzi.CostantiCazzi import GOOGLE_SHEETS_CREDENTIALS_FILE, SPREADSHEET_URL, TELEGRAM_BOT_TOKEN, FREQUENZA_CHECK

# Inizializza logging
LoggingCazzi.setup_logging()

# Connessione al database
# CREATE TABLE cagatori(
# user_id int NOT NULL UNIQUE,
# nome TEXT NOT NULL UNIQUE,
# fuso int NOT NULL,
# admin bool NOT NULL DEFAULT 0,
# citta TEXT,
# stato TEXT,
# PRIMARY KEY (user_id));
# CREATE UNIQUE INDEX idx_cagatori_user_id ON cagatori(user_id);
# CREATE UNIQUE INDEX idx_cagatori_nome ON cagatori(nome);

# CREATE TABLE cacche(
# nome TEXT NOT NULL,
# giorno TEXT NOT NULL,
# ora TEXT NOT NULL,
# citta TEXT,
# stato TEXT,
# altitudine TEXT,
# velocita TEXT,
# messaggio int NOT NULL UNIQUE,
# timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
# CREATE INDEX idx_cacche_timestamp ON cacche(timestamp);

# Tabella delle cacche da inserire.

try:
    conn = sqlite3.connect('cagatori.db')
    cursor = conn.cursor()
    logging.info("Connesso al database.")
except sqlite3.Error as e:
    logging.error(f"Errore nella connessione al database: {e}")
    raise ConnectionError(f"Errore nella connessione al database: {e}")

# Inizializza Google Sheets handler
sheets_handler = GoogleSheetsCazzi.GoogleSheetsHandler(GOOGLE_SHEETS_CREDENTIALS_FILE, SPREADSHEET_URL)

# Nomi sensati per i valori ritornati nelle conversazioni
CACCA_CONFERMA, JOIN_NOME, JOIN_FUSO, JOIN_CITTA, JOIN_STATO, SETDATO_DATO, SETDATO_CAMBIA, RMCACCA_RIMUOVI, ABBANDONA_SI, SUDO_MENU, SUDO_RMCACCA_SCEGLI, SUDO_RMCACCA_RIMUOVI, SUDO_ADDCACCA_MESSAGGIO, SUDO_ADDCACCA_CONFERMA, SUDO_ADDCACCA_SI, SUDO_RMADMIN_DECLASSA, SUDO_ADDADMIN_PROMUOVI, SUDO_RMUSER_RIMUOVI = range(18)


# Comandi Bot

# Gestisce le cacche
async def cacca_handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestione dei messaggi"""
    if(update.message):
        LoggingCazzi.log_user_activity(update, "CACCA", f"Messaggio: {update.message.text[:50]}...")
        if (HelpersCazzi.check_gruppo_o_admin(update, cursor)):

            user_message = update.message.text
            user_id = update.message.from_user.id

            # Preparare dati da mettere nella tabella

            # Tabella per converire i nomi di telegram nei nomi sul google sheets. Uso lo user_id per determinarlo.
            cursor.execute("select nome, fuso, citta, stato from cagatori where user_id=?", (user_id,))
            dati=cursor.fetchone()
            if(not dati):
                logging.warning("Utente non nel database: input ignorato.")
            else:

                [chi, fuso, citta, stato]=dati

                # Per controllare se i dati devono essere aggiornati nel database.
                flag = bool(False)

                # Le keywords sono ora case insensitive
                
                if(re.search("altitudine: ", user_message, re.IGNORECASE)):
                    value = re.split("altitudine: ", user_message, flags=re.IGNORECASE)[1]
                    altitudine=re.split(r'[,;\n]+',value)[0]
                    if(not altitudine.isdigit()):
                        await update.message.reply_text("Errore: altitudine non valida. Riprova.")
                        logging.warning("Errore: altitudine non valida.")
                        logging.info("-"*50)
                        return ConversationHandler.END
                else:
                    altitudine=""
                if(re.search("velocità: ", user_message, re.IGNORECASE)):
                    value = re.split("velocità: ", user_message, flags=re.IGNORECASE)[1]
                    velocita=re.split(r'[,;\n]+',value)[0]
                    if(not velocita.isdigit()):
                        await update.message.reply_text("Errore: velocità non valida. Riprova.")
                        logging.warning("Errore: velocità non valida.")
                        logging.info("-"*50)
                        return ConversationHandler.END
                else:
                    velocita=""

                # Dati potenzialmente da modificare nel database
                if(re.search("città: ", user_message, re.IGNORECASE)):
                    flag = bool(True)
                    value = re.split("città: ", user_message, flags=re.IGNORECASE)[1]
                    citta=re.split(r'[,;\n]+',value)[0]
                    if(not citta.isalpha()):
                        await update.message.reply_text("Errore: città non valida (sono accettate solo lettere). Riprova.")
                        logging.warning("Errore: città contiene caratteri che non sono lettere.")
                        logging.info("-"*50)
                        return ConversationHandler.END
                if(re.search("fuso: ", user_message, re.IGNORECASE)):
                    flag = bool(True)
                    value = re.split("fuso: ", user_message, flags=re.IGNORECASE)[1]
                    fuso=re.split(r'[,;\n]+',value)[0]
                    if(not HelpersCazzi.is_integer(fuso)):
                        await update.message.reply_text("Errore: fuso non valido (deve essere un intero). Riprova.")
                        logging.warning("Errore: fuso non valido.")
                        logging.info("-"*50)
                        return ConversationHandler.END
                    else:
                        fuso=int(fuso)
                if(re.search("stato: ", user_message, re.IGNORECASE)):
                    flag = bool(True)
                    value = re.split("stato: ", user_message, flags=re.IGNORECASE)[1]
                    stato=re.split(r'[,;\n]+',value)[0]
                    if(not stato.isalpha()):
                        await update.message.reply_text("Errore: stato non valido (sono accettate solo lettere). Riprova.")
                        logging.warning("Errore: stato contiene caratteri che non sono lettere.")
                        logging.info("-"*50)
                        return ConversationHandler.END

                # giorno e ora

                # assumo che nessuno metta il giorno senza mettere l'ora
                if(re.search("or[ae]: ", user_message, re.IGNORECASE)):
                    value = re.split("or[ae]: ", user_message, flags=re.IGNORECASE)[1]
                    ora=HelpersCazzi.valid_hour(re.split(r'[,;\n]+',value)[0])
                    if(not ora):
                        await update.message.reply_text("Errore: ora non valida. Riprova.")
                        logging.warning("Errore: ora non valida.")
                        logging.info("-"*50)
                        return ConversationHandler.END

                    if(re.search("giorno: ", user_message, re.IGNORECASE)):
                        value = re.split("giorno: ", user_message, flags=re.IGNORECASE)[1]
                        giorno=HelpersCazzi.valid_day(re.split(r'[,;\n]+',value)[0])
                        if(not giorno):
                            await update.message.reply_text("Errore: giorno non valido. Riprova.")
                            logging.warning("Errore: giorno non valido.")
                            logging.info("-"*50)
                            return ConversationHandler.END
                    else:
                        # Per assicurarsi che il giorno sia localizzato.
                        data=update.message.date + timedelta(hours=fuso)
                        giorno = data.date().strftime('%d/%m/%y')
                else:
                    # Fa lo shift in base al fuso orario
                    data=update.message.date + timedelta(hours=fuso)
                    giorno=data.date().strftime('%d/%m/%y')
                    ora=data.time().strftime('%H.%M')

                if(flag):
                    cursor.execute("update cagatori set citta=?, stato=?, fuso=? where user_id=?", (citta, stato, fuso, user_id))

                # Tastiera con le opzioni
                keyboard=[["Sì", "No"]]

                # Chiede conferma
                ans = await update.message.reply_text(
                    f"Verranno inseriti i seguenti dati:\n\nGiorno: {giorno}\nOra: {ora}\nCittà: {citta}\nStato: {stato}\nAltitudine: {altitudine}\nVelocità: {velocita}\n\nSono corretti?",
                    reply_markup=ReplyKeyboardMarkup(
                        keyboard, one_time_keyboard=True, resize_keyboard=True, selective=True
                    ),
                )
                context.user_data["roba"]=[chi, giorno, ora, citta, stato, altitudine, velocita]
                context.user_data["aggiornare"]=flag
                context.user_data["fuso"]=fuso
                context.user_data["messaggio"]=update.message.message_id
                context.user_data["eliminare"]=ans.message_id
                return CACCA_CONFERMA
        logging.info("-"*50)
    return ConversationHandler.END

# Inserisce la cacca se l'utente conferma
async def cacca_conferma(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if(update.message):
        LoggingCazzi.log_user_activity(update, "CACCA_SI")
        ans = await context.bot.send_message(chat_id=update.message.chat_id, text="Inserisco la cacca...", reply_markup=ReplyKeyboardRemove())

        roba=context.user_data["roba"]
        cursor.execute("insert into cacche (nome, giorno, ora, citta, stato, altitudine, velocita, messaggio) values (?, ?, ?, ?, ?, ?, ?, ?)", (roba[0], roba[1], roba[2], roba[3], roba[4], roba[5], roba[6], context.user_data["messaggio"]))
        conn.commit()
        logging.info(f"Roba da inserire: {roba}")

        # Cancella i messaggi precedenti

        await context.bot.delete_messages(chat_id=update.message.chat_id, message_ids=[context.user_data["eliminare"],update.message.message_id, ans.message_id])

        # Se tutto va bene, reagire con "👍"

        await context.bot.set_message_reaction(
            chat_id=update.message.chat_id,
            message_id=context.user_data["messaggio"],
            reaction=[ReactionTypeEmoji("👍")]
        )
        logging.info("Dati cacca salvati.")
        if(context.user_data["aggiornare"]):
            logging.info(f"Aggiornati i dati di {roba[0]}: Città: {roba[3]}, Stato: {roba[4]}, Fuso: {context.user_data["fuso"]}")

        context.user_data.clear()
        logging.info("-"*50)
        return ConversationHandler.END

# Rimuove la cacca se l'utente annulla
async def cacca_annulla(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if(update.message):
        LoggingCazzi.log_user_activity(update, "CACCA_ANNULLA", f"Messaggio: {update.message.text[:50]}")
        ans = await context.bot.send_message(chat_id=update.message.chat_id, text="Cacca annullata.", reply_markup=ReplyKeyboardRemove())
        conn.rollback() # Annulla update al database

        # Cancella i messaggi precedenti

        await context.bot.delete_messages(chat_id=update.message.chat_id, message_ids=[context.user_data["eliminare"], context.user_data["messaggio"], update.message.message_id, ans.message_id])
        context.user_data.clear()
        logging.info(f"Dati cacca non salvati, e dati non salvati nel database.")
        logging.info("-"*50)
        return ConversationHandler.END


# /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manda messaggio di aiuto"""
    if(update.message):
        LoggingCazzi.log_user_activity(update, "HELP_COMMAND")
        if HelpersCazzi.check_gruppo_o_admin(update, cursor):
            # Messaggio
            await update.message.reply_text("""
Cosa fare se sei appena entrato nel gruppo:
- Diventa un cagatore con il comando /join, inserendo i tuoi dati: nome sullo spreadheet, fuso orario, città e stato.

Come vengono trattati i messaggi di cacca?
- Se hai fatto /join, i messaggi inviati che iniziano con "💩" saranno contati come cacche, e i dati relativi registrati nello spreadsheet.
- Le informazioni base registrate con ogni cacca sono: il vostro nome, il giorno e l'ora (localizzati in base al vostro fuso orario), la città e lo stato in cui siete.
- Di base, cioè quando il messaggio è "💩", per capire giorno e ora vengono utilizzate la data e l'ora a cui avete inviato il messaggio, aggiustate con il fuso orario memorizzato, e per la città e lo stato vengono inseriti i valori memorizzati nel database.
- Il messaggio base può essere esteso con unteriori informazioni: vedere /sintassi per informazioni su come fare.
- Se nel messaggio vengono specificati fuso, città o stato, questi verranno memorizzati nel database, e diventeranno i nuovi valori di default (quindi la prossima volta che non specificherete una di queste informazioni, verrà usato questo valore).
- Per modificare i dati senza mandare una cacca, usare /setdato.
- Per visualizzare i propri dati attuali, usare il comando /mieidati.

Altre cose:
- /comandi manda una lista di tutti i comandi disponibili.
- /abbandona permette di essere rimosso dal database, e le proprie cacche non verranno più contate.
- /cagatori manda una lista di tutti i cagatori (cioè gli utenti inseriti nel database).

        """)
            logging.info("Messaggio di aiuto mandato.")
        logging.info("-"*50)


# /comandi
async def comandi_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manda la lista dei comandi"""
    if(update.message):
        LoggingCazzi.log_user_activity(update, "COMANDI_COMMAND")
        if HelpersCazzi.check_gruppo_o_admin(update, cursor):
            await update.message.reply_text("""
Lista dei comandi:

/help - Visualizza un messaggio di aiuto
/comandi - Manda una lista dei comandi
/join - Diventa un cagatore
/sintassi - Visualizza sintassi dei messaggi di cacca
/mieidati - Visualizza i propri dati
/setdato - Aggiorna un proprio dato
/rmcacca - Visualizza e rimuovi le ultime cacche inserite
/cagatori - Lista tutti i cagatori
/abbandona - Smetti di essere un cagatore
/annulla - Annulla il comando corrente
/sudo - Comando di gestione (solo per admin)
        """)
            logging.info("Lista dei comandi mandata.")
        logging.info("-"*50)


# /join
async def join_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Joina la cacca"""
    if(update.message):
        LoggingCazzi.log_user_activity(update, "JOIN_COMMAND")
        if(HelpersCazzi.check_gruppo_o_admin(update, cursor)):
            # Chiede il nome
            mess=await update.message.reply_text(
                "Inserisci il tuo nome. Questo è il nome che comaprirà sullo spreadsheet.\n\nFare /annulla in qualsiasi momento per annullare l'operazione."
            )
            # Memorizza gli id dei messaggi per poterli cancellare poi
            context.user_data["messaggio"]=update.message.message_id
            context.user_data["eliminare"]=[mess.message_id,]
            logging.info("Chiesto il nome.")
            return JOIN_NOME
        else:
            # Termina la conversazione se non è nel gruppo o non è admin
            logging.info("-"*50)
            return ConversationHandler.END

# Registra il nome e chiede il fuso
async def join_nome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if(update.message):
        LoggingCazzi.log_user_activity(update, "JOIN_NOME", f"Messaggio: {update.message.text[:50]}")
        context.user_data["eliminare"].append(update.message.message_id)
        if(update.message.text.isalpha()): # Controlla il nome
            context.user_data["nome"]=update.message.text # Registra il nome
            mess=await update.message.reply_text( # Chiede il fuso
                "Inserisci il tuo fuso orario UTC (esempio: +1)."
            )
            context.user_data["eliminare"].append(mess.message_id)
            logging.info("Chiesto il fuso.")
            return JOIN_FUSO
        else:
            logging.warning("Nome non valido")
            mess=await update.message.reply_text("Errore: nome non valido (sono accettate solo lettere). Riprova.")
            context.user_data["eliminare"].append(mess.message_id)
            return JOIN_NOME # Se non è valido, richiede il nome

# Registra il fuso e chiede la città
async def join_fuso(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if(update.message):
        LoggingCazzi.log_user_activity(update, "JOIN_FUSO", f"Messaggio: {update.message.text[:50]}")
        context.user_data["eliminare"].append(update.message.message_id)
        fuso=update.message.text
        if(HelpersCazzi.is_integer(fuso)): # Controlla il fuso
            context.user_data["fuso"]=int(fuso) # Registra il fuso
            mess=await update.message.reply_text( # Chiede la città
                "Inserisci la tua città attuale."
            )
            context.user_data["eliminare"].append(mess.message_id)
            logging.info("Chiesta la città.")
            return JOIN_CITTA
        else:
            logging.warning("Fuso non valido.")
            mess=await update.message.reply_text("Errore: fuso non valido. Reinserire il fuso.")
            context.user_data["eliminare"].append(mess.message_id)
            return JOIN_FUSO # Se non è valido, richiede il fuso

# Regista la città e chiede lo stato
async def join_citta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if(update.message):
        context.user_data["eliminare"].append(update.message.message_id)
        LoggingCazzi.log_user_activity(update, "JOIN_CITTA", f"Messaggio: {update.message.text[:50]}")
        if(update.message.text.isalpha()): # Controlla la città
            context.user_data["citta"]=update.message.text # Registra la città
            mess=await update.message.reply_text( # Chiede lo stato
                "Inserisci il tuo stato."
            )
            context.user_data["eliminare"].append(mess.message_id)
            logging.info("Chiesto lo stato.")
            return JOIN_STATO
        else:
            logging.warning("Città non valida.")
            mess=await update.message.reply_text("Errore: città non valida (sono accettate solo lettere). Riprova.")
            context.user_data["eliminare"].append(mess.message_id)
            return JOIN_CITTA # Se non è valido, richiede la città

# Chiede lo stato, dopodiché se è valido prende tutti i dati e crea il nuovo cagatore
async def join_stato(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if(update.message):
        LoggingCazzi.log_user_activity(update, "JOIN_STATO", f"Messaggio: {update.message.text[:50]}")
        context.user_data["eliminare"].append(update.message.message_id)
        stato=update.message.text
        if(stato.isalpha()): # Controlla lo stato
            # Prende i dati
            user_id=update.message.from_user.id
            nome=context.user_data["nome"]
            fuso=context.user_data["fuso"]
            citta=context.user_data["citta"]
            try:
                # Inserisce i dati nel database
                cursor.execute("insert into cagatori values (?, ?, ?, 0, ?, ?)", (user_id, nome, fuso, citta, stato))
                await update.message.reply_text(f"Complementi {nome}! Ora sei anche tu un* cagator*! Il tuo fuso orario UTC è {fuso}, la tua città è {citta} e il tuo stato è {stato}.")
                logging.info(f"Aggiunto cagatore {nome} con user_id {user_id}, fuso orario {fuso}, città {citta}, stato {stato}.")
                conn.commit()
            except sqlite3.Error as e:
                # Errore
                await update.message.reply_text("Errore nell'inserimento nel database. Forse sei già nel database o qualcuno ha il tuo stesso nome.")
                logging.warning(f"Errore nell'inserimento nel database: {e}")

            # Elimina messaggi

            await context.bot.delete_messages(chat_id=update.message.chat_id, message_ids=context.user_data["eliminare"])
            context.user_data.clear()
            logging.info("-"*50)
            return ConversationHandler.END
        else:
            # Se non è valido, richiede lo stato
            logging.warning("Stato non valido.")
            mess=await update.message.reply_text("Errore: stato non valido (sono accettate solo lettere). Riprova.")
            context.user_data["eliminare"].append(mess.message_id)
            return JOIN_STATO

# /annulla - annulla l'operazione di join
async def join_annulla(update: Update, context: ContextTypes.DEFAULT_TYPE):
    LoggingCazzi.log_user_activity(update, "JOIN_ANNULLA")
    context.user_data["eliminare"].append(update.message.message_id)
    mess=await update.message.reply_text("Operazione annullata.")
    context.user_data["eliminare"].append(mess.message_id)
    context.user_data["eliminare"].append(context.user_data["messaggio"])

    # Elimina messaggi

    await context.bot.delete_messages(chat_id=update.message.chat_id, message_ids=context.user_data["eliminare"])
    context.user_data.clear() # Pulisce i dati salvati precedentemente
    logging.info("Operazione annullata.")
    logging.info("-"*50)
    return ConversationHandler.END


# /sintassi
async def sintassi_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra sintassi per i messaggi di cacca"""
    if(update.message):
        LoggingCazzi.log_user_activity(update, "SINTASSI_COMMAND")
        if(await HelpersCazzi.check_cagatore_o_admin(update, cursor)):
            # Messaggio
            await update.message.reply_text("""
Sintassi per i messaggi di cacca:

· Il messaggio deve iniziare con "💩", altrimenti non verrà contato.
· Il messaggio può contenere informazioni extra, basta metterla all'interno del messaggio nella seguente forma: "keyword: valore".
Le keyword accettate sono: Giorno, Ora, Città, Stato, Altitudine, Velocità (l'altitudine è da considerarsi in metri slm e la velocità in km/h) e le coppie "Keyword: valore" devono essere separate da "," ";" o "<a capo>".
Le keyword sono case-insensitive. Le keyword non riconosciute saranno ignorate. L'ordine non è importante.

Esempio che usa ogni campo:
"💩
giorno: 03/03/25
ORA: 04.20
fusO: +1
Città: Sale Marasino
StAtO: Italia
altituDINE: 250
VELOcità: 340"
    """)

            logging.info("Mandato messaggio con la sintassi.")
        logging.info("-"*50)


# /mieidati
async def mieidati_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Visualizza i miei dati"""
    if(update.message):
        LoggingCazzi.log_user_activity(update, "MIEIDATI_COMMAND")
        if(await HelpersCazzi.check_cagatore_o_admin(update, cursor)):
            try:
                # Prende i dati del cagatore
                user_id = update.message.from_user.id
                cursor.execute("select nome, admin, fuso, citta, stato from cagatori where user_id=?", (user_id,))
                dati=cursor.fetchone()
                if(dati[1]): # Se è admin
                    messaggio = f"Nome: <b>{dati[0]}</b>\n"
                else:
                    messaggio = f"Nome: {dati[0]}\n"
                messaggio += f"Fuso: {dati[2]}\nCittà: {dati[3]}\nStato: {dati[4]}\n"
                await update.message.reply_text(messaggio, parse_mode='HTML') # Per scrivere in grassetto gli admin
                logging.info(f"Mandati dati di {dati[0]}")
            except sqlite3.Error as e:
                # Errore
                await update.message.reply_text(f"Errore nel recuperare i dati.")
                logging.error(f"Errore. {e}")
        logging.info("-"*50)


# /setdato
async def setdato_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Modifica i propri dati"""
    if(update.message):
        LoggingCazzi.log_user_activity(update, "SETDATO_COMMAND")
        if(await HelpersCazzi.check_cagatore_o_admin(update, cursor)):
            context.user_data["messaggio"]=update.message.message_id
            # Tastiera con le opzioni
            keyboard=[["Fuso", "Città"], ["Stato", "Annulla"]]

            # Chiede dato da cambiare
            mess=await update.message.reply_text(
                "Quale dato vuoi cambiare?\n\nScrivi /annulla in qualsiasi momento per annullare.",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard, one_time_keyboard=True, resize_keyboard=True, selective=True
                ),
            )
            context.user_data["eliminare"]=[mess.message_id]
            logging.info("Chiesto dato da cambiare.")
            return SETDATO_DATO
        else:
            logging.info("-"*50)
            return ConversationHandler.END

# Salva l'opzione, e chiede il nuovo valore
async def setdato_dato(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if(update.message):
        LoggingCazzi.log_user_activity(update, "SETDATO_DATO", f"Messaggio: {update.message.text}")
        context.user_data["eliminare"].append(update.message.message_id)
        context.user_data["dato"]=update.message.text # Salva l'opzione
        mess=await update.message.reply_text( # Chiede il nuovo valore
            "Scrivi il nuovo valore.", reply_markup=ReplyKeyboardRemove()
        )
        context.user_data["eliminare"].append(mess.message_id)
        logging.info("Chiesto nuovo valore del dato.")
        return SETDATO_CAMBIA

# Salva il nuovo valore, e lo cambia se è valido
async def setdato_cambia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if(update.message):
        LoggingCazzi.log_user_activity(update, "SETDATO_CAMBIA", f"Messaggio: {update.message.text}")
        context.user_data["eliminare"].append(update.message.message_id)
        # Prende le informazioni
        user_id=update.message.from_user.id
        dato=context.user_data["dato"]
        roba=update.message.text
        if dato == 'Fuso':
            # Controlla fuso
            if(HelpersCazzi.is_integer(roba)): # Controlla validità
                # Aggiorna dato
                fuso=(int)(roba)
                cursor.execute("update cagatori set fuso=? where user_id=?", (fuso, user_id))
                await update.message.reply_text(f"Fuso orario aggiornato a UTC {fuso}.")
                logging.info(f"Fuso orario aggiornato a UTC {fuso}.")
                conn.commit()
            else:
                # Errore
                logging.warning("Errore: fuso non valido. Riprova.")
                mess=await update.message.reply_text("Errore: fuso non valido. Riprova")
                context.user_data["eliminare"].append(mess.message_id)
                return SETDATO_CAMBIA

        elif dato == 'Città':
            if(roba.isalpha()): # Controlla validità
                # Aggiorna dato
                cursor.execute("update cagatori set citta=? where user_id=?", (roba, user_id))
                await update.message.reply_text(f"Città aggiornata a {roba}.")
                logging.info(f"Città aggiornata a {roba}.")
                conn.commit()
            else:
                # Errore
                logging.warning("Città non valida.")
                mess=await update.message.reply_text("Errore: città non valida (sono accettate solo lettere). Riprova.")
                context.user_data["eliminare"].append(mess.message_id)
                return SETDATO_CAMBIA

        else: # dato == 'Stato'
            if(roba.isalpha()): # Controlla validità
                # Aggiorna dato
                cursor.execute("update cagatori set stato=? where user_id=?", (roba, user_id))
                await update.message.reply_text(f"Stato aggiornato a {roba}.")
                logging.info(f"Stato aggiornato a {roba}.")
                conn.commit()
            else:
                # Errore
                logging.warning("Stato non valido.")
                mess=await update.message.reply_text("Errore: stato non valido (sono accettate solo lettere). Riprova.")
                context.user_data["eliminare"].append(mess.message_id)
                return SETDATO_CAMBIA
        await context.bot.delete_messages(chat_id=update.message.chat_id, message_ids=context.user_data["eliminare"])
        context.user_data.clear() # Pulisce i dati raccolti
        logging.info("-"*50)
        return ConversationHandler.END

# /annulla
async def setdato_annulla(update: Update, context: ContextTypes.DEFAULT_TYPE):
    LoggingCazzi.log_user_activity(update, "SETDATO_ANNULLA", f"Messaggio: {update.message.text[:50]}")
    mess=await update.message.reply_text("Operazione annullata.", reply_markup=ReplyKeyboardRemove()) # Fa sparire la tastiera
    context.user_data["eliminare"].append(update.message.message_id)
    context.user_data["eliminare"].append(mess.message_id)
    context.user_data["eliminare"].append(context.user_data["messaggio"])

    # Elimina messaggi

    await context.bot.delete_messages(chat_id=update.message.chat_id, message_ids=context.user_data["eliminare"])
    context.user_data.clear() # Pulisce i dati raccolti
    logging.info("Operazione annullata.")
    logging.info("-"*50)
    return ConversationHandler.END


# /rmcacca
async def rmcacca_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Rimuove una propria cacca"""
    if(update.message):
        LoggingCazzi.log_user_activity(update, "RMCACCA_COMMAND")
        if(await HelpersCazzi.check_cagatore_o_admin(update, cursor)):
            user_id=update.message.from_user.id
            nome=cursor.execute("select nome from cagatori where user_id=?", (user_id,)).fetchone()[0]
            ultime_cacche=cursor.execute("select nome, giorno, ora, citta, stato, altitudine, velocita, messaggio from cacche where nome=?", (nome,)).fetchall()
            if(ultime_cacche):
                messaggio="Le tue cacche recenti sono:\n\n"
                i=1
                for cacca in ultime_cacche:
                    messaggio+=f"{i}: {cacca[0:7]} \n"
                    i=i+1
                messaggio+="\nInserire il numero della cacca da cancellare, /annulla per annullare.\n"
                mess=await update.message.reply_text(messaggio)
                logging.info("Mandato messaggio con le cacche recenti.")
                context.user_data["cacche"]=ultime_cacche
                context.user_data["eliminare"]=[update.message.message_id, mess.message_id]
                return RMCACCA_RIMUOVI
            else:
                await update.message.reply_text("Non hai inserito cacche di recente.")
                logging.info("Non ci sono cacche dell'utente nella tabella cacche.")
                logging.info("-"*50)
                return ConversationHandler.END
        else:
            logging.info("-"*50)
            return ConversationHandler.END
        
# Legge il numero inserito ed elimina

async def rmcacca_rimuovi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if(update.message):
        LoggingCazzi.log_user_activity(update, "RMCACCA_RIMUOVI", f"Messaggio: {update.message.text}")
        context.user_data["eliminare"].append(update.message.message_id)
        i=int(update.message.text)-1
        cacche=context.user_data["cacche"]
        if(i>=0 and i<len(cacche)):
            messid=int(cacche[i][7])
            cursor.execute("delete from cacche where messaggio=?", (messid,))
            conn.commit()
            mess=await update.message.reply_text("Cacca rimossa con successo.")
            context.user_data["eliminare"].append(mess.message_id)
            context.user_data["eliminare"].append(messid) # Rinuove messaggio con la cacca
            await context.bot.delete_messages(chat_id=update.message.chat_id, message_ids=context.user_data["eliminare"])
            context.user_data.clear() # Pulisce i dati raccolti
            logging.info(f"Cacca rimossa con successo: {cacche[i]}")
            logging.info("-"*50)
            return ConversationHandler.END
        else:
            logging.warning("Numero inserito non valido.")
            mess=await update.message.reply_text("Il numero inserito non è valido, riprova.")
            context.user_data["eliminare"].append(mess.message_id)
            return RMCACCA_RIMUOVI

# /annulla
async def rmcacca_annulla(update: Update, context: ContextTypes.DEFAULT_TYPE):
    LoggingCazzi.log_user_activity(update, "RMCACCA_ANNULLA", f"Messaggio: {update.message.text[:50]}")
    mess=await update.message.reply_text("Operazione annullata.")
    context.user_data["eliminare"].append(update.message.message_id)
    context.user_data["eliminare"].append(mess.message_id)

    # Elimina messaggi

    await context.bot.delete_messages(chat_id=update.message.chat_id, message_ids=context.user_data["eliminare"])
    context.user_data.clear() # Pulisce i dati raccolti
    logging.info("Operazione annullata.")
    logging.info("-"*50)
    return ConversationHandler.END


# /cagatori
async def cagatori_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Visualizza tutti i cagatori"""
    if(update.message):
        LoggingCazzi.log_user_activity(update, "CAGATORI_COMMAND")
        if(HelpersCazzi.check_gruppo_o_admin(update, cursor)):
            try:
                # Prende dati di tutti i cagatori
                cursor.execute("select nome, fuso, admin, citta, stato from cagatori")
                messaggio = 'Lista cagatori:\n\n'
                lista_cagatori=cursor.fetchall()
                # Si itera su tutti i cagatori
                for lista in lista_cagatori:
                    if(lista[2]): # Se è admin
                        messaggio += f"<b>{lista[0]}</b>   Fuso: {lista[1]}, Città: {lista[3]}, Stato: {lista[4]}\n"
                    else:
                        messaggio += f"{lista[0]}   Fuso: {lista[1]}, Città: {lista[3]}, Stato: {lista[4]}\n"
                await update.message.reply_text(messaggio, parse_mode='HTML') # Per scrivere in grassetto gli admin
                logging.info("Mandata lista dei cagatori.")
            except sqlite3.Error as e:
                # Errore
                await update.message.reply_text(f"Errore nel recuperare la lista dei cagatori.")
                logging.error(f"Errore: {e}")
        logging.info("-"*50)


# /abbandona
async def abbandona_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Abbandona la cacca"""
    if(update.message):
        LoggingCazzi.log_user_activity(update, "ABBANDONA_COMMAND")
        if(await HelpersCazzi.check_cagatore_o_admin(update, cursor)):
            context.user_data["messaggio"]=update.message.message_id
            # Tastiera con le opzioni
            keyboard=[["Sì", "No"]]

            # Chiede conferma
            mess=await update.message.reply_text(
                "Vuoi davvero uscire dal database? Le tue cacche non verranno più registrate.",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard, one_time_keyboard=True, resize_keyboard=True, selective=True
                ),
            )
            context.user_data["eliminare"]=[mess.message_id]
            logging.info("Chiesta conferma all'utente che vuole abbandonare.")
            return ABBANDONA_SI
        else:
            logging.info("-"*50)
            return ConversationHandler.END

# Se dice sì, abbandona
async def abbandona_si(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if(update.message):
        LoggingCazzi.log_user_activity(update, "ABBANDONA_SI")
        context.user_data["eliminare"].append(update.message.message_id)
        try:
            # Rimuovi dal database
            user_id = update.message.from_user.id
            cursor.execute("delete from cagatori where user_id=?", (user_id,))
            await update.message.reply_text(f"Addio, ci mancherai! 😢", reply_markup=ReplyKeyboardRemove()) # Fai sparire la tastiera
            logging.info(f"Il cagatore {user_id} se n'è andato e non ritorna più.")
            conn.commit()
        except sqlite3.Error as e:
            # Errore
            await update.message.reply_text(f"Errore nella rimozione.", reply_markup=ReplyKeyboardRemove()) # Fai sparire la tastiera
            logging.error(f"Errore nella rimozione: {e}")

        # Elimina messaggi
        await context.bot.delete_messages(chat_id=update.message.chat_id, message_ids=context.user_data["eliminare"])
        context.user_data.clear()
        logging.info("-"*50)
        return ConversationHandler.END

# Annulla
async def abbandona_annulla(update: Update, context: ContextTypes.DEFAULT_TYPE):
    LoggingCazzi.log_user_activity(update, "ABBANDONA_ANNULLA", f"Messaggio: {update.message.text[:50]}")
    mess=await update.message.reply_text("Operazione annullata.", reply_markup=ReplyKeyboardRemove()) # Fai sparire la tastiera
    context.user_data["eliminare"].append(update.message.message_id)
    context.user_data["eliminare"].append(mess.message_id)
    context.user_data["eliminare"].append(context.user_data["messaggio"])

    # Elimina messaggi

    await context.bot.delete_messages(chat_id=update.message.chat_id, message_ids=context.user_data["eliminare"])
    context.user_data.clear()
    logging.info("Operazione annullata.")
    logging.info("-"*50)
    return ConversationHandler.END



# /sudo
async def sudo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando per admin per la gestione"""
    if(update.message):
        LoggingCazzi.log_user_activity(update, "SUDO_COMMAND")
        # ADMIN ONLY
        if(await HelpersCazzi.check_admin(update, cursor)):
            context.user_data["eliminare"]=[update.message.message_id]
            # Menu delle opzioni disponibili
            keyboard=[['Rimuovere una cacca', 'Aggiungere una cacca'],['Declassare admin', 'Nominare admin'], ['Rimuovere un cagatore', 'Annulla']]

            mess=await update.message.reply_text(
                "Cosa vuoi fare? (/annulla in ogni momento per annullare)",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard, one_time_keyboard=True, resize_keyboard=True, selective=True
                ),
            )
            context.user_data["eliminare"].append(mess.message_id)
            logging.info("Chiesto cosa l'admin vuol fare.")
            return SUDO_MENU
        else:
            logging.warning(f"L'utente {update.effective_user.id} non è un admin")
            logging.info("-"*50)
            return ConversationHandler.END


# Rimuovi la cacca di qualcun altro
async def sudo_rmcacca(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if(update.message):
        LoggingCazzi.log_user_activity(update, "SUDO_RMCACCA", f"Messaggio: {update.message.text[:50]}...")
        context.user_data["eliminare"].append(update.message.message_id)
        mess=await update.message.reply_text(
            "Inserire il nome del cagatore per cui vuoi togliere una cacca.", reply_markup=ReplyKeyboardRemove() # Fai sparire la tastiera
        )
        context.user_data["eliminare"].append(mess.message_id)
        logging.info("Chiesto l'utente a cui rimuovere una cacca.")
        return SUDO_RMCACCA_SCEGLI

# Scegli la cacca, se il cagatore con quel nome esiste
async def sudo_rmcacca_scegli(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if(update.message):
        LoggingCazzi.log_user_activity(update, "SUDO_RMCACCA_SCEGLI", f"Messaggio: {update.message.text[:50]}...")
        context.user_data["eliminare"].append(update.message.message_id)
        nome=update.message.text
        if(cursor.execute("select nome from cagatori where nome=?", (nome,)).fetchone()):
            ultime_cacche=cursor.execute("select nome, giorno, ora, citta, stato, altitudine, velocita, messaggio from cacche where nome=?", (nome,)).fetchall()
            if(ultime_cacche):
                messaggio=f"Le cacche recenti di {nome} sono:\n\n"
                i=1
                for cacca in ultime_cacche:
                    messaggio+=f"{i}: {cacca[0:7]} \n"
                    i=i+1
                messaggio+="\nInserire il numero della cacca da cancellare, /annulla per annullare.\n"
                mess=await update.message.reply_text(messaggio)
                logging.info(f"Mandato messaggio con le cacche recenti di {nome}.")
                context.user_data["cacche"]=ultime_cacche
                context.user_data["eliminare"].append(mess.message_id)
                return SUDO_RMCACCA_RIMUOVI
            else:
                await update.message.reply_text(f"{nome} non ha inserito cacche di recente.")
                logging.info(f"Non ci sono cacche di {nome} nella tabella cacche.")
                logging.info("-"*50)
                return ConversationHandler.END
        else:
            # Errore
            mess=await update.message.reply_text(
                "Non c'è un cagatore con questo nome. Riprova."
            )
            context.user_data["eliminare"].append(mess.message_id)
            logging.warning("Non c'è un cagatore con questo nome.")
            return SUDO_RMCACCA_SCEGLI

# Procede a rimuovere la cacca
async def sudo_rmcacca_rimuovi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if(update.message):
        LoggingCazzi.log_user_activity(update, "SUDO_RMCACCA_RIMUOVI", f"Messaggio: {update.message.text[:50]}...")
        context.user_data["eliminare"].append(update.message.message_id)
        i=int(update.message.text)-1
        cacche=context.user_data["cacche"]
        if(i>=0 and i<len(cacche)):
            messid=int(cacche[i][7])
            cursor.execute("delete from cacche where messaggio=?", (messid,))
            conn.commit()
            mess=await update.message.reply_text("Cacca rimossa con successo.")
            context.user_data["eliminare"].append(mess.message_id)
            context.user_data["eliminare"].append(messid) # Rinuove messaggio con la cacca
            await context.bot.delete_messages(chat_id=update.message.chat_id, message_ids=context.user_data["eliminare"])
            context.user_data.clear() # Pulisce i dati raccolti
            logging.info(f"Cacca rimossa con successo: {cacche[i]}")
            logging.info("-"*50)
            return ConversationHandler.END
        else:
            logging.warning("Numero inserito non valido.")
            mess=await update.message.reply_text("Il numero inserito non è valido, riprova.")
            context.user_data["eliminare"].append(mess.message_id)
            return SUDO_RMCACCA_RIMUOVI


# Aggiungi cacca per un cagatore.
async def sudo_addcacca(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if(update.message):
        LoggingCazzi.log_user_activity(update, "SUDO_ADDCACCA", f"Messaggio: {update.message.text[:50]}...")
        context.user_data["eliminare"].append(update.message.message_id)
        mess=await update.message.reply_text(
            "Inserire il nome del cagatore per cui vuoi inserire la cacca.", reply_markup=ReplyKeyboardRemove() # Fai sparire la tastiera
        )
        context.user_data["eliminare"].append(mess.message_id)
        logging.info("Chiesto l'utente a cui aggiungere una cacca.")
        return SUDO_ADDCACCA_MESSAGGIO

# Scrivi il messaggio che il cagatore avrebbe docuto scrivere.
async def sudo_addcacca_messaggio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if(update.message):
        LoggingCazzi.log_user_activity(update, "SUDO_ADDCACCA_MESSAGGIO", f"Messaggio: {update.message.text[:50]}...")
        context.user_data["eliminare"].append(update.message.message_id)

        # Se abbiamo scelto 'No' nella conferma allora torniamo qui, ma il cagatore è già stato inserito. Quindi vogliamo leggere il nome solo se non abbiamo già i dati.
        if(not "dati" in context.user_data): 
            # Controlla che il cagatore esista
            nome=update.message.text
            # Prende i dati del cagatore, che ci serviranno più tardi
            dati=cursor.execute("select nome, fuso, citta, stato from cagatori where nome=?", (nome,)).fetchone()
            if(dati):
                logging.info(f"Dati di {nome} acquisiti con successo.")
                context.user_data["dati"]=dati
            else:
                # Errore
                mess=await update.message.reply_text(
                    "Non c'è un cagatore con questo nome. Riprova."
                )
                context.user_data["eliminare"].append(mess.message_id)
                logging.warning("Non c'è un cagatore con questo nome.")
                return SUDO_ADDCACCA_MESSAGGIO

        mess=await update.message.reply_text(
            "Inserire il messaggio di cacca che il cagatore dovrebbe scrivere (senza 💩 iniziale)."
        )
        context.user_data["eliminare"].append(mess.id)
        logging.info("Chiesto messaggio di cacca.")
        return SUDO_ADDCACCA_CONFERMA

# Ho copia-incollato tutto dall'handling dei messaggi di cacca e modificato qualcosina.
async def sudo_addcacca_conferma(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if(update.message):
        LoggingCazzi.log_user_activity(update, "SUDO_ADDCACCA_CONFERMA", f"Messaggio: {update.message.text[:50]}...")
        context.user_data["eliminare"].append(update.message.message_id)

        # Mi salvo il messaggio di cacca che ci servirà dopo.
        user_message = update.message.text
        context.user_data["mess_cacca"]=user_message

        # Ripeschiamo i dati
        [chi, fuso, citta, stato]=context.user_data["dati"]

        # Per controllare se i dati devono essere aggiornati nel database.
        flag = bool(False)

        # Le keywords sono ora case insensitive
        
        if(re.search("altitudine: ", user_message, re.IGNORECASE)):
            value = re.split("altitudine: ", user_message, flags=re.IGNORECASE)[1]
            altitudine=re.split(r'[,;\n]+',value)[0]
            if(not altitudine.isdigit()):
                err = await update.message.reply_text("Errore: altitudine non valida. Riprova.")
                context.user_data["eliminare"].append(err.message_id)
                logging.warning("Errore: altitudine non valida.")
                return SUDO_ADDCACCA_CONFERMA
        else:
            altitudine=""
        if(re.search("velocità: ", user_message, re.IGNORECASE)):
            value = re.split("velocità: ", user_message, flags=re.IGNORECASE)[1]
            velocita=re.split(r'[,;\n]+',value)[0]
            if(not velocita.isdigit()):
                err = await update.message.reply_text("Errore: velocità non valida. Riprova.")
                context.user_data["eliminare"].append(err.message_id)
                logging.warning("Errore: velocità non valida.")
                return SUDO_ADDCACCA_CONFERMA
        else:
            velocita=""

        # Dati potenzialmente da modificare nel database
        if(re.search("città: ", user_message, re.IGNORECASE)):
            flag = bool(True)
            value = re.split("città: ", user_message, flags=re.IGNORECASE)[1]
            citta=re.split(r'[,;\n]+',value)[0]
            if(not citta.isalpha()):
                err = await update.message.reply_text("Errore: città non valida (sono accettate solo lettere). Riprova.")
                context.user_data["eliminare"].append(err.message_id)
                logging.warning("Errore: città contiene caratteri che non sono lettere. Riprova.")
                return SUDO_ADDCACCA_CONFERMA
        if(re.search("fuso: ", user_message, re.IGNORECASE)):
            flag = bool(True)
            value = re.split("fuso: ", user_message, flags=re.IGNORECASE)[1]
            fuso=re.split(r'[,;\n]+',value)[0]
            if(not HelpersCazzi.is_integer(fuso)):
                err = await update.message.reply_text("Errore: fuso non valido (deve essere un intero). Riprova.")
                context.user_data["eliminare"].append(err.message_id)
                logging.warning("Errore: fuso non valido.")
                return SUDO_ADDCACCA_CONFERMA
            else:
                fuso=int(fuso)
        if(re.search("stato: ", user_message, re.IGNORECASE)):
            flag = bool(True)
            value = re.split("stato: ", user_message, flags=re.IGNORECASE)[1]
            stato=re.split(r'[,;\n]+',value)[0]
            if(not stato.isalpha()):
                err = await update.message.reply_text("Errore: stato non valido (sono accettate solo lettere). Riprova.")
                context.user_data["eliminare"].append(err.message_id)
                logging.warning("Errore: stato contiene caratteri che non sono lettere.")
                return SUDO_ADDCACCA_CONFERMA

        # giorno e ora

        # assumo che nessuno metta il giorno senza mettere l'ora
        if(re.search("or[ae]: ", user_message, re.IGNORECASE)):
            value = re.split("or[ae]: ", user_message, flags=re.IGNORECASE)[1]
            ora=HelpersCazzi.valid_hour(re.split(r'[,;\n]+',value)[0])
            if(not ora):
                err = await update.message.reply_text("Errore: ora non valida. Riprova.")
                context.user_data["eliminare"].append(err.message_id)
                logging.warning("Errore: ora non valida.")
                return SUDO_ADDCACCA_CONFERMA

            if(re.search("giorno: ", user_message, re.IGNORECASE)):
                value = re.split("giorno: ", user_message, flags=re.IGNORECASE)[1]
                giorno=HelpersCazzi.valid_day(re.split(r'[,;\n]+',value)[0])
                if(not giorno):
                    err = await update.message.reply_text("Errore: giorno non valido. Riprova.")
                    context.user_data["eliminare"].append(err.message_id)
                    logging.warning("Errore: giorno non valido.")
                    return SUDO_ADDCACCA_CONFERMA
            else:
                # Per assicurarsi che il giorno sia localizzato.
                data=update.message.date + timedelta(hours=fuso)
                giorno = data.date().strftime('%d/%m/%y')
        else:
            # Fa lo shift in base al fuso orario
            data=update.message.date + timedelta(hours=fuso)
            giorno=data.date().strftime('%d/%m/%y')
            ora=data.time().strftime('%H.%M')

        if(flag):
            cursor.execute("update cagatori set citta=?, stato=?, fuso=? where nome=?", (citta, stato, fuso, chi))

        # Tastiera con le opzioni
        keyboard=[["Sì", "No"]]

        # Chiede conferma
        ans = await update.message.reply_text(
            f"Verranno inseriti i seguenti dati per {chi}:\n\nGiorno: {giorno}\nOra: {ora}\nCittà: {citta}\nStato: {stato}\nAltitudine: {altitudine}\nVelocità: {velocita}\n\nSono corretti?",
            reply_markup=ReplyKeyboardMarkup(
                keyboard, one_time_keyboard=True, resize_keyboard=True, selective=True
            ),
        )
        context.user_data["roba"]=[chi, giorno, ora, citta, stato, altitudine, velocita]
        context.user_data["aggiornare"]=flag
        context.user_data["fuso"]=fuso
        context.user_data["eliminare"].append(ans.message_id)
        logging.info("Chiesta conferma.")
        return SUDO_ADDCACCA_SI

# Inserisce la cacca se tutto è ok.
async def sudo_addcacca_si(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if(update.message):
        LoggingCazzi.log_user_activity(update, "SUDO_ADDCACCA_SI", f"Messaggio: {update.message.text[:50]}...")
        context.user_data["eliminare"].append(update.message.message_id)

        # Scrive il messaggio come se l'avesse scritto l'utente, e sarà l'unico messaggio che resta alla fine
        ans = await context.bot.send_message(chat_id=update.message.chat_id, text=f"💩 ({context.user_data["dati"][0]})\n{context.user_data["mess_cacca"]}", reply_markup=ReplyKeyboardRemove())

        roba=context.user_data["roba"]

        cursor.execute("insert into cacche (nome, giorno, ora, citta, stato, altitudine, velocita, messaggio) values (?, ?, ?, ?, ?, ?, ?, ?)", (roba[0], roba[1], roba[2], roba[3], roba[4], roba[5], roba[6], ans.message_id))
        conn.commit()
        logging.info(f"Roba da inserire: {roba}")

        # Cancella i messaggi precedenti
        await context.bot.delete_messages(chat_id=update.message.chat_id, message_ids=context.user_data["eliminare"])

        # Se tutto va bene, reagire con "👍"

        await context.bot.set_message_reaction(
            chat_id=update.message.chat_id,
            message_id=ans.message_id,
            reaction=[ReactionTypeEmoji("👍")]
        )
        logging.info("Dati cacca salvati.")
        if(context.user_data["aggiornare"]):
            logging.info(f"Aggiornati i dati di {roba[0]}: Città: {roba[3]}, Stato: {roba[4]}, Fuso: {context.user_data["fuso"]}")

        context.user_data.clear()
        logging.info("-"*50)
        return ConversationHandler.END


# Nomina un cagatore admin
async def sudo_addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if(update.message):
        LoggingCazzi.log_user_activity(update, "SUDO_ADDADMIN", f"Messaggio: {update.message.text[:50]}...")
        context.user_data["eliminare"].append(update.message.message_id)
        mess=await update.message.reply_text(
            "Inserire il nome del cagatore che vuoi rendere admin.", reply_markup=ReplyKeyboardRemove() # Fai sparire la tastiera
        )
        context.user_data["eliminare"].append(mess.message_id)
        logging.info("Chiesto il cagatore da rendere admin.")
        return SUDO_ADDADMIN_PROMUOVI

# Rende il cagatore admin
async def sudo_addadmin_promuovi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if(update.message):
        LoggingCazzi.log_user_activity(update, "SUDO_ADDADMIN_PROMUOVI", f"Messaggio: {update.message.text[:50]}...")
        context.user_data["eliminare"].append(update.message.message_id)
        nome=update.message.text
        if(cursor.execute("select nome from cagatori where nome=?", (nome,)).fetchone()):
            cursor.execute("update cagatori set admin=1 where nome=?", (nome,))
            conn.commit()
            await context.bot.send_message(chat_id=update.message.chat_id, text=f"{nome} è ora un admin.")
            logging.info(f"{nome} è ora un admin.")
            await context.bot.delete_messages(chat_id=update.message.chat_id, message_ids=context.user_data["eliminare"])
        else:
            await update.message.reply_text("Non esiste un cagatore con questo nome.")
            logging.warning(f"Non esiste un cagatore con questo nome.")
        context.user_data.clear() # Pulisce i dati raccolti
        logging.info("-"*50)
        return ConversationHandler.END


# Rimuovi qualcuno dal ruolo di admin
async def sudo_rmadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if(update.message):
        LoggingCazzi.log_user_activity(update, "SUDO_RMADMIN", f"Messaggio: {update.message.text[:50]}...")
        context.user_data["eliminare"].append(update.message.message_id)
        mess=await update.message.reply_text(
            "Inserire il nome dell'admin a cui vuoi togliere i poteri di admin.", reply_markup=ReplyKeyboardRemove() # Fai sparire la tastiera
        )
        context.user_data["eliminare"].append(mess.message_id)
        logging.info("Chiesto l'admin da rimuovere")
        return SUDO_RMADMIN_DECLASSA

# Toglie i poteri di admin
async def sudo_rmadmin_declassa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if(update.message):
        LoggingCazzi.log_user_activity(update, "SUDO_RMADMIN_DECLASSA", f"Messaggio: {update.message.text[:50]}...")
        context.user_data["eliminare"].append(update.message.message_id)
        nome=update.message.text
        if(cursor.execute("select nome from cagatori where nome=? and admin=1", (nome,)).fetchone()):
            cursor.execute("update cagatori set admin=0 where nome=?", (nome,))
            conn.commit()
            await context.bot.send_message(chat_id=update.message.chat_id, text=f"{nome} ora non è più un admin.")
            logging.info(f"{nome} ora non è più un admin.")
            await context.bot.delete_messages(chat_id=update.message.chat_id, message_ids=context.user_data["eliminare"])
        else:
            await update.message.reply_text("Non esiste un admin con questo nome.")
            logging.warning(f"Non esiste un admin con questo nome.")
        context.user_data.clear() # Pulisce i dati raccolti
        logging.info("-"*50)
        return ConversationHandler.END
    

# Rimuove un cagatore
async def sudo_rmuser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if(update.message):
        LoggingCazzi.log_user_activity(update, "SUDO_RMUSER", f"Messaggio: {update.message.text[:50]}...")
        context.user_data["eliminare"].append(update.message.message_id)
        mess=await update.message.reply_text(
            "Inserire il nome del cagatore che vuoi rimuovere.", reply_markup=ReplyKeyboardRemove() # Fai sparire la tastiera
        )
        context.user_data["eliminare"].append(mess.message_id)
        logging.info("Chiesto il cagatore da rimuovere.")
        return SUDO_RMUSER_RIMUOVI

# Procede a rimuovere il cagatore
async def sudo_rmuser_rimuovi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if(update.message):
        LoggingCazzi.log_user_activity(update, "SUDO_RMUSER", f"Messaggio: {update.message.text[:50]}...")
        context.user_data["eliminare"].append(update.message.message_id)
        nome=update.message.text
        if(cursor.execute("select nome from cagatori where nome=?", (nome,)).fetchone()):
            cursor.execute("delete from cagatori where nome=?", (nome,))
            conn.commit()
            await context.bot.send_message(chat_id=update.message.chat_id, text=f"{nome} ora non è più un cagatore.")
            logging.info(f"{nome} ora non è più un cagatore.")
            await context.bot.delete_messages(chat_id=update.message.chat_id, message_ids=context.user_data["eliminare"])
        else:
            await update.message.reply_text("Non esiste un cagatore con questo nome.")
            logging.warning(f"Non esiste un cagatore con questo nome.")
        context.user_data.clear() # Pulisce i dati raccolti
        logging.info("-"*50)
        return ConversationHandler.END


# /annulla
async def sudo_annulla(update: Update, context: ContextTypes.DEFAULT_TYPE):
    LoggingCazzi.log_user_activity(update, "SUDO_ANNULLA", f"Messaggio: {update.message.text[:50]}")
    mess=await update.message.reply_text("Operazione annullata.", reply_markup=ReplyKeyboardRemove()) # Fai sparire la tastiera
    conn.rollback() # Annulla update al database (serve nel caso di una cacca annullata).
    context.user_data["eliminare"].append(update.message.message_id)
    context.user_data["eliminare"].append(mess.message_id)

    # Elimina messaggi

    await context.bot.delete_messages(chat_id=update.message.chat_id, message_ids=context.user_data["eliminare"])
    context.user_data.clear()
    logging.info("Operazione annullata.")
    logging.info("-"*50)
    return ConversationHandler.END


async def annulla(update: Update, context: ContextTypes.DEFAULT_TYPE):
    LoggingCazzi.log_user_activity(update, "ANNULLA", f"Messaggio: {update.message.text[:50]}")
    mess=await update.message.reply_text("Operazione annullata.", reply_markup=ReplyKeyboardRemove()) # Fai sparire la tastiera
    conn.rollback() # Annulla update al database
    context.user_data.clear()
    logging.info("Operazione annullata.")
    logging.info("-"*50)
    return ConversationHandler.END

# Handling dei segnali per far funzionare systemd come Ctrl+C
def shutdown(signum, frame):
    sys.exit(0)

signal.signal(signal.SIGTERM, shutdown)
signal.signal(signal.SIGINT, shutdown)


def main():
    """Fai partire il bot."""
    try:
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

# help - Visualizza un messaggio di aiuto
# comandi - Manda una lista dei comandi
# join - Diventa un cagatore
# sintassi - Visualizza sintassi dei messaggi di cacca
# mieidati - Visualizza i propri dati
# setdato - Aggiorna un proprio dato
# rmcacca - Visualizza e rimuovi le ultime cacche inserite
# cagatori - Lista tutti i cagatori
# abbandona - Smetti di essere un cagatore
# annulla - Annulla il comando corrente
# sudo - Comando di gestione (solo per admin)


        # Handler per i comandi

        application.add_handler(ConversationHandler(
            entry_points=[MessageHandler(filters.Regex("^💩"), cacca_handle),
                          CommandHandler("join", join_command),
                          CommandHandler("setdato", setdato_command),
                          CommandHandler("rmcacca", rmcacca_command),
                          CommandHandler("abbandona", abbandona_command),
                          CommandHandler("sudo", sudo_command)],
            states={
                CACCA_CONFERMA: [MessageHandler(filters.Regex("(?i)^(sì|si|y|s)$"), cacca_conferma), MessageHandler(filters.TEXT, cacca_annulla)],

                JOIN_NOME: [MessageHandler(filters.TEXT & ~filters.COMMAND, join_nome), MessageHandler(filters.COMMAND, join_annulla)],
                JOIN_FUSO: [MessageHandler(filters.TEXT & ~filters.COMMAND, join_fuso), MessageHandler(filters.COMMAND, join_annulla)],
                JOIN_CITTA: [MessageHandler(filters.TEXT & ~filters.COMMAND, join_citta), MessageHandler(filters.COMMAND, join_annulla)],
                JOIN_STATO: [MessageHandler(filters.TEXT & ~filters.COMMAND, join_stato), MessageHandler(filters.COMMAND, join_annulla)],

                SETDATO_DATO: [MessageHandler(filters.Regex("^(Fuso|Città|Stato)$"), setdato_dato), MessageHandler(filters.TEXT, setdato_annulla)],
                SETDATO_CAMBIA: [MessageHandler(filters.TEXT & ~filters.COMMAND, setdato_cambia), MessageHandler(filters.COMMAND, setdato_annulla)],

                RMCACCA_RIMUOVI: [MessageHandler(filters.Regex("^[0-9]*$"), rmcacca_rimuovi), MessageHandler(filters.TEXT, rmcacca_annulla)],

                ABBANDONA_SI: [MessageHandler(filters.Regex("^Sì$"), abbandona_si), MessageHandler(filters.TEXT, abbandona_annulla)],

                SUDO_MENU: [MessageHandler(filters.Regex("^Rimuovere una cacca$"), sudo_rmcacca),
                            MessageHandler(filters.Regex("^Aggiungere una cacca$"), sudo_addcacca),
                            MessageHandler(filters.Regex("^Declassare admin$"), sudo_rmadmin),
                            MessageHandler(filters.Regex("^Nominare admin$"), sudo_addadmin),
                            MessageHandler(filters.Regex("^Rimuovere un cagatore$"), sudo_rmuser),
                            MessageHandler(filters.TEXT, sudo_annulla)],

                SUDO_RMCACCA_SCEGLI: [MessageHandler(filters.TEXT & ~filters.COMMAND, sudo_rmcacca_scegli), MessageHandler(filters.TEXT, sudo_annulla)],
                SUDO_RMCACCA_RIMUOVI: [MessageHandler(filters.Regex("^[0-9]*$"), sudo_rmcacca_rimuovi), MessageHandler(filters.TEXT, sudo_annulla)],

                SUDO_ADDCACCA_MESSAGGIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, sudo_addcacca_messaggio), MessageHandler(filters.COMMAND, sudo_annulla)],
                SUDO_ADDCACCA_CONFERMA: [MessageHandler(filters.TEXT & ~filters.COMMAND, sudo_addcacca_conferma), MessageHandler(filters.COMMAND, sudo_annulla)],
                SUDO_ADDCACCA_SI: [MessageHandler(filters.Regex("(?i)^(sì|si|y|s)$"), sudo_addcacca_si), MessageHandler(filters.TEXT & ~filters.COMMAND, sudo_addcacca_messaggio), MessageHandler(filters.COMMAND, sudo_annulla)],

                SUDO_RMADMIN_DECLASSA: [MessageHandler(filters.TEXT & ~filters.COMMAND, sudo_rmadmin_declassa), MessageHandler(filters.COMMAND, sudo_annulla)],

                SUDO_ADDADMIN_PROMUOVI: [MessageHandler(filters.TEXT & ~filters.COMMAND, sudo_addadmin_promuovi), MessageHandler(filters.COMMAND, sudo_annulla)],

                SUDO_RMUSER_RIMUOVI: [MessageHandler(filters.TEXT & ~filters.COMMAND, sudo_rmuser_rimuovi), MessageHandler(filters.COMMAND, sudo_annulla)],

            },
            fallbacks=[MessageHandler(filters.TEXT, annulla)],
            allow_reentry=False
        ))

        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("comandi", comandi_command))
        application.add_handler(CommandHandler("sintassi", sintassi_command))
        application.add_handler(CommandHandler("mieidati", mieidati_command))
        application.add_handler(CommandHandler("cagatori", cagatori_command))

        # Fa partire il bot
        logging.info("Bot partito...")
        application.run_polling()
    except Exception as e:
        logging.critical(f"Errore: bot non partito: {e}", exc_info=True)
        raise RuntimeError(f"Errore: bot non partito: {e}")

if __name__ == '__main__':

    # Memorizza le cacche e le invia ogni tot in blocco
    scheduler = BackgroundScheduler()
    scheduler.add_job(sheets_handler.inserisci_cacche, "interval", minutes=FREQUENZA_CHECK)
    scheduler.start()

    # Fa partire il loop
    main()

    logging.info("Bot fermato.")
