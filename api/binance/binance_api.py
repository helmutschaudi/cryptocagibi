#!/usr/bin/env python3

from os import getenv
from math import log
from dotenv import load_dotenv
from binance.client import Client
from binance.exceptions import BinanceAPIException

class binance_api():

    def __init__(self):

        load_dotenv()
        self.client = Client(getenv('binance_api'),
                        getenv('binance_secret'))

        # List of all symbols for which we explicitely have set the margin type
        # to isolated
        self.margin_type_symbols = []

    def _convert_size_to_precision(self, size):
        return int(round(-log(size, 10), 0))

    def _get_filter_element(self, filter_list, filter_type):
        for filter_element in filter_list:
            if filter_element['filterType'] == filter_type:
                return filter_element

    def get_step_size_precision(self, symbol, filter_type='MARKET_LOT_SIZE'):
        # Filters are defined by different filter types
        # For the step size, possible filter types are
        # LOT_SIZE and MARKET_LOT_SIZE
        futures_exchange_info = self.client.futures_exchange_info()
        for info in futures_exchange_info['symbols']:
            if info['symbol'] == symbol:
                step_size = float(self._get_filter_element
                                  (info['filters'], filter_type)['stepSize']
                                  )
                return self._convert_size_to_precision(step_size)

    def get_tick_size_precision(self, symbol):
        # Filters are defined by different filter types
        # For the tick size, the filter type is always the same
        filter_type = 'PRICE_FILTER'
        futures_exchange_info = self.client.futures_exchange_info()
        for info in futures_exchange_info['symbols']:
            if info['symbol'] == symbol:
                tick_size = float(self._get_filter_element
                                  (info['filters'], filter_type)['tickSize']
                                  )
                return self._convert_size_to_precision(tick_size)

    def get_account_balance(self, asset):
        for account in self.client.futures_account_balance():
            if account['asset'] == asset:
                return (float(account['balance']),
                        float(account['withdrawAvailable']))

    def get_max_leverage(self, symbol):
        return int(self.client.futures_leverage_bracket(symbol=symbol)[0]
                   ['brackets'][0]['initialLeverage'])

    def get_futures_open_positions(self):
        open_positions = []
        for position in self.client.futures_position_information():
            if float(position['positionAmt']) != 0.:
                open_positions.append(position)
        return open_positions

    def get_futures_open_orders(self):
        return self.client.futures_get_open_orders()

    def get_futures_market_price(self, symbol):
        return float(self.client.futures_mark_price(symbol=symbol)['markPrice'])

    def _set_margin_type(self, symbol):
        # Always use isolated mode
        if symbol not in self.margin_type_symbols:
            try:
                self.client.futures_change_margin_type(symbol=symbol, marginType='ISOLATED')
            except BinanceAPIException:
                pass
            self.margin_type_symbols.append(symbol)

    def futures_create_market_order(self, symbol, side, quantity):
        self._set_margin_type(symbol)
        return self.client.futures_create_order(symbol=symbol, side=side,
                                                type='MARKET',
                                                quantity=quantity)

    def futures_create_limit_order(self, symbol, side, quantity, price=-1,
                                   timeInForce='GTC'):
        self._set_margin_type(symbol)
        return self.client.futures_create_order(symbol=symbol, side=side,
                                                type='LIMIT', quantity=quantity,
                                                price=price,
                                                timeInForce=timeInForce)

    def futures_change_position_margin(self, symbol, amount, margin_add, type=1):
        return (self.client.futures_change_position_margin(symbol=symbol,
                                                           amount=myBet
                                                           .margin_add,
                                                           type=type
                                                           ))

    def futures_change_leverage(self, symbol, leverage):
        return self.client.futures_change_leverage(symbol=symbol,
                                                   leverage=leverage)

    def get_futures_all_orders(self):
        return self.client.futures_get_all_orders()
