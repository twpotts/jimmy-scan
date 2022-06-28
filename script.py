# Import required packages globally

import pandas as pd
import re
import requests
import json
import datetime as dt
import numpy as np

# Define function to read tickers inside CSV file

file = "2022-03-14_options.csv"
def read_csv(file):
    csv_data = pd.read_csv(file)
    first_ticker = csv_data.columns[0]
    tickers = [first_ticker] + list(csv_data[first_ticker].values)
    tickers = [ticker.replace('.','') for ticker in tickers]
    return tickers

# Execute the function

tickers = read_csv(file)

# Define function to convert Tickers to TDA Format (e.g. SPY_031622P370) or Tradier format (e.g. SPY220316P00370000)

def convert_option_symbol(option_symbol, broker = 'TDA'):
    match_1 = re.search("\d", option_symbol)
    exp_start_idx = match_1.start()
    symbol = option_symbol[:exp_start_idx]
    match_2 = re.search("[A-Z]", option_symbol[exp_start_idx:])
    exp_end_idx = exp_start_idx + match_2.start()
    exp = option_symbol[exp_start_idx:exp_end_idx]
    year = exp[:2]
    month = exp[2:4]
    day = exp[4:]
    abbr = option_symbol[exp_end_idx:exp_end_idx+1]
    strike = option_symbol[exp_end_idx+1:]
    max_left = 5
    max_right = 3
    if "." in strike:
        strike_left = strike.split('.')[0]
        strike_right = strike.split('.')[1]
    else:
        strike_left = strike
        strike_right = ''
    left_zeroes = '0' * (max_left - len(strike_left))
    right_zeroes = '0' * (max_right - len(strike_right))
    if broker == 'TDA':
        option_symbol = symbol + '_' + month + day + year + abbr + strike
    elif broker == 'Tradier':
        option_symbol = symbol + exp + abbr + left_zeroes + strike + right_zeroes
    return option_symbol

# Execute the function

tickers = [convert_option_symbol(ticker) for ticker in tickers]

# Also grab the underlying tickers

short_tickers = [ticker.split('_')[0] for ticker in tickers]

# Import sensitive data from config

import config
tdam_refresh_token = config.tdam_refresh_token
tdam_client_id = config.tdam_client_id
tdam_act_nbr = config.tdam_act_nbr

# Define function to hook up to TD Ameritrade API

tdam_base = 'https://api.tdameritrade.com/v1/'
def tda_auth():
    tdam_auth_url = '{}oauth2/token'.format(tdam_base)
    tdam_payload = {
        'grant_type': 'refresh_token',
        'refresh_token': tdam_refresh_token,
        'client_id': tdam_client_id,
    }
    tdam_token_request = requests.post(tdam_auth_url, data = tdam_payload)
    tdam_token_response = json.loads(tdam_token_request.content)
    tdam_access_token = tdam_token_response['access_token']
    tdam_headers = {'Authorization': 'Bearer {}'.format(tdam_access_token)}
    return tdam_headers

# Execute the function

tdam_headers = tda_auth()

# Set option parameters

moneyness = 'SAK' # Strikes Above marKet (valid options = ITM, NTM, OTM, SAK, SBK, SNK, ALL (default = ALL))
atm_diff = 2
strike_count = int((atm_diff + 1) * 2)
contract_type = "CALL"
dte_start = 0
dte_end = 31
now = dt.datetime.now()
from_date = (now + dt.timedelta(days=dte_start)).strftime('%Y-%m-%d')
to_date = (now + dt.timedelta(days=dte_end)).strftime('%Y-%m-%d')

# Create a helper function that will find the ATM option given a current quote and list of strikes

def find_atm(quote, strike_list):
    if type(strike_list[0]) == str:
        strike_list = [float(strike) for strike in strike_list]
    arr = np.asarray(strike_list) 
    idx = np.abs((arr - quote)).argmin() 
    atm = strike_list[idx]
    return atm

# Define function to get the option symbols we want to trade given a list of tickers

def get_desired_options_tda(tickers):
    desired_options = []
    for ticker in tickers:
        chain_url = f'{tdam_base}marketdata/chains?apikey={tdam_client_id}&symbol={ticker}&contractType={contract_type} \
                    &includeQuotes=true&strikeCount={strike_count}&range={moneyness}&fromDate={from_date}&toDate={to_date} \
                    &optionType=S'
        tdam_chain_request = requests.get(chain_url, headers = tdam_headers)
        if tdam_chain_request.status_code != 200:
            print("Error: TDA status code")
            tdam_chain_content = tdam_chain_request.content
        else:
            tdam_chain_content = json.loads(tdam_chain_request.content)
            if tdam_chain_content['status'] == 'FAILED':
                print("Error: TDA data fetch FAILED")
            else:
                quote = round(tdam_chain_content['underlying']['last'], 2)
                calls = tdam_chain_content['callExpDateMap']
                call_exps = list(calls.keys())
                soonest_chain = calls[call_exps[0]]
                soonest_exp = call_exps[0].split(':')[0]
                soonest_strikes = list(soonest_chain.keys())
                atm = find_atm(quote, soonest_strikes)
                atm_idx = soonest_strikes.index(str(atm))
                desired_idx = atm_idx + atm_diff
                desired_strike = soonest_strikes[desired_idx]
                desired_option = soonest_chain[desired_strike][0]['symbol']
                desired_options.append(desired_option)
    return desired_options

# Execute the function

desired_options_tda = get_desired_options_tda(short_tickers)

# Define function to build order template for TDA

def build_order_tda(option_symbol):
    order_dict = \
    {
      "complexOrderStrategyType": "NONE",
      "orderType": "MARKET",
      "session": "NORMAL",
      "duration": "DAY",
      "orderStrategyType": "SINGLE",
      "orderLegCollection": [
        {
          "instruction": "BUY_TO_OPEN",
          "quantity": 1,
          "instrument": {
            "symbol": option_symbol,
            "assetType": "OPTION"
            }
        }
      ]
    }
    return order_dict

# Execute the function

order_data_tda = [build_order_tda(option) for option in desired_options_tda]

# Define function to send off orders for each of desired options

tdam_orders_url = f'{tdam_base}accounts/{tdam_act_nbr}/orders'
def send_order_tda(order_data):
    order_responses = []
    for order_datum in order_data:
        r = requests.post(tdam_orders_url, json = order_datum, headers = tdam_headers)
        if r.status_code not in [200, 201]:
            order_response = r.content
        elif len(r.content) == 0:
            order_response = r.content
        else:
            order_response = json.loads(r.content)
        print(order_response)
        order_responses.append(order_response)
    return order_responses

# Execute the function

option_orders_tda = send_order_tda(order_data_tda)

# Print log

print("Successfully reached end of script")