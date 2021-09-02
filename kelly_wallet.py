#!/usr/bin/env python3
from datetime import datetime


class kelly_wallet:

    def __init__(self, wallet_id, symbol):
        self._wallet_id = wallet_id
        self._symbol = symbol
        self._balance = -1
        self._initial_balance = -1
        self._leverage = -1
        self._entry_price = -1 # price paid when bought futures
        # win case price not stored yet -> get_filled_order_avg_price(current_wallet)        
        self._liquidation_price = -1 # lose case price
        self._margin_added = -1
        self._buy_order_id = -1
        self._buy_order_status = 'none'
        self._buy_order_executed_quantity = -1
        self._sell_order_id = -1
        self._sell_order_status = 'none'
        self._sell_order_executed_quantity = -1
        self._symbol_no_usdt = self.get_symbol_without_usdt()

    def get_symbol_without_usdt(self):
        return(self._symbol.replace('USDT',''))
    
    def reset_sell_order_id(self):
        self._sell_order_id = -1

    def reset_buy_order_id(self):
        self._buy_order_id = -1

    def print_wallet_info(self):

        print('---------------------------------')
        print(f'WALLET INFO FOR ID {self._wallet_id}    {self._symbol}')
        print(f'printtime:    {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}')
        print(f'current balance: {self._balance:.2f} USDT')
        print(f'initial balance: {self._initial_balance:.2f} USDT')
        print(f'executed qty: {self._buy_order_executed_quantity} {self._symbol_no_usdt}')
        print(f'leverage: {self._leverage}')
        print(f'entry price: {self._entry_price}')
        print(f'liquidation_price: {self._liquidation_price}')
        print(f'margin added: {self._margin_added}')
        print(f'buy order id: {self._buy_order_id}')
        print(f'buy order status: {self._buy_order_status}')
        print(f'sell order id: {self._sell_order_id}')
        print(f'sell order status: {self._sell_order_status}')
        print('---------------------------------')

# GETTER -----------------------------------------------------------------------

    @property
    def wallet_id(self):
        return self._wallet_id

    @property
    def balance(self):
        return self._balance

    @property
    def initial_balance(self):
        return self._initial_balance

    @property
    def symbol(self):
        return self._symbol

    @property
    def leverage(self):
        return self._leverage

    @property
    def entry_price(self):
        return self._entry_price

    @property
    def margin_added(self):
        return self._margin_added

    @property
    def buy_order_id(self):
        return self._buy_order_id

    @property
    def sell_order_id(self):
        return self._sell_order_id

    @property
    def buy_order_status(self):
        return self._buy_order_status

    @property
    def sell_order_status(self):
        return self._sell_order_status

    @property
    def buy_order_executed_quantity(self):
        return self._buy_order_executed_quantity

    @property
    def liquidation_price(self):
        return self._liquidation_price

    @property
    def sell_order_executed_quantity(self):
        return self._sell_order_executed_quantity

   
    # SETTER -----------------------------------------------------------------------

    @balance.setter
    def balance(self, balance):
        self._balance = balance

    @initial_balance.setter
    def initial_balance(self, initial_balance):
        self._initial_balance = initial_balance

    @leverage.setter
    def leverage(self, leverage):
        self._leverage = leverage

    @entry_price.setter
    def entry_price(self, entry_price):
        self._entry_price = entry_price

    @margin_added.setter
    def margin_added(self, margin_added):
        self._margin_added = margin_added

    @buy_order_id.setter
    def buy_order_id(self, buy_order_id):
        self._buy_order_id = buy_order_id

    @buy_order_executed_quantity.setter
    def buy_order_executed_quantity(self, buy_order_executed_quantity):
        self._buy_order_executed_quantity = buy_order_executed_quantity

    @liquidation_price.setter
    def liquidation_price(self, liquidation_price):
        self._liquidation_price = liquidation_price

    @sell_order_id.setter
    def sell_order_id(self, sell_order_id):
        self._sell_order_id = sell_order_id

    @buy_order_status.setter
    def buy_order_status(self, buy_order_status):
        self._buy_order_status = buy_order_status

    @sell_order_status.setter
    def sell_order_status(self, sell_order_status):
        self._sell_order_status = sell_order_status

    @sell_order_executed_quantity.setter
    def sell_order_executed_quantity(self, sell_order_executed_quantity):
        self._sell_order_executed_quantity = sell_order_executed_quantity

   
