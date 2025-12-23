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
            self.sheet = self.client.open_by_url(self.spreadsheet_url).worksheet(WORKSHEET_NAME)
            self.logger.info("Google Sheets client initialized successfully")
        except Exception as e:
            self.logger.error(f"Error setting up Google Sheets client: {e}", exc_info=True)
            raise
    
    def append_data(self, data):
        """Append data to the spreadsheet"""
        try:
            self.sheet.append_row(data, table_range='A1', value_input_option="USER_ENTERED")
            self.logger.info(f"Data appended to sheet: {data}")
            return True
        except Exception as e:
            self.logger.error(f"Error appending data: {e}", exc_info=True)
            return False
        
    # def remove_last_cacca(self, nome):
    #     """Rimuove l'ultima cacca"""
    #     try:
    #         row_count = get_populated_row_count(self.sheet)
    #         span = min(row_count, 10)
    #         first_row=row_count+1-span
    #         range_str = f"A{first_row}:A{row_count}"
    #         last_rows = self.sheet.get(range_str)
    #         print(row_count, range_str, last_rows)
    #         for i in range(span - 1, -1, -1):
    #             if (last_rows[i][0] == nome):
    #                 self.sheet.delete_rows(first_row + i)
    #                 return last_rows[i]
    #         self.logger.error(f"Errore. {last_rows}")
    #     except Exception as e:
    #         self.logger.error(f"Error removing data: {e}", exc_info=True)
    #         return False
    
    # def get_all_data(self):
    #     """Get all data from the spreadsheet"""
    #     try:
    #         data = self.sheet.get_all_records()
    #         self.logger.info(f"Retrieved {len(data)} records from spreadsheet")
    #         return data
    #     except Exception as e:
    #         self.logger.error(f"Error getting data: {e}", exc_info=True)
    #         return []
