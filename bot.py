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
from Cazzi.CostantiCazzi import GOOGLE_SHEETS_CREDENTIALS_FILE, SPREADSHEET_URL, TELEGRAM_BOT_TOKEN

# Inizializza logging
LoggingCazzi.setup_logging()

# Connessione al database
# CREATE TABLE cagatori(
# user_id int NOT NULL,
# nome varchar(100) NOT NULL UNIQUE,
# fuso int NOT NULL,
# admin bool NOT NULL DEFAULT 0,
# citta varchar(100),
# stato varchar(100),
# PRIMARY KEY (user_id))
# CREATE UNIQUE INDEX idx_cagatori_user_id ON cagatori(user_id);
# CREATE UNIQUE INDEX idx_cagatori_nome ON cagatori(nome);

# CREATE TABLE cacche1(
# nome varchar(100) NOT NULL,
# giorno varchar(16) NOT NULL,
# ora varchar(10) NOT NULL,
# citta varchar(100),
# stato varchar(100),
# altitudine varchar(10),
# velocita varchar(10));

# CREATE TABLE cacche2(
# nome varchar(100) NOT NULL,
# giorno varchar(16) NOT NULL,
# ora varchar(10) NOT NULL,
# citta varchar(100),
# stato varchar(100),
# altitudine varchar(10),
# velocita varchar(10));

try:
    conn = sqlite3.connect('cagatori.db')
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS cacche1(nome varchar(100) NOT NULL, giorno varchar(16) NOT NULL, ora varchar(10) NOT NULL, citta varchar(100), stato varchar(100), altitudine varchar(10), velocita varchar(10));")
    cursor.execute("CREATE TABLE IF NOT EXISTS cacche2(nome varchar(100) NOT NULL, giorno varchar(16) NOT NULL, ora varchar(10) NOT NULL, citta varchar(100), stato varchar(100), altitudine varchar(10), velocita varchar(10));")
    logging.info("Connesso al database.")
except sqlite3.Error as e:
    logging.error(f"Errore nella connessione al database: {e}")
    raise

# Inizializza Google Sheets handler
sheets_handler = GoogleSheetsCazzi.GoogleSheetsHandler(GOOGLE_SHEETS_CREDENTIALS_FILE, SPREADSHEET_URL)

# # Liste delle cacche da inserire: vengono inserite prima in cacche1, poi dopo un po' vengono spostate in cacche2 e infine scritte sullo spreadsheet.
# cacche1=[]
# cacche2=[]

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
                        await update.message.reply_text("Errore: altitudine non valida.")
                        logging.error("Errore: altitudine non valida.")
                        raise
                else:
                    altitudine=""
                if(re.search("velocità: ", user_message, re.IGNORECASE)):
                    value = re.split("velocità: ", user_message, flags=re.IGNORECASE)[1]
                    velocita=re.split(r'[,;\n]+',value)[0]
                    if(not velocita.isdigit()):
                        await update.message.reply_text("Errore: velocità non valida.")
                        logging.error("Errore: velocità non valida.")
                        raise
                else:
                    velocita=""

                # Dati potenzialmente da modificare nel database
                if(re.search("città: ", user_message, re.IGNORECASE)):
                    flag = bool(True)
                    value = re.split("città: ", user_message, flags=re.IGNORECASE)[1]
                    citta=re.split(r'[,;\n]+',value)[0]
                    # Le stringhe non possono iniziare con =, altrimenti su google sheets è un casino
                    if(citta.startswith('=')):
                        await update.message.reply_text("Bel tentativo...")
                        logging.error("Errore: Città inizia con '='.")
                        raise
                if(re.search("fuso: ", user_message, re.IGNORECASE)):
                    flag = bool(True)
                    value = re.split("fuso: ", user_message, flags=re.IGNORECASE)[1]
                    fuso=re.split(r'[,;\n]+',value)[0]
                    if(not HelpersCazzi.is_integer(fuso)):
                        await update.message.reply_text("Errore: fuso non valido.")
                        logging.error(f"Errore: fuso non valido.")
                        raise
                    else:
                        fuso=int(fuso)
                if(re.search("stato: ", user_message, re.IGNORECASE)):
                    flag = bool(True)
                    value = re.split("stato: ", user_message, flags=re.IGNORECASE)[1]
                    stato=re.split(r'[,;\n]+',value)[0]
                    # Le stringhe non possono iniziare con =, altrimenti su google sheets è un casino
                    if(stato.startswith('=')):
                        await update.message.reply_text("Bel tentativo...")
                        logging.error("Errore: Stato inizia con '='.")
                        raise

                # giorno e ora

                # assumo che nessuno metta il giorno senza mettere l'ora
                if(re.search("or[ae]: ", user_message, re.IGNORECASE)):
                    value = re.split("or[ae]: ", user_message, flags=re.IGNORECASE)[1]
                    ora=HelpersCazzi.valid_hour(re.split(r'[,;\n]+',value)[0])
                    if(not ora):
                        await update.message.reply_text("Errore: ora non valida.")
                        logging.error("Errore: ora non valida.")
                        raise

                    if(re.search("giorno: ", user_message, re.IGNORECASE)):
                        value = re.split("giorno: ", user_message, flags=re.IGNORECASE)[1]
                        giorno=HelpersCazzi.valid_day(re.split(r'[,;\n]+',value)[0])
                        if(not giorno):
                            await update.message.reply_text("Errore: giorno non valido.")
                            logging.error("Errore: giorno non valido.")
                            raise
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
                    try:
                        cursor.execute("update cagatori set citta=?, stato=?, fuso=? where user_id=?", (citta, stato, fuso, user_id))
                    except sqlite3.Error as e:
                        await update.message.reply_text("Errore: dati non validi.")
                        logging.error(f"Dati inseriti non validi: {e}")
                        raise

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
                return 1
        logging.info("-"*50)
    return ConversationHandler.END

