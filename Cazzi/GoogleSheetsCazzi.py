import os
import logging
from google.oauth2.service_account import Credentials
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
            
            scopes = [
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive"
            ]
            creds = Credentials.from_service_account_file(self.creds_file, scopes=scopes)
            self.client = gspread.authorize(creds)
            self.sheet = self.client.open_by_url(self.spreadsheet_url).worksheet(WORKSHEET_NAME)
            self.logger.info("Client di Google sheets inizializzato")
        except Exception as e:
            self.logger.error(f"Errore nell'inizializzazione del client di Google Sheets: {e}", exc_info=True)
            raise
    
    # Un dirty trick clamoroso
    def keep_alive(self):
        """Fa una richiesta per tenere in vita la connessione"""
        try:
            _=self.sheet.acell("A1").value
        except:
            self.logger.warning("Connessione allo spreadsheet persa, probabilmente ora è ristabilita.")
            pass

    def append_data(self, data):
        """Aggiungi dati al Google Sheets"""
        try:

            self.sheet.append_row(data, table_range='A1', value_input_option="USER_ENTERED")
            self.logger.info(f"Dati aggiunti: {data}")
            return True
        except Exception as e:
            self.logger.error(f"Errore nell'aggiungere dati: {e}", exc_info=True)
            return False
