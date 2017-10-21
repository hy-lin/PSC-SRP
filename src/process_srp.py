
from __future__ import print_function
import httplib2
import os

from apiclient import discovery
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage

from urllib.parse import urlparse
import urllib.request

import gzip
import json
from io import StringIO
import static_data
import datetime

try:
    import argparse
    flags = argparse.ArgumentParser(parents=[tools.argparser]).parse_args()
except ImportError:
    flags = None

# If modifying these scopes, delete your previously saved credentials
# at ~/.credentials/sheets.googleapis.com-python-quickstart.json
SCOPES = ['https://www.googleapis.com/auth/spreadsheets',
          'https://www.googleapis.com/auth/spreadsheets.readonly']
CLIENT_SECRET_FILE = 'client_secret.json'
APPLICATION_NAME = 'Google Sheets API Python Quickstart'


class ZKillRequest(urllib.request.Request):
    def __init__(self, kmID):
        url = 'https://zkillboard.com/api/killID/{}/no-items/no-attackers/'.format(kmID)
        urllib.request.Request.__init__(
            self,
            url = url,
            headers = {'User-Agent': 'https://pleaseignore.com Maintainer: CogVokan@pleaseignore.com',
                    'Accept-Encoding': 'gzip'}
            )

def get_credentials():
    """Gets valid user credentials from storage.

    If nothing has been stored, or if the stored credentials are invalid,
    the OAuth2 flow is completed to obtain the new credentials.

    Returns:
        Credentials, the obtained credential.
    """
    home_dir = os.path.expanduser('~')
    credential_dir = os.path.join(home_dir, '.credentials')
    if not os.path.exists(credential_dir):
        os.makedirs(credential_dir)
    credential_path = os.path.join(credential_dir,
                                   'sheets.googleapis.com-python-quickstart.json')

    store = Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
        flow.user_agent = APPLICATION_NAME
        if flags:
            credentials = tools.run_flow(flow, store, flags)
        else: # Needed only for compatibility with Python 2.6
            credentials = tools.run(flow, store)
        print('Storing credentials to ' + credential_path)
    return credentials


def getService():
    credentials = get_credentials()
    http = credentials.authorize(httplib2.Http())
    discoveryUrl = ('https://sheets.googleapis.com/$discovery/rest?'
                    'version=v4')
    service = discovery.build('sheets', 'v4', http=http,
                              discoveryServiceUrl=discoveryUrl)

    return service

def getSRPLog(service):
    """Shows basic usage of the Sheets API.

    Creates a Sheets API service object and prints the names and majors of
    students in a sample spreadsheet:
    https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit
    """
    spreadsheetId = '1JHZepSOgSRnntI7DFkWZ01pc_1BgYOxA86fadfrJrpY'
    rangeName = 'SRP List!A2:G'
    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheetId, range=rangeName).execute()
    values = result.get('values', [])

    if not values:
        print('No data found.')
        return None
    else:
        return values


def loadPayout(service):
    """Shows basic usage of the Sheets API.

    Creates a Sheets API service object and prints the names and majors of
    students in a sample spreadsheet:
    https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit
    """

    spreadsheetId = '1JHZepSOgSRnntI7DFkWZ01pc_1BgYOxA86fadfrJrpY'
    rangeName = 'SRP Payout!A2:B'
    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheetId, range=rangeName).execute()
    values = result.get('values', [])

    if not values:
        print('No data found.')
        return None
    else:
        return values

def writeCell(service, range_, val):
    spreadsheet_id = '1JHZepSOgSRnntI7DFkWZ01pc_1BgYOxA86fadfrJrpY'  # TODO: Update placeholder value.

    # The A1 notation of the values to update.

    value_range_body = {
        'range': range_,
        'values': [
            [val]
        ]
    }

    request = service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=range_,
        body=value_range_body, 
        valueInputOption='RAW'
        )

    response = request.execute()


class Player(object):
    def __init__(self, main_name, character_ids = [], character_names = []):
        self.main_name = main_name
        self.character_ids = character_ids
        self.character_names = character_names
        self.loses = []
        self.payout = []

    def __eq__(self, target):
        return self.main_name == target


def processSRP():
    service = getService()
    srp_logs = getSRPLog(service)
    srp_payouts = loadPayout(service)
    players = {}

    for r_ind, row in enumerate(srp_logs):
        if row[2] in ['approved', 'evaluated']:
            km_id = getKMID(row)
            km_info = getKMInfo(km_id)
            character_id = km_info[0]['victim']['character_id']
            character_name = getCharacterName(character_id)
            ship_type = static_data.ships[km_info[0]['victim']['ship_type_id']]

            if row[1] not in players:
                players[row[1]] = Player(row[1], character_ids = [character_id], character_names = [character_name])

            players[row[1]].loses.append(ship_type)

            if row[2] == 'evaluated':
                payout = float(row[4])
            else:
                payout = getPayout(ship_type, srp_payouts)

            players[row[1]].payout.append(payout)
            time_string = datetime.datetime.now().isoformat()


            writeCell(service, 'SRP List!C{}'.format(r_ind+2), 'evaluated')
            writeCell(service, 'SRP List!D{}'.format(r_ind+2), time_string)
            writeCell(service, 'SRP List!E{}'.format(r_ind+2), payout)
            writeCell(service, 'SRP List!F{}'.format(r_ind+2), ship_type)


            print(character_id, character_name, ship_type, payout)


def getKMInfo(km_id):
    km_request = ZKillRequest(km_id)
    respond = urllib.request.urlopen(km_request)
    km_info = gzip.decompress(respond.read()).decode()
    km_info = json.loads(km_info)
    return km_info


def getCharacterName(character_id):
    # https://esi.tech.ccp.is/latest/characters/names/?character_ids=455675978&datasource=tranquility
    name_request = urllib.request.Request(url = 'https://esi.tech.ccp.is/latest/characters/names/?character_ids={}&datasource=tranquility'.format(character_id))
    respond = urllib.request.urlopen(name_request)
    name_info = respond.read().decode()
    name_info = json.loads(name_info)
    return name_info[0]['character_name']


def getKMID(row):
    parsed_url = urlparse(row[0])
    path = parsed_url.path.split('/')
    km_id = path[path.index('kill')+1]

    return km_id


def getPayout(ship_type, srp_payouts):
    for row in srp_payouts:
        if ship_type == row[0]:
            return float(row[1])

if __name__ == '__main__':
    processSRP()

