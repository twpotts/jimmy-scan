# Converted from ThinkScript scans

# Measure execution time

import time
time_start = time.time()

# Import packages

import requests
import json
import pandas as pd
import numpy as np
import ta
import datetime as dt
import pyrebase
import pytz
from selenium import webdriver
from selenium_stealth import stealth
from bs4 import BeautifulSoup
from chromedriver_py import binary_path

# Web scrapes a list of symbols from FinViz (filters: index = S&P 500, optionable = True)

# user_headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.51 Safari/537.36'}
# nbr_symbols = 510
# symbols_list = []
# row_nbr = 1
# try:
#     # Beautiful Soup 1st
#     while row_nbr < nbr_symbols:
#         print(row_nbr)
#         finviz_url = f'https://finviz.com/screener.ashx?v=111&f=idx_sp500,sh_opt_option&ft=4&o=-volume&r={row_nbr}'
#         response = requests.get(finviz_url, headers = user_headers)
#         html = response.content
#         soup = BeautifulSoup(html, 'html.parser')
#         table = soup.find('table', {"class": 'table-light'})
#         trs = table.find_all('tr')[1:]
#         tds = [tr.find_all('td') for tr in trs]
#         page = [row.string for row in table.find_all('a', {'class': 'screener-link-primary'})]
#         for symbol in page:
#             symbols_list.append(symbol)
#         row_nbr += 20
#     last_idx = symbols_list.index(symbols_list[-1])
#     symbols_list = symbols_list[:last_idx+1]
#     with open("symbols_list.txt", "w") as f:
#         for symbol in symbols_list:
#             f.write(symbol + "\n")
#         f.close()
#     print("Successful web scrape from FinViz using Beautiful Soup")
# except Exception as e:
#     print("Error web scraping from FinViz using Beautiful Soup")
#     print(e)
#     # Selenium stealth 2nd
#     try:
#         chrome_options = webdriver.ChromeOptions()
#         chrome_options.add_argument("--headless")
#         driver = webdriver.Chrome(executable_path = binary_path, options = chrome_options)
#         # Don't get detected by website
#         stealth(driver,
#                 languages=["en-US", "en"],
#                 vendor="Google Inc.",
#                 platform="Win32",
#                 webgl_vendor="Intel Inc.",
#                 renderer="Intel Iris OpenGL Engine",
#                 fix_hairline=True,
#         )
#         symbols_list = []
#         row_nbr = 1
#         while row_nbr < nbr_symbols:
#             print(row_nbr)
#             finviz_url = f'https://finviz.com/screener.ashx?v=111&f=idx_sp500,sh_opt_option&ft=4&o=-volume&r={row_nbr}'
#             driver.get(finviz_url)
#             table = driver.find_elements_by_class_name("table-light")[0]
#             trs = table.find_elements_by_tag_name('tr')[1:]
#             tds = [tr.find_elements_by_tag_name('td') for tr in trs]
#             page = [row.text for row in table.find_elements_by_class_name('screener-link-primary')]
#             for symbol in page:
#                 symbols_list.append(symbol)
#             row_nbr += 20
#         driver.quit()
#         last_idx = symbols_list.index(symbols_list[-1])
#         symbols_list = symbols_list[:last_idx+1]
#         with open("symbols_list.txt", "w") as f:
#             for symbol in symbols_list:
#                 f.write(symbol + "\n")
#             f.close()
#         print("Successful web scrape from FinViz using Selenium Stealth")
#     except Exception as e2:
#         print("Error web scraping from FinViz using Selenium Stealth")
#         print(e2)

# Extract symbols list

with open("symbols_list.txt") as f:
    items = f.readlines()
    symbols_list = [item.split('\n')[0] for item in items]

# Import sensitive items from config

import config
tradier_act_nbr = config.tradier_act_nbr
tradier_api = config.tradier_api
tradier_act_nbr_paper = config.tradier_act_nbr_paper
tradier_api_paper = config.tradier_api_paper

# Define function to connect to Tradier API

def auth_tradier(paper_trading=True):
    if paper_trading == True:
        tradier_base = 'https://sandbox.tradier.com/v1/'
        trad_account = tradier_act_nbr_paper
        trad_api = tradier_api_paper
    else:
        tradier_base = 'https://api.tradier.com/v1/'
        trad_account = tradier_act_nbr
        trad_api = tradier_api
    tradier_headers = {
        'Authorization': f'Bearer {trad_api}',
        'Accept': 'application/json'
    }
    auth_trad = {
        'tradier_base': tradier_base,
        'tradier_headers': tradier_headers,
        'tradier_act_nbr': trad_account
    }
    return auth_trad

# Execute the function

auth_trad = auth_tradier()

# Connect to database

db_config = config.db_config
firebase = pyrebase.initialize_app(db_config)
db = firebase.database()
db_name = "scanner"

# Retrieve database values