# Inserisce la cacca se l'utente conferma
async def cacca_conferma(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if(update.message):
        LoggingCazzi.log_user_activity(update, "CACCA_SI")
        ans = await context.bot.send_message(chat_id=update.message.chat_id, text="Inserisco la cacca...", reply_markup=ReplyKeyboardRemove())

        roba=context.user_data["roba"]
        cursor.execute("insert into cacche1 values (?, ?, ?, ?, ?, ?, ?)", (roba[0], roba[1], roba[2], roba[3], roba[4], roba[5], roba[6]))
        conn.commit()
        # cacche1.append(roba)
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
/sintassi - Visualizza sintassi dei messaggi di cacca
/aggiungi - Aggiungi cagatore (admin only)
/join - Diventa un cagatore
/rimuovi - Rimuovi cagatore (admin only)
/abbandona - Smetti di essere un cagatore
/setdato - Aggiorna un proprio dato
/rmcacca - Visualizza e rimuovi le ultime cacche inserite
/cagatori - Lista tutti i cagatori
/addadmin - Nomina admin (admin only)
/rmadmin - Rimuovi admin (admin only)
/mieidati - Visualizza i propri dati
/annulla - Annulla il comando corrente
        """)
            logging.info("Lista dei comandi mandata.")
        logging.info("-"*50)


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
Città: Sale Marasino
StAtO: Italia
altituDINE: 250
VELOcità: 340"
    """)

            logging.info("Mandato messaggio con la sintassi.")
        logging.info("-"*50)


