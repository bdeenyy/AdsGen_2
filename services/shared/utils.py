"""
AdsGen 2.0 - Shared Utility Functions
"""

import logging
import json
import base64
import os
from typing import List, Dict, Any

import gspread
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)


class GoogleSheetsService:
    """Service for interacting with Google Sheets API."""

    def __init__(self, credentials_info: str):
        """
        Initialize the service with credentials.
        credentials_info can be a path to a JSON file, or a base64 encoded JSON string.
        """
        self.scopes = [
            "https://www.googleapis.com/auth/spreadsheets.readonly",
            "https://www.googleapis.com/auth/drive.readonly",
        ]
        
        try:
            if os.path.exists(credentials_info):
                # It's a file path
                self.gc = gspread.service_account(filename=credentials_info, scopes=self.scopes)
            else:
                # Try decoding as base64
                try:
                    creds_json = base64.b64decode(credentials_info).decode("utf-8")
                    creds_dict = json.loads(creds_json)
                    creds = Credentials.from_service_account_info(creds_dict, scopes=self.scopes)
                    self.gc = gspread.authorize(creds)
                except Exception:
                    # Try parsing as raw JSON
                    creds_dict = json.loads(credentials_info)
                    creds = Credentials.from_service_account_info(creds_dict, scopes=self.scopes)
                    self.gc = gspread.authorize(creds)
            
            logger.info("Google Sheets Service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Google Sheets Service: {e}")
            raise

    def get_sheet_data(self, spreadsheet_input: str, sheet_name: str = None) -> List[Dict[str, Any]]:
        """
        Fetch data from a Google Sheet and return as a list of dictionaries.
        spreadsheet_input: Can be a Spreadsheet ID or a full URL.
        """
        try:
            if spreadsheet_input.startswith("http"):
                sh = self.gc.open_by_url(spreadsheet_input)
            else:
                sh = self.gc.open_by_key(spreadsheet_input)
                
            if sheet_name:
                worksheet = sh.worksheet(sheet_name)
            else:
                worksheet = sh.get_worksheet(0)
            
            return worksheet.get_all_records()
        except Exception as e:
            logger.error(f"Error fetching Google Sheet data: {e}")
            raise

    def get_sheet_names(self, spreadsheet_input: str) -> List[str]:
        """
        Get list of sheet names from a spreadsheet.
        """
        try:
            if spreadsheet_input.startswith("http"):
                sh = self.gc.open_by_url(spreadsheet_input)
            else:
                sh = self.gc.open_by_key(spreadsheet_input)
            
            return [worksheet.title for worksheet in sh.worksheets()]
        except Exception as e:
            logger.error(f"Error fetching sheet names: {e}")
            raise

    def get_sheet_headers(self, spreadsheet_input: str, sheet_name: str = None) -> List[str]:
        """
        Get the first row (headers) of a specific sheet.
        """
        try:
            if spreadsheet_input.startswith("http"):
                sh = self.gc.open_by_url(spreadsheet_input)
            else:
                sh = self.gc.open_by_key(spreadsheet_input)
                
            if sheet_name:
                worksheet = sh.worksheet(sheet_name)
            else:
                worksheet = sh.get_worksheet(0)
            
            # Fetch only the first row
            return worksheet.row_values(1)
        except Exception as e:
            logger.error(f"Error fetching sheet headers: {e}")
            raise
