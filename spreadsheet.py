from __future__ import print_function

import os.path

from decouple import config
from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
EXPORT_RANGE_NAME = 'Stats'
MAPPING_RANGE_NAME = 'Players!A:C'


def _get_spreadsheets():
    secret_file = os.path.join(os.getcwd(), 'client_secret.json')
    credentials = service_account.Credentials.from_service_account_file(secret_file, scopes=SCOPES)
    service = build('sheets', 'v4', credentials=credentials)

    return service.spreadsheets()


def export_to_sheet(data):
    sheet = _get_spreadsheets()

    sheet.values().clear(
        spreadsheetId=config('SPREADSHEET_ID'),
        range=EXPORT_RANGE_NAME
    ).execute()
    sheet.values().update(
        spreadsheetId=config('SPREADSHEET_ID'),
        valueInputOption='RAW',
        range=EXPORT_RANGE_NAME,
        body=dict(
            majorDimension='ROWS',
            values=data)
    ).execute()


def get_notifications_mapping():
    sheet = _get_spreadsheets()
    result = sheet.values().get(spreadsheetId=config('SPREADSHEET_ID'),
                                range=MAPPING_RANGE_NAME).execute()
    return result.get('values', [])