# /aggiungi - Sintassi /aggiungi <user_id> <nome_spreadsheet> <fuso UTC> <città> <stato>
# C'è il bug degli spazi: non si possono mettere città, nomi o stati con uno spazio.
async def aggiungi_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Aggiungi cagatore"""
    if(update.message):
        LoggingCazzi.log_user_activity(update, "AGGIUNGI_COMMAND", f"args: {context.args}")
        # Solo admin
        if(await HelpersCazzi.check_admin(update, cursor)):
            # Controlla il numero di argomenti e che gli argomenti siano validi
            if (len(context.args)==5 and HelpersCazzi.is_integer(context.args[0]) and HelpersCazzi.is_integer(context.args[2]) and not context.args[1].startswith("=") and not context.args[3].startswith("=") and not context.args[4].startswith("=")):

                try:
                    # Inserisce i dati nel database
                    user_id=(int)(context.args[0])
                    nome=context.args[1]
                    fuso=(int)(context.args[2])
                    citta=context.args[3]
                    stato=context.args[4]
                    cursor.execute("insert into cagatori values (?, ?, ?, 0, ?, ?)", (user_id, nome, fuso, citta, stato)) # Inserisce come non_admin.
                    await update.message.reply_text(f"Aggiunto il cagatore {nome} con user_id {user_id}, fuso orario {fuso}, città {citta}, stato {stato}.")
                    logging.info(f"Aggiunto il cagatore {nome} con user_id {user_id}, fuso orario {fuso}, città {citta}, stato {stato}.")
                    conn.commit()
                except sqlite3.Error as e:
                    # Errore
                    await update.message.reply_text("Errore nell'inserimento nel database. Probabilmente c'è già un cagatore con lo stesso nome o user_id.")
                    logging.warning(f"Errore nell'inserimento nel database: {e}")

            else:
                # Spiega la sintassi
                await update.message.reply_text("Sintassi: /aggiungi <user_id> <nome_spreadsheet> <fuso UTC> <città> <stato>")
                logging.info("Spiegata la sintassi di /aggiungi")
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
            return 1
        else:
            # Termina la conversazione se non è nel gruppo o non è admin
            logging.info("-"*50)
            return ConversationHandler.END

# Registra il nome e chiede il fuso
async def join_nome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if(update.message):
        LoggingCazzi.log_user_activity(update, "JOIN_NOME", f"Messaggio: {update.message.text[:50]}")
        context.user_data["eliminare"].append(update.message.message_id)
        if(not update.message.text.startswith('=')): # Controlla il nome
            context.user_data["nome"]=update.message.text # Registra il nome
            mess=await update.message.reply_text( # Chiede il fuso
                "Inserisci il tuo fuso orario UTC (esempio: +1)."
            )
            context.user_data["eliminare"].append(mess.message_id)
            return 2
        else:
            logging.warning("Valore inizia con =")
            mess=await update.message.reply_text("Bel tentativo... Riprova.")
            context.user_data["eliminare"].append(mess.message_id)
            return 1 # Se non è valido, richiede il nome

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
            return 3
        else:
            logging.warning("Il fuso inserito non è valido.")
            mess=await update.message.reply_text("Errore: fuso non valido. Reinserire il fuso.")
            context.user_data["eliminare"].append(mess.message_id)
            return 2 # Se non è valido, richiede il fuso

# Regista la città e chiede lo stato
async def join_citta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if(update.message):
        context.user_data["eliminare"].append(update.message.message_id)
        LoggingCazzi.log_user_activity(update, "JOIN_CITTA", f"Messaggio: {update.message.text[:50]}")
        if(not update.message.text.startswith('=')): # Controlla la città
            context.user_data["citta"]=update.message.text # Registra la città
            mess=await update.message.reply_text( # Chiede lo stato
                "Inserisci il tuo stato."
            )
            context.user_data["eliminare"].append(mess.message_id)
            return 4
        else:
            logging.warning("Valore inizia con =")
            mess=await update.message.reply_text("Bel tentativo... Riprova.")
            context.user_data["eliminare"].append(mess.message_id)
            return 3 # Se non è valido, richiede la città

# Chiede lo stato, dopodiché se è valido prende tutti i dati e crea il nuovo cagatore
async def join_stato(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if(update.message):
        LoggingCazzi.log_user_activity(update, "JOIN_STATO", f"Messaggio: {update.message.text[:50]}")
        context.user_data["eliminare"].append(update.message.message_id)
        stato=update.message.text
        if(not stato.startswith('=')): # Controlla lo stato
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
            logging.warning("Bel tentativo...")
            mess=await update.message.reply_text("Bel tentativo... Riprova.")
            context.user_data["eliminare"].append(mess.message_id)
            return 4

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


# /rimuovi - Sintassi: /rimuovi <nome>
# C'è il bug degli spazi: non si può inserire un nome con degli spazi
async def rimuovi_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Rimuovi cagatore"""
    if(update.message):
        LoggingCazzi.log_user_activity(update, "RIMUOVI_COMMAND", f"args: {context.args}")
        # Solo admin
        if(await HelpersCazzi.check_admin(update, cursor)):
            # Controlla il numero di argomenti
            if (len(context.args)==1):
                # Tutto implementato con un bel database sql
                try:
                    nome=context.args[0]
                    # Controlla che il cagatore esista
                    if(cursor.execute("select nome from cagatori where nome=?", (nome,)).fetchone()):
                        # Rimuove dal database
                        cursor.execute("delete from cagatori where nome=?", (nome,))
                        await update.message.reply_text(f"Rimosso il cagatore {nome}.")
                        logging.info(f"Rimosso cagatore {nome}.")
                        conn.commit()
                    else:
                        # Errore
                        await update.message.reply_text(f"Il cagatore {nome} non esiste.")
                        logging.warning(f"Il cagatore {nome} non esiste.")
                except sqlite3.Error as e:
                    await update.message.reply_text(f"Errore nella rimozione.")
                    logging.error(f"Errore nella rimozione: {e}")
            else:
                await update.message.reply_text("Sintassi: /rimuovi <nome>")
                logging.info("Spiegata la sintassi di /rimuovi")
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
            return 1
        else:
            logging.info("-"*50)
            return ConversationHandler.END
    logging.info("-"*50)

