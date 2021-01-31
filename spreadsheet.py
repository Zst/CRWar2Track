from __future__ import print_function

import os.path

from decouple import config
from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
RANGE_NAME = 'A1:AA1000'


def export_to_sheet(data):
    secret_file = os.path.join(os.getcwd(), 'client_secret.json')
    credentials = service_account.Credentials.from_service_account_file(secret_file, scopes=SCOPES)
    service = build('sheets', 'v4', credentials=credentials)

    sheet = service.spreadsheets()

    sheet.values().clear(
        spreadsheetId=config('SPREADSHEET_ID'),
        range=RANGE_NAME
    ).execute()
    sheet.values().update(
        spreadsheetId=config('SPREADSHEET_ID'),
        valueInputOption='RAW',
        range=RANGE_NAME,
        body=dict(
            majorDimension='ROWS',
            values=data)
    ).execute()