info = dict(db.child(db_name).child("info").get().val())
DTE_max = int(info['DTE_max'])
DTE_min = int(info['DTE_min'])
cutoff = int(info['cutoff'])
delta = int(info['delta'])
min_oi = int(info['min_oi'])
time_back = int(info['time_back'])
interval = str(info['interval']) # daily, weekly, monthly
end_date = str(info['end_date'])
if end_date != "":
    print(f"Using {end_date} as end date")

# Define function to get historical data from Tradier

def get_historical_data(symbol):
    date_format = "%Y-%m-%d"
    if end_date == "":
        end = dt.datetime.now()
        end_str = end.strftime(date_format)
    else:
        end_str = end_date
        end = pd.to_datetime(end_date)
    start = end - dt.timedelta(days=int(time_back*2))
    start_str = start.strftime(date_format)
    data_url = f"{auth_trad['tradier_base']}markets/history?symbol={symbol}&interval={interval}&start={start_str}&end={end_str}"
    data_request = requests.get(data_url, headers = auth_trad['tradier_headers'])
    if data_request.status_code in [200, 201]:
        data = json.loads(data_request.content)
        if 'history' in data:
            data = data['history']
            if 'day' in data:
                data = data['day']
                if data[-1]['close'] == 'NaN':
                    data = data[:-1]
            else:
                print(data)
                return False
        else:
            print(data)
            return False
    else:
        data = data_request.content
        print(data)
        return False
    return data

# Define function to get quote

def get_quote(symbol):
    symbol = symbol.upper()
    auth = auth_tradier()
    quote_url = '{}markets/quotes?symbols={}'.format(auth['tradier_base'], symbol)
    quote_request = requests.get(quote_url, headers = auth['tradier_headers'])
    if quote_request.status_code != 200:
        quote = quote_request.content
        print(quote)
        return False
    else:
        quote = json.loads(quote_request.content)
        if 'quotes' in quote:
            quote = quote['quotes']
            if 'quote' in quote:
                quote = quote['quote']
    return quote

# Define function to find 30-delta call

def find_call(symbol):
    auth = auth_tradier()
    day_start = dt.datetime.now() + dt.timedelta(days=DTE_min)
    day_counter = day_start
    day_max = dt.datetime.now() + dt.timedelta(days=DTE_max)
    chain = [None]
    while day_counter <= day_max:
        exp = day_counter.strftime('%Y-%m-%d')
        chain_url = '{}markets/options/chains?symbol={}&expiration={}&greeks=True'.format(auth['tradier_base'], symbol, exp)
        chain_request = requests.get(chain_url, headers = auth['tradier_headers'])
        if chain_request.status_code != 200:
            chain = chain_request.content
            return False
        chain = json.loads(chain_request.content)
        if 'options' in chain:
            chain = chain['options']
            if chain != None:
                break
        day_counter = day_counter + dt.timedelta(days=1)
    if chain == None:
        return False
    if 'option' in chain:
        chain = chain['option']
    else:
        return False
    calls = [option for option in chain if option['option_type'] == 'call' and option['open_interest'] > min_oi]
    if calls != []:
        call_deltas = [call['greeks']['delta'] if call['greeks'] != None else 0 for call in calls]
        desired_delta = delta / 100
        delta_diffs = list(abs(np.array(call_deltas) - desired_delta))
        min_diff = min(delta_diffs)
        min_idx = delta_diffs.index(min_diff)
        desired_call = calls[min_idx]
    else:
        return False
    return desired_call

# Use TA library to create ThinkScript functions

def ExpAverage(c, calcLength):
    ema = ta.trend.ema_indicator(c, window=calcLength)
    return ema

def CCI(h, l, c, cci_window):
    cci = ta.trend.cci(h, l, c, window=cci_window)
    return cci

# User inputs

calcLength = 1
smoothLength = 2

# Execute the scan

