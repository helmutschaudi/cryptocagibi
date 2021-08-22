#!/usr/bin/env python3

class kelly_wallet:

    def __init__(self, wallet_id, symbol):
        self._wallet_id = wallet_id
        self._symbol = symbol
        self._balance = -1
        self._leverage = -1  # (needed when calculating profits)
        self._entry_price = -1  # (needed when calculating profits)
        self._margin_added = -1  # (needed when calculating profits)
        self._buy_order_id = -1
        self._sell_order_id = -1

    # def kelly_wallet(self):
        # self._id  # probably not required
        # self._amount_invested  # not sure if required
        # # self._has_buy_order # to be implemented later
        # self._buy_order_state
        # # self._has_sell_order # to be implemented later
        # self._sell_order_state

    def reset_sell_order_id(self):
        self._sell_order_id = -1

    def reset_buy_order_id(self):
        self._buy_order_id = -1

    def print_wallet_info(self):

        print('---------------------------')
        print('WALLET INFO')
        print(f'wallet id: {self._wallet_id}')
        print(f'symbol: {self._symbol}')
        print(f'balance: {self._balance}')
        print(f'leverage: {self._leverage}')
        print(f'entry price: {self._entry_price}')
        print(f'margin added: {self._margin_added}')
        print('---------------------------')

# GETTER -----------------------------------------------------------------------

    @property
    def wallet_id(self):
        return self._wallet_id
    
    @property
    def balance(self):
        return self._balance

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

    # SETTER -----------------------------------------------------------------------

    @balance.setter
    def balance(self, balance):
        self._balance = balance

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

    @sell_order_id.setter
    def sell_order_id(self, sell_order_id):
        self._sell_order_id = sell_order_id
