import os
import logging
import gspread

from Cazzi.CostantiCazzi import WORKSHEET_NAME

class GoogleSheetsHandler:
    def __init__(self, creds_file, spreadsheet_url):
        self.creds_file = creds_file
        self.spreadsheet_url = spreadsheet_url
        self.client = None
        self.sheet = None
        self.logger = logging.getLogger(__name__)
        self._setup_client()

    def _setup_client(self):
        """Initializza il client di Google Sheets"""
        try:
            # Controlla che il file con le credenziali esista
            if not os.path.exists(self.creds_file):
                error_msg = f"File con le credenziali di Google Sheets non trovato: {self.creds_file}"
                self.logger.error(error_msg)
                raise FileNotFoundError(error_msg)
            
            self.client = gspread.service_account(filename=self.creds_file)
            self.sheet = self.client.open_by_url(self.spreadsheet_url).worksheet(WORKSHEET_NAME)

            self.logger.info("Client di Google sheets inizializzato")
        except Exception as e:
            self.logger.error(f"Errore nell'inizializzazione del client di Google Sheets: {e}", exc_info=True)
            raise

    def connect(self):
        """Crea la connessione allo spreadsheet"""
        try:
            self.client = gspread.service_account(filename=self.creds_file)
            self.sheet = self.client.open_by_url(self.spreadsheet_url).worksheet(WORKSHEET_NAME)
            self.logger.info("Connessione allo spreadsheet riuscita.")
        except Exception as e:
            self.logger.error(f"Connessione allo spreadsheet non riuscita: {e}", exc_info=True)
            raise

    # Un dirty trick clamoroso
    # def keep_alive(self):
    #     """Fa una richiesta per tenere in vita la connessione"""
    #     try:
    #         _=self.sheet.acell("A1").value
    #     except:
    #         self.logger.warning("Connessione allo spreadsheet persa, probabilmente ora è ristabilita.")
    #         pass

    def append_data(self, data):
        """Aggiungi dati al Google Sheets"""
        try:
            self.sheet.append_rows(data, table_range='A1', value_input_option="USER_ENTERED")
            self.logger.info("##### Dati aggiunti: #####")
            for cacca in data:
                self.logger.info(f"{cacca}")
            self.logger.info("##########################")
            return True
        except Exception as e:
            self.logger.error(f"Errore nell'aggiungere dati: {e}", exc_info=True)
            return False