watchlist_down, watchlist_up = [], []
for symbol in symbols_list[:cutoff]:
    nbr = symbols_list.index(symbol)
    print(nbr)
    if '-' in symbol:
        symbol = symbol.replace('-','/')
    data = get_historical_data(symbol)
    if data:
        o = [bar['open'] for bar in data if type(bar) != int]
        h = [bar['high'] for bar in data if type(bar) != int]
        l = [bar['low'] for bar in data if type(bar) != int]
        c = [bar['close'] for bar in data if type(bar) != int]
        df = pd.DataFrame()
        df['o'] = o
        df['h'] = h
        df['l'] = l
        df['c'] = c
        EMA = ExpAverage(df['c'], calcLength)
        Main = ExpAverage(EMA, smoothLength)
        CCI4 = ta.trend.cci(df['h'], df['l'], df['c'], 4)
        MOBDN = Main.values[-2] > Main.values[-1]
        CCI14 = ta.trend.cci(df['h'], df['l'], df['c'], 14)
        C4DN = CCI4.values[-2] > CCI4.values[-1]
        C14DN = CCI14.values[-2] > CCI14.values[-1]
        C4CHGDN = CCI4.values[-2] > CCI4.values[-3]
        MOBCHGDN = Main.values[-2] > Main.values[-3]
        C14CHGDN = CCI14.values[-2] > CCI14.values[-3]
        if (C4DN and MOBDN and C14DN and C4CHGDN) \
        or (C4DN and MOBDN and C14DN and  MOBCHGDN) \
        or (C4DN and MOBDN and C14DN and C14CHGDN):
            info_dict = {}
            if end_date == "":
                quote = get_quote(symbol)
                call = find_call(symbol)
                if call:
                    if 'greeks' in call:
                        if call['greeks'] != None:
                            if 'delta' in call['greeks']:
                                greek_delta = call['greeks']['delta']
                            else:
                                greek_delta = 0
                        else:
                            greek_delta = 0
                    else:
                        greek_delta = 0
                    info_dict = {
                        "option_symbol": call['symbol'],
                        "symbol": call['underlying'],
                        "strike": call['strike'],
                        "expiration": call['expiration_date'],
                        "delta": round(float(greek_delta),3),
                        "open_interest": call['open_interest']
                    }
                    if quote:
                        info_dict["last"] = quote['last']
                    watchlist_down.append(info_dict)
                    print(f"{symbol} added to down watchlist")
            else:
                info_dict["symbol"] = symbol
                info_dict["last"] = data[-1]['close']
                watchlist_down.append(info_dict)
                print(f"{symbol} added to down watchlist")
        C4UP = CCI4.values[-2] < CCI4.values[-1]
        MOBUP = Main.values[-2] < Main.values[-1]
        C14UP =  CCI14.values[-2] < CCI14.values[-1]
        C4CHG =CCI4.values[-2] < CCI4.values[-3]
        MOBCHG = Main.values[-2] < Main.values[-3]
        C14CHG = CCI14.values[-2] < CCI14.values[-3]
        if (C4UP and MOBUP and C14UP and C4CHG) \
        or (C4UP and MOBUP and C14UP and  MOBCHG) \
        or (C4UP and MOBUP and C14UP and C14CHG):
            info_dict = {}
            if end_date == "":
                quote = get_quote(symbol)
                call = find_call(symbol)
                if call:
                    if 'greeks' in call:
                        if call['greeks'] != None:
                            if 'delta' in call['greeks']:
                                greek_delta = call['greeks']['delta']
                            else:
                                greek_delta = 0
                        else:
                            greek_delta = 0
                    else:
                        greek_delta = 0
                    info_dict = {
                        "option_symbol": call['symbol'],
                        "symbol": call['underlying'],
                        "strike": call['strike'],
                        "expiration": call['expiration_date'],
                        "delta": round(float(greek_delta),3),
                        "open_interest": call['open_interest']
                    }
                    if quote:
                        info_dict["last"] = quote['last']
                    watchlist_up.append(info_dict)
                    print(f"{symbol} added to up watchlist")
            else:
                info_dict["symbol"] = symbol
                info_dict["last"] = data[-1]['close']
                watchlist_up.append(info_dict)
                print(f"{symbol} added to up watchlist")
    json_count = {
        "counter": nbr,
        "progress_pct": int((nbr + 1) / min(cutoff,len(symbols_list)) * 100 - 100),
    }
    if nbr == 0:
        json_count["symbols_length"] = len(symbols_list)
    db.child(db_name).child("info").update(json_count)

# Display results

# print(f"Watchlist (down) ({len(watchlist_down)}) = {watchlist_down}")
# print(f"Watchlist (up) ({len(watchlist_up)}) = {watchlist_up}")

# Store in database

if watchlist_down == []:
    watchlist_down = [{
        "option_symbol": "NA",
        "symbol": "NA",
        "strike": "NA",
        "expiration": "NA",
        "last": "NA",
        "delta": "NA",
        "open_interest": "NA"
    }]
if watchlist_up == []:
    watchlist_up = [{
        "option_symbol": "NA",
        "symbol": "NA",
        "strike": "NA",
        "expiration": "NA",
        "last": "NA",
        "delta": "NA",
        "open_interest": "NA"
    }]
db.child(db_name).child("down_list").set(watchlist_down)
db.child(db_name).child("up_list").set(watchlist_up)
local_timezone = local_timezone = pytz.timezone('US/Pacific')
now = dt.datetime.now()
db_time = now.astimezone(local_timezone).strftime("%c")
json_info = {
    "time": db_time,
    "counter": min(cutoff,len(symbols_list)) - 1,
    "length_up": len(watchlist_up),
    "length_down": len(watchlist_down)
}
db.child(db_name).child("info").update(json_info)

# Fetch database

# down_list = db.child(db_name).child("down_list").get().val()
# up_list = db.child(db_name).child("up_list").get().val()
# info = dict(db.child(db_name).child("info").get().val())

# Not needed

length = 2
zero = 0
ob = round(length * 0.7)
os = round(-length * 0.7)

# Execution time

time_end = time.time()
time_total = round(time_end - time_start, 2)
print(f"Execution time = {time_total} seconds")