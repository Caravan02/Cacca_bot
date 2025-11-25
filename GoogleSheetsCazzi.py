import os
import logging
from google.oauth2.service_account import Credentials
import gspread

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration from environment variables
WORKSHEET_NAME = os.getenv('WORKSHEET_NAME', 'Sheet1')

class GoogleSheetsHandler:
    def __init__(self, creds_file, spreadsheet_name):
        self.creds_file = creds_file
        self.spreadsheet_name = spreadsheet_name
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
            self.sheet = self.client.open(self.spreadsheet_name).worksheet(WORKSHEET_NAME)
            self.logger.info("Google Sheets client initialized successfully")
        except Exception as e:
            self.logger.error(f"Error setting up Google Sheets client: {e}", exc_info=True)
            raise
    
    def append_data(self, data):
        """Append data to the spreadsheet"""
        try:
            self.sheet.append_row(data, table_range='A1')
            self.logger.info(f"Data appended to sheet: {data}")
            return True
        except Exception as e:
            self.logger.error(f"Error appending data: {e}", exc_info=True)
            return False
    
    def get_all_data(self):
        """Get all data from the spreadsheet"""
        try:
            data = self.sheet.get_all_records()
            self.logger.info(f"Retrieved {len(data)} records from spreadsheet")
            return data
        except Exception as e:
            self.logger.error(f"Error getting data: {e}", exc_info=True)
            return []