# Se dice sì, abbandona
async def abbandona_si(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
            return 1
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
        return 2

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
                return 2

        elif dato == 'Città':
            if(not roba.startswith('=')): # Controlla validità
                # Aggiorna dato
                cursor.execute("update cagatori set citta=? where user_id=?", (roba, user_id))
                await update.message.reply_text(f"Città aggiornata a {roba}.")
                logging.info(f"Città aggiornata a {roba}.")
                conn.commit()
            else:
                # Errore
                logging.warning("Valore inizia con =")
                mess=await update.message.reply_text("Bel tentativo... Riprova.")
                context.user_data["eliminare"].append(mess.message_id)
                return 2

        else: # dato == 'Stato'
            if(not roba.startswith('=')): # Controlla validità
                # Aggiorna dato
                cursor.execute("update cagatori set stato=? where user_id=?", (roba, user_id))
                await update.message.reply_text(f"Stato aggiornato a {roba}.")
                logging.info(f"Stato aggiornato a {roba}.")
                conn.commit()
            else:
                # Errore
                logging.warning("Valore inizia con =")
                mess=await update.message.reply_text("Bel tentativo... Riprova.")
                context.user_data["eliminare"].append(mess.message_id)
                return 2
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
    if(update.message):
        LoggingCazzi.log_user_activity(update, "RMCACCA_COMMAND")
        if(await HelpersCazzi.check_cagatore_o_admin(update, cursor)):
            user_id=update.message.from_user.id
            nome=cursor.execute("select nome from cagatori where user_id=?", (user_id,)).fetchone()[0]
            ultime_cacche=cursor.execute("select * from cacche1 where nome=?", (nome,)).fetchall()
            ultime_cacche+=cursor.execute("select * from cacche2 where nome=?", (nome,)).fetchall()
            if(ultime_cacche):
                messaggio="Le tue cacche recenti sono:\n\n"
                i=1
                for cacca in ultime_cacche:
                    messaggio+=f"{i}: {cacca}\n"
                    i=i+1
                messaggio+="\nInserire il numero della cacca da cancellare, /annulla per annullare.\n"
                mess=await update.message.reply_text(messaggio)
                logging.info("Mandato messaggio con le cacche recenti.")
                context.user_data["cacche"]=ultime_cacche
                context.user_data["messaggio"]=update.message.message_id
                context.user_data["eliminare"]=[mess.message_id]
                return 1
            else:
                await update.message.reply_text("Non hai inserito cacche di recente.")
                logging.info("Non ci sono cacche dell'utente in cacca1 e cacca2.")
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
            cursor.execute("delete from cacche1 where nome=? and giorno=? and ora=? and citta=? and stato=? and altitudine=? and velocita=?", cacche[i])
            cursor.execute("delete from cacche2 where nome=? and giorno=? and ora=? and citta=? and stato=? and altitudine=? and velocita=?", cacche[i])
            conn.commit()
            mess=await update.message.reply_text("Cacca rimossa con successo.")
            context.user_data["eliminare"].append(mess.message_id)
            context.user_data["eliminare"].append(context.user_data["messaggio"])
            await context.bot.delete_messages(chat_id=update.message.chat_id, message_ids=context.user_data["eliminare"])
            context.user_data.clear() # Pulisce i dati raccolti
            logging.info(f"Cacca rimossa con successo: {cacche[i]}")
            logging.info("-"*50)
            return ConversationHandler.END
        else:
            mess=await update.message.reply_text("Il numero inserito non è valido, riprova.")
            context.user_data["eliminare"].append(mess.message_id)
            return 1

# /annulla
async def rmcacca_annulla(update: Update, context: ContextTypes.DEFAULT_TYPE):
    LoggingCazzi.log_user_activity(update, "RMCACCA_ANNULLA", f"Messaggio: {update.message.text[:50]}")
    mess=await update.message.reply_text("Operazione annullata.")
    context.user_data["eliminare"].append(update.message.message_id)
    context.user_data["eliminare"].append(mess.message_id)
    context.user_data["eliminare"].append(context.user_data["messaggio"])

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


# /addadmin - Sintassi: /addadmin <nome>
async def addadmin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Nomina admin"""
    if(update.message):
        LoggingCazzi.log_user_activity(update, "ADDADMIN_COMMAND", f"args: {context.args}")
        # Solo admin
        if(await HelpersCazzi.check_admin(update, cursor)):
            if(len(context.args)==1):
                try:
                    nome=context.args[0]
                    if(cursor.execute("select nome from cagatori where nome=?", (nome,)).fetchone()):
                        # Aggiunge admin
                        cursor.execute("update cagatori set admin=1 where nome=?", (nome,))
                        await update.message.reply_text(f"Ora {nome} è un admin.")
                        logging.info(f"Ora {nome} è un admin.")
                        conn.commit()
                    else:
                        # Nome non trovato
                        await update.message.reply_text(f"Il cagatore {nome} non esiste.")
                        logging.warning(f"Il cagatore {nome} non esiste.")
                except sqlite3.Error as e:
                    # Errore
                    await update.message.reply_text(f"Errore.")
                    logging.error(f"Errore. {e}")
            else:
                await update.message.reply_text("Sintassi: /addadmin <nome>")
                logging.info("Spiegata la sintassi di /addadmin")
        logging.info("-"*50)


# /rmadmin - Sintassi: /rmadmin <nome>
async def rmadmin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Rimuovi admin"""
    if(update.message):
        LoggingCazzi.log_user_activity(update, "RMADMIN_COMMAND", f"args: {context.args}")
        # Solo admin
        if(await HelpersCazzi.check_admin(update, cursor)):
            if(len(context.args)==1):
                try:
                    nome=context.args[0]
                    if(cursor.execute("select nome from cagatori where nome=?", (nome,)).fetchone()):
                        # Toglie admin
                        cursor.execute("update cagatori set admin=0 where nome=?", (nome,))
                        await update.message.reply_text(f"Ora {nome} non è un admin.")
                        logging.info(f"Ora {nome} non è un admin.")
                        conn.commit()
                    else:
                        # Nome non trovato
                        await update.message.reply_text(f"Il cagatore {nome} non esiste.")
                        logging.warning(f"Il cagatore {nome} non esiste.")
                except sqlite3.Error as e:
                    # Errore
                    await update.message.reply_text(f"Errore.")
                    logging.error(f"Errore: {e}")
            else:
                await update.message.reply_text("Sintassi: /rmadmin <nome>")
                logging.info("Spiegata la sintassi di /rmadmin")
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


def inserisci_cacche():
    """Inserisce le cacche nello spreadsheet e gestisce la coda"""
    # Fa la connessione al database per evitare casini.
    try:
        lconn = sqlite3.connect('cagatori.db')
        lcursor = lconn.cursor()
    except sqlite3.Error as e:
        logging.error(f"Errore nella connessione al database: {e}")
        raise

    # Inserisce cacche nello spreadsheet
    lcursor.execute("select * from cacche2")
    cacche2=lcursor.fetchall()
    problemi=False
    if(cacche2):
        sheets_handler.connect()
        if not sheets_handler.append_data(cacche2):
            problemi=True
            logging.error("Errore: cacche non aggiunte.")
        else:
            lcursor.execute("delete from cacche2")
            lconn.commit()
    else:
        logging.info("Non ci sono nuove cacche da aggiungere allo spreadsheet.")

    # Cambia i nomi delle tabelle in modo da gestire la coda.
    if not problemi:
        lcursor.execute("alter table cacche2 rename to bvfduw9ieafwbu")
        lcursor.execute("alter table cacche1 rename to cacche2")
        lcursor.execute("alter table bvfduw9ieafwbu rename to cacche1")


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
# sintassi - Visualizza sintassi dei messaggi di cacca
# aggiungi - Aggiungi cagatore (admin only)
# join - Diventa un cagatore
# rimuovi - Rimuovi cagatore (admin only)
# abbandona - Smetti di essere un cagatore
# setdato - Aggiorna un proprio dato
# rmcacca - Visualizza e rimuovi le ultime cacche inserite
# cagatori - Lista tutti i cagatori
# addadmin - Nomina admin (admin only)
# rmadmin - Rimuovi admin (admin only)
# mieidati - Visualizza i propri dati
# annulla - Annulla il comando corrente


        # Handler per i comandi
        application.add_handler(ConversationHandler(
            entry_points=[MessageHandler(filters.Regex("^💩"), cacca_handle)],
            states={
                1: [MessageHandler(filters.Regex("(?i)^(sì|si|y|s)$"), cacca_conferma)],
            },
            fallbacks=[MessageHandler(filters.TEXT, cacca_annulla)]
        ))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("comandi", comandi_command))
        application.add_handler(CommandHandler("sintassi", sintassi_command))
        application.add_handler(CommandHandler("aggiungi", aggiungi_command))
        application.add_handler(ConversationHandler(
            entry_points=[CommandHandler("join", join_command)],
            states={
                1: [MessageHandler(filters.TEXT & ~filters.COMMAND, join_nome)],
                2: [MessageHandler(filters.TEXT & ~filters.COMMAND, join_fuso)],
                3: [MessageHandler(filters.TEXT & ~filters.COMMAND, join_citta)],
                4: [MessageHandler(filters.TEXT & ~filters.COMMAND, join_stato)]
            },
            fallbacks=[CommandHandler("annulla", join_annulla)],
        ))
        application.add_handler(CommandHandler("rimuovi", rimuovi_command))
        application.add_handler(ConversationHandler(
            entry_points=[CommandHandler("abbandona", abbandona_command)],
            states={
                1: [MessageHandler(filters.Regex("^Sì$"), abbandona_si)]
            },
            fallbacks=[MessageHandler(filters.TEXT, abbandona_annulla)],
        ))
        application.add_handler(ConversationHandler(
            entry_points=[CommandHandler("rmcacca", rmcacca_command)],
            states={
                1: [MessageHandler(filters.Regex("^[0-9]*$"), rmcacca_rimuovi)]
            },
            fallbacks=[MessageHandler(filters.TEXT, rmcacca_annulla)],
        ))
        application.add_handler(ConversationHandler(
            entry_points=[CommandHandler("setdato", setdato_command)],
            states={
                1: [MessageHandler(filters.Regex("^(Fuso|Città|Stato)$"), setdato_dato), MessageHandler(filters.TEXT, setdato_annulla)],
                2: [MessageHandler(filters.TEXT & ~filters.COMMAND, setdato_cambia)]
            },
            fallbacks=[CommandHandler("annulla", setdato_annulla)]
        ))
        application.add_handler(CommandHandler("cagatori", cagatori_command))
        application.add_handler(CommandHandler("addadmin", addadmin_command))
        application.add_handler(CommandHandler("rmadmin", rmadmin_command))
        application.add_handler(CommandHandler("mieidati", mieidati_command))

        # Fa partire il bot
        logging.info("Bot partito...")
        application.run_polling()
    except Exception as e:
        logging.critical(f"Errore: bot non partito: {e}", exc_info=True)
        raise

if __name__ == '__main__':

    # Memorizza le cacche e le invia ogni ora in blocco
    scheduler = BackgroundScheduler()
    scheduler.add_job(inserisci_cacche, "interval", minutes=60) # Ogni 60 minuti
    scheduler.start()

    # Fa partire il loop
    main()

    # Inserisce le ultime cacche prima di terminare
    # logging.info("Inserisco le ultime cacche prima di uscire...")
    # inserisci_cacche()
    logging.info("Bot fermato.")
