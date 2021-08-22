#!/usr/bin/env python3

import logging
from math import log, trunc
from datetime import datetime
from time import sleep
from binance.client import Client
from kellyBet import kellyBet
from kelly_wallet import kelly_wallet
from binance_keys import *


def setup_logger(name, log_file, level=logging.INFO):

    formatter = logging.Formatter('%(levelname)-8s - %(asctime)s - '
                                  '%(message)s')

    handler = logging.FileHandler(log_file)
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)

    return logger


# Configure logger (for info and debugging)
logger = setup_logger('default_logger',
                      'log.out',
                      level=logging.DEBUG)


class get_rich_quick_scheme():

    def __init__(self):

        # self.api_key = os.environ.get('binance_api')
        # self.api_secret = os.environ.get('binance_secret')

        self.api_key = binance_api
        self.api_secret = binance_secret

        self.client = Client(self.api_key, self.api_secret)
        self.dry_run = True

        # Keep track of multiple buy and sell orders by dicts
        # self.order_ids is a dict of dicts, e.g.:
        # self.order_ids = {11: {'BUY': 0178, 'SELL': 02320}, 22: {'BUY': 00926, 'SELL': 008}}
        # An order ID of -1  means there is no current order registered in the
        # system
        self.order_ids = {}

        # Keep track of multiple wallets by dicts
        # self.wallets is a dict, e.g.:
        # self.wallets = {11: 100, 22: 300}
        self.wallets = {}

        # Keep track of different entry prices
        # (needed when calculating profits)
        # self.entry_prices is a dict, e.g.:
        # self.entry_prices = {11: 1.10, 22: 7.70}
        self.entry_prices = {}

        # Keep track of different leverages
        # (needed when calculating profits)
        # self.leverages is a dict, e.g.:
        # self.leverages = {11: 100, 22: 125}
        self.leverages = {}

        # Keep track of different added margins
        # (needed when calculating profits)
        # self.margins_added is a dict, e.g.:
        # self.margins_added = {11: 0, 22: 6.66}
        self.margins_added = {}

    def initialize_order_ids(self, idx, buy_id=-1, sell_id=-1):
        self.order_ids[idx] = {'BUY': buy_id, 'SELL': sell_id}

    def set_buy_order_id(self, idx, buy_id=-1):
        try:
            self.order_ids[idx]['BUY'] = buy_id
        except KeyError:
            self.initialize_order_ids(idx, buy_id=buy_id)

    def set_sell_order_id(self, idx, sell_id=-1):
        try:
            self.order_ids[idx]['SELL'] = sell_id
        except KeyError:
            self.initialize_order_ids(idx, sell_id=sell_id)

    def initialize_wallets(self, idxs, wallet_balances):
        assert len(idxs) == len(wallet_balances), 'When initializing wallets, '
        'you should define as many wallets as indexes.'
        for idx, _ in enumerate(idxs):
            self.wallets[idxs[idx]] = wallet_balances[idx]
        self.check_wallets()

    def get_total_balance_wallets(self):
        total = 0
        for _, value in self.wallets.items():
            total += value
        return total

    def check_wallets(self):
        _, wallet_free = self.get_account_balance('USDT')
        if self.get_total_balance_wallets() > wallet_free:
            logger.error('The total of requested value for wallets is higher '
                         'than your free account balance: %.2f > %.2f',
                         self.get_total_balance_wallets(), wallet_free)
            raise ValueError('Not enough money.')
        logger.info('Total wallets balance: %.2f',
                    self.get_total_balance_wallets())
        logger.info('Total free wallet balance: %.2f',
                    wallet_free)

    def check_open_order(self, idx):
        try:
            # If order IDs are -1, there are no current orders for a given
            # index
            if self.order_ids[idx]['BUY'] < 0 and \
               self.order_ids[idx]['SELL'] < 0:  # ----- no buy order alone would be sufficient reason to make one
                logger.info('No current orders found. [index=%d]', idx)
                return False
        except KeyError:
            # If order IDs are unset, there are no current orders for a given
            # index
            return False

        # If we reach here, order IDs are both set and positive,
        # which means we have valid current orders
        logger.info('Current BUY order ID: %s [index=%d]',  # log shows -1 for all buy orders?
                    self.order_ids[idx]['BUY'], idx)
        logger.info('Current SELL order ID: %s [index=%d]',
                    self.order_ids[idx]['SELL'], idx)
        return True

    def reset_open_buy_order(self, idx):
        logger.info('    Reset BUY order ID %s [index=%d].',
                    self.order_ids[idx]['BUY'], idx)
        self.order_ids[idx]['BUY'] = -1

    def reset_open_sell_order(self, idx):
        logger.info('    Reset SELL order ID %s [index=%d].',
                    self.order_ids[idx]['SELL'], idx)
        self.order_ids[idx]['SELL'] = -1

    def turn_off_dry_run(self):
        self.dry_run = False

    def convert_size_to_precision(self, size):
        return int(round(-log(size, 10), 0))

    def get_filter_element(self, filter_list, filter_type):
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
                step_size = float(self.get_filter_element
                                  (info['filters'], filter_type)['stepSize']
                                  )
                return self.convert_size_to_precision(step_size)

    def get_tick_size_precision(self, symbol):
        # Filters are defined by different filter types
        # For the tick size, the filter type is always the same
        filter_type = 'PRICE_FILTER'
        futures_exchange_info = self.client.futures_exchange_info()
        for info in futures_exchange_info['symbols']:
            if info['symbol'] == symbol:
                tick_size = float(self.get_filter_element
                                  (info['filters'], filter_type)['tickSize']
                                  )
                return self.convert_size_to_precision(tick_size)

    def set_quantities(self, symbol, futures_buy, futures_sell):

        # Get quantities right for Binance API
        # See also https://binance-docs.github.io/apidocs/futures/en/#filters

        step_size = self.get_step_size_precision(symbol)
        step_size2 = self.get_step_size_precision(symbol, 'LOT_SIZE')

        logger.debug('Step size precision for %s: %s', symbol, step_size)
        logger.debug('Step size2 precision for %s: %s', symbol, step_size2)
        return (round(futures_buy, step_size),
                round(futures_sell, step_size))

    def set_prices(self, symbol, price_old, price_new):
        # Get prices right for Binance API
        # See also https://binance-docs.github.io/apidocs/futures/en/#filters

        tick_size = self.get_tick_size_precision(symbol)
        logger.debug('Tick size precision for %s: %s', symbol, tick_size)

        # If tick size is 0, the filter is disabled
        # I.e. we can buy whatever quantities we want
        # (assuming we are between min and max buy amounts)
        if tick_size == 0:
            return (price_old, price_new)

        # Otherwise we may have to round
        return (round(price_old, tick_size),
                round(price_new, tick_size))

    def get_account_balance(self, asset):
        for account in self.client.futures_account_balance():
            if account['asset'] == asset:
                return (float(account['balance']),
                        float(account['withdrawAvailable']))

    def get_max_leverage(self, symbol):
        return int(self.client.futures_leverage_bracket(symbol=symbol)[0]
                   ['brackets'][0]['initialLeverage'])

    def show_open_positions(self):

        # Get open positions
        open_positions = []
        for position in self.client.futures_position_information():
            if float(position['positionAmt']) != 0.:
                open_positions.append(position)

        logger.info('Number of open positions: %d', len(open_positions))

        # If there are open positions, output some info, otherwise do nothing
        for open_position in open_positions:

            # Collect info
            symbol = open_position['symbol']
            price_entry = float(open_position['entryPrice'])
            price_market = float(open_position['markPrice'])
            price_liq = float(open_position['liquidationPrice'])
            quantity = float(open_position['positionAmt'])
            leverage = int(open_position['leverage'])
            leverage_max = self.get_max_leverage(symbol)
            margin_initial = quantity*price_entry/leverage
            margin_total = float(open_position['isolatedWallet'])
            margin_type = open_position['marginType']
            pnl = float(open_position['unRealizedProfit'])
            roe = 100*pnl/margin_initial
            time = (datetime
                    .fromtimestamp(open_position['updateTime']/1000.)
                    .strftime('%Y-%m-%d %H:%M:%S.%f')
                    )

            logger.info('--> Symbol: %s', symbol)
            logger.info('    Leverage: %d/%d', leverage, leverage_max)
            logger.info('    Entry price: %.2f', price_entry)
            logger.info('    Market price: %.2f', price_market)
            logger.info('    PNL: %.2f', pnl)
            logger.info('    ROE: %.2f %%', roe)
            logger.info('    Initial margin: %.2f', margin_initial)
            logger.info('    Total margin: %.2f', margin_total)
            logger.info('    Margin type: %s', margin_type)
            logger.info('    Liquidation price: %.2f', price_liq)
            logger.info('    Quantity: %.3g', quantity)
            logger.info('    Time of request: %s', time)

        return len(open_positions)

    def show_open_orders(self):
        # Get data
        open_orders = self.client.futures_get_open_orders()

        logger.info('Number of open orders: %d', len(open_orders))

        # If there are open orders, output some info, otherwise do nothing
        for open_order in open_orders:

            # Collect info
            symbol = open_order['symbol']
            price_market = float(self.client.futures_mark_price(symbol=symbol)
                                 ['markPrice'])
            price_sell = float(open_order['price'])
            quantity = float(open_orders[0]['origQty'])
            time_placement = (datetime
                              .fromtimestamp(open_order['time']/1000.)
                              .strftime('%Y-%m-%d %H:%M:%S.%f')
                              )
            client_order_id = open_order['clientOrderId']

            logger.info('--> Symbol: %s', symbol)
            logger.info('    Market price: %.2f', price_market)
            logger.info('    Sell price: %.2f', price_sell)
            logger.info('    Quantity: %.3g', quantity)
            logger.info('    Time of placement: %s', time_placement)
            logger.info('    Client Order ID: %s', client_order_id)

        return len(open_orders)

    def log_new_kelly_bet(self, symbol, idx,):
        logger.info('Placing Kelly bet for %s [index=%d].', symbol, idx)
        logger.info('Kelly options:')
        price_market = float(self.client.futures_position_information
                             (symbol=symbol)[0]['markPrice'])
        wallet_total, wallet_free = self.get_account_balance('USDT')
        logger.info('    Account balance total: %.2f', wallet_total)
        logger.info('    Account balance free: %.2f', wallet_free)
        logger.info('    Wallet balance: %.2f', self.wallets[idx])
        logger.info('    Market price: %.2f', price_market)
        logger.info('    Leverage: %d', self.leverages[idx])

    def log_kelly_bet_plan(self, myBet, symbol):
        logger.info('    Bet size: %s', myBet.bet_size_factor)
        logger.info('    Gross odds: %s', myBet.gross_odds)

        logger.info('Kelly plan:')

        # Get significant figures right for Binance API
        # See also https://binance-docs.github.io/apidocs/futures/en/#filters
        futures_buy, futures_sell = self.set_quantities(symbol,
                                                        myBet.futures_buy,
                                                        myBet.futures_sell)
        logger.debug('Quantities may have changed due to API filters:')
        logger.debug('    BUY : %s --> %s', myBet.futures_buy, futures_buy)
        logger.debug('    SELL: %s --> %s', myBet.futures_sell, futures_sell)

        price_old, price_new = self.set_prices(symbol,
                                               myBet.price_old,
                                               myBet.price_new)
        logger.debug('Prices may have changed due to API filters:')
        logger.debug('    BUY : %s --> %s', myBet.price_old, price_old)
        logger.debug('    SELL: %s --> %s', myBet.price_new, price_new)

    def buy_futures(self, myBet, idx, symbol):
        futures_buy, futures_sell = self.set_quantities(symbol,
                                                        myBet.futures_buy,
                                                        myBet.futures_sell)

        price_old, price_new = self.set_prices(symbol,
                                               myBet.price_old,
                                               myBet.price_new)
        # Buy futures
        logger.info('    Buy %s futures at %s, pay initial margin %s.',
                    futures_buy, price_old, myBet.asset_old)

        if not self.dry_run:
            response = self.client.futures_create_order(symbol=symbol,
                                                        side='BUY',
                                                        type='MARKET',
                                                        quantity=futures_buy
                                                        )
            self.set_buy_order_id(idx, buy_id=response['orderId'])
            logger.info('        BUY order ID: %s',
                        self.order_ids[idx]['BUY'])
        else:
            logger.warning('Dry run, do not actually buy anything.')

    def add_margin(self, myBet, idx, symbol):
        # Add margin
        self.margins_added[idx] = myBet.margin_add
        if myBet.margin_add > 0.:
            logger.info('    Add margin %s, pay total %s.',
                        myBet.margin_add, myBet.asset_total)
            if not self.dry_run:
                response = (self.client.
                            futures_change_position_margin(symbol=symbol,
                                                           amount=myBet
                                                           .margin_add,
                                                           type=1
                                                           )
                            )
        else:
            logger.info('    No margin added.')

    def place_sell_order(self, myBet, idx, symbol):
        futures_buy, futures_sell = self.set_quantities(symbol,
                                                        myBet.futures_buy,
                                                        myBet.futures_sell)
        price_old, price_new = self.set_prices(symbol,
                                               myBet.price_old,
                                               myBet.price_new)

        logger.info('    Sell %s futures at %s (+%.1f %%), get %s, '
                    'gain %s (+%.1f %% / ROE: +%.1f %%).',
                    futures_sell, price_new,
                    myBet.price_gain_percentage_win,
                    myBet.asset_new, myBet.gain_value,
                    myBet.gain_percentage,
                    myBet.roe_win)
        if not self.dry_run:
            response = (self.client.
                        futures_create_order(symbol=symbol,
                                             side='SELL',
                                             type='LIMIT',
                                             quantity=futures_sell,
                                             timeInForce='GTC',  # Good til
                                             price=price_new     # canceled
                                             )
                        )
            self.set_sell_order_id(idx, sell_id=response['orderId'])
            logger.info('        SELL order ID: %s',
                        self.order_ids[idx]['SELL'])

    def log_liquidation_info(self, myBet):
        logger.info('    Or %s futures are liquidated at ~%s (%.1f %%), '
                    'lose %s (-100.0 %% / ROE: -%.2f %%).',
                    myBet.futures_sell,
                    myBet.price_liq,
                    myBet.price_drop_percentage_lose,
                    myBet.asset_total,
                    myBet.roe_lose)

    def place_kelly_bet(self, symbol, leverage, idx):

        # Store leverage
        self.leverages[idx] = leverage

        # Set margin type and leverage
        # self.client.futures_change_margin_type(symbol=symbol, marginType='ISOLATED')

        self.client.futures_change_leverage(symbol=symbol, leverage=leverage)

        self.log_new_kelly_bet(symbol, idx,)

        price_market = float(self.client.futures_position_information
                             (symbol=symbol)[0]['markPrice'])

        myBet = kellyBet(self.wallets[idx], price_market, leverage)

        # ----------------------------------------------------------------------
        # Define gross odds and margin factor
        # myBet.kellyBet(3.5, 2.0)
        myBet.kellyBet(1.2, 1.0)
        # ----------------------------------------------------------------------

        self.log_kelly_bet_plan(myBet, symbol)

        self.buy_futures(myBet, idx, symbol)

        self.add_margin(myBet, idx, symbol)

        self.place_sell_order(myBet, idx, symbol)

        self.log_liquidation_info(myBet)

    def check_buy_order_status(self, order, idx):
        if order['status'] == 'NEW':
            logger.info('Buy order with ID %s still open '
                        '[index=%d].',
                        order['orderId'], idx)
        elif order['status'] == 'FILLED':
            # Bought, we have to pay money
            # Update buy order
            logger.info('Buy order withd ID %s filled at %.2f '
                        '[index=%d].',
                        order['orderId'],
                        float(order['avgPrice']),
                        idx)
            # -------does this work? will a new binance order be created?
            self.reset_open_buy_order(idx)
            # Update wallet
            logger.info('    Index wallet before: %.2f',
                        self.wallets[idx])
            # Subtract cost of futures
            self.wallets[idx] -= (float(order['avgPrice']) *
                                  float(order['executedQty']) /
                                  self.leverages[idx]
                                  )
            # Subtract added margin
            self.wallets[idx] -= self.margins_added[idx]
            logger.info('    Index wallet after (ignoring fees): '
                        '%.2f', self.wallets[idx])
            # Store entry price for later usage
            self.entry_prices[idx] = float(order['avgPrice'])
        else:
            logger.warning('Buy order with ID %s has unknown '
                           'state %s [index=%d].',
                           order['orderId'], order['status'], idx)

    def check_status_of_all_buy_orders(self):
        all_orders = self.client.futures_get_all_orders()
        # Loop over current orders (stored in this instance)
        for idx, order_id in self.order_ids.items():

            # If there is no current buy order, skip
            if self.order_ids[idx]['BUY'] < 0:
                logger.info('No current open buy order for index=%d', idx)
                # return # no, process all other positions as well, since we got the expensive get_all_orders() info

            else:
                # Loop over all orders (from API)
                for order in all_orders:
                    # Match the two orders
                    if order['orderId'] == order_id['BUY']:

                        # Log order
                        logger.debug(order)

                        # We found the current order for a given index
                        # Now check status
                        self.check_buy_order_status(order, idx)

    def calculate_pnl(self, order, idx):
        pnl = (float(order['executedQty']) *
               self.entry_prices[idx] *
               (1/self.leverages[idx]-1.) +
               float(order['avgPrice']) *
               float(order['executedQty'])
               )
        return pnl

    def check_sell_order_status(self, order, idx):
        if order['status'] == 'NEW':
            logger.info('Sell order with ID %s still open '
                        '[index=%d].',
                        order['orderId'], idx)
        elif order['status'] == 'FILLED':
            # Sold, we get money
            # Update sell order
            logger.info('Sell order withd ID %s filled '
                        '[index=%d].',
                        order['orderId'], idx)
            self.reset_open_sell_order(idx)

            # Update wallet
            logger.info('    Balance wallet before: %.2f',
                        self.wallets[idx])
            # See dev.binance.vision/t/pnl-manual-calculation/1723
            self.wallets[idx] += self.calculate_pnl(order, idx)
            self.wallets[idx] += self.margins_added[idx]
            logger.info('    Balance wallet after (ignoring fees): '
                        '%.2f', self.wallets[idx])
        elif order['status'] == 'CANCELED':
            # Canceled, no money
            # Update sell order
            logger.info('Sell order withd ID %s canceled '
                        '[index=%d].',
                        order['orderId'], idx)
            self.reset_open_sell_order(idx)
        elif order['status'] == 'EXPIRED':
            # Liquidated, we lose money
            # Update sell order
            logger.info('Sell order with ID %s expired '
                        '[index=%d].',
                        order['orderId'], idx)
            self.reset_open_sell_order(idx)
            # Update wallet
            logger.info('Wallet balance: %.2f',
                        self.wallets[idx])
            # See dev.binance.vision/t/pnl-manual-calculation/1723
            self.wallets[idx] -= (self.calculate_pnl(order, idx))
            logger.info('Wallet after (ignoring fees): '
                        '%.2f', self.wallets[idx])
        else:
            # Update sell order
            logger.warning('Sell order with ID %s has unknown '
                           'state %s [index=%d].',
                           order['orderId'], order['status'], idx)
            logger.warning('Should I reset the open order?')

    def check_status_of_all_sell_orders(self):
        all_orders = self.client.futures_get_all_orders()

        # Loop over current orders (stored in this instance)
        for idx, order_id in self.order_ids.items():

            # If there is no current sell order, skip
            if self.order_ids[idx]['SELL'] < 0:
                logger.info('No current open sell order. index=%d', idx)
                # return # no, process all other positions as well, since we got the expensive get_all_orders() info

            # Loop over all orders (from API)
            # for order in all_orders:
            else:
                for order in all_orders:
                    # Match the two orders
                    if order['orderId'] == order_id['SELL']:
                        # Log order
                        logger.debug(order)
                        # We found the current order for a given index
                        # Now check status
                        self.check_sell_order_status(order, idx)

    def print_debug_info(self):
        # print(self.client.get_account())
        # print(self.client.get_asset_balance(asset='ETH'))
        # print(self.client.get_margin_account())
        # print(self.client.get_symbol_ticker(symbol="ETHUSDT"))
        # print(self.client.get_symbol_info(symbol="ETHUSDT"))
        # print(self.client.get_open_orders())
        # print(self.client.futures_account())
        # print(self.client.futures_account_balance())
        # print(self.client.futures_account_trades())
        # print(self.client.futures_get_open_orders())
        # print(self.client.futures_get_all_orders())
        # print(self.client.futures_get_open_orders()[0]['price'])
        return

    def calculate_wallet_balances(self, wallet_size_percentages):
        wallet_balances = []
        _, wallet_free = self.get_account_balance('USDT')
        for i in range(len(wallet_size_percentages)):
            wallet_balances.append(
                trunc(wallet_free*wallet_size_percentages[i]/100))
        return wallet_balances

    def calculate_wallet_balance(self, wallet_size_percentage):
        _, wallet_free = self.get_account_balance('USDT')
        wallet_balance=trunc(wallet_free*wallet_size_percentage/100)
        return wallet_balance

    def michi_debug_print_status_of_all_futures_positions(self):
        print(self.client.futures_get_all_orders())

        # open_positions = []
        # for position in self.client.futures_position_information():
        #     if float(position['positionAmt']) != 0.:  # positionAmt = position amount
        #         open_positions.append(position)

        # for open_position in open_positions:
        #     order_symbol = open_position['symbol']
        #     order_amount = float(open_position['positionAmt'])
        #     print(
        #         f'FUTURE POSITION SYMBOL:{order_symbol} AMOUNT:{order_amount} ')

    def michi_debug_print_status_of_all_sell_orders(self):
        return
        # all_orders = self.client.futures_get_open_orders()
        # for order in all_orders:
        #     order_id = order['orderId']  # ...gibt auch client id
        #     order_symbol = order['symbol']
        #     order_status = order['status']
        #     order_amount = order['origQty']
        #     print(
        #         f'BUY ORDER ID:{order_id}  SYMBOL:{order_symbol}  STATUS:{order_status} AMOUNT:{order_amount}')

    # def monitor_and_restart_investments(self):
    # not required, already existing procedure (should) work fine
        return
        # After program newstart, initial investments are made for each wallet
        # Afterwards this function monitors and restarts invesments.

        # check status of all futures positions
        #     possible status: NEW(active) FILLED(we lost) ...? CANCELED(? manually?)
        # check status of all sell orders
        #     possible status: NEW(active) FILLED(we won)  CANCELED()  EXPIRED()

        # if FUTURES_POSITION=NEW  & SELL_ORDER=NEW
        # wallet ok, still open

        # if SELL_ORDER=FILLED (market order filled, sell order filled, )
        # sold, we won
        # update stuff accordingly
        # place new kelly bet

        # if FUTURES_POSITION=FILLED (limit sell order expired or canceled ...when does what happen?)
        # we lost, futures have been liquidated
        # update stuff accordingly ()
        # place new kelly bet ()

        # if SELL_ORDER=CANCELED
        # update sell order

        # if SELL_ORDER=EXPIRED ...(when) does this happen?
        # liquidated (we lose money)
        # Update sell order
        # Update wallet

        # sell order else:
        #     # Update sell order
        #     logger.warning('Sell order with ID %s has unknown '
        #                    'state %s [index=%d].',
        #                    order['orderId'], order['status'], idx)
        #     logger.warning('Should I reset the open order?')


if __name__ == '__main__':

    # Create object
    loseitall = get_rich_quick_scheme()

    # --------------------------------------------------------------------------
    # Define investment
    idxs = [11, 22, 33, 44, 55]
    symbols = ['BTCUSDT', 'VETUSDT', 'ADAUSDT', 'ETHUSDT', 'XRPUSDT']
    wallet_size_percentages = [20, 20, 20, 20, 20]  # sum <= 100
    leverages = [20, 20, 20, 20, 20]  # leverage max. 20 for a new account
    # --------------------------------------------------------------------------

    # --------------------------------------------------------------------------
    # Turn off dry run
    # loseitall.turn_off_dry_run()
    # --------------------------------------------------------------------------

    # Create wallet portfolio containing all wallets
    wallet_portfolio = []

    i = 0
    for idx in idxs:

        # Add wallet to portfolio
        wallet_portfolio.append(kelly_wallet(idxs[i],symbols[i]))

        # Add known parameters to current wallet 
        current_wallet=wallet_portfolio[i]
        current_wallet.leverage=leverages[i]
        current_wallet.reset_buy_order_id()
        wallet_balance=loseitall.calculate_wallet_balance(20)
        current_wallet.balance=loseitall.calculate_wallet_balance(wallet_size_percentages[i])
        i = i+1

    for wallet in wallet_portfolio:
        wallet.print_wallet_info()

    # --------------------------------------------------------------------------
    # MICHI DEBUG
    # --------------------------------------------------------------------------
    # FUTURES POSITIONS:
    # futures positions can be identified by symbol and positionAmt
    # loseitall.michi_debug_print_status_of_all_futures_positions()
    # --------------------------------------------------------------------------
    # OUTPUT VON self.client.futures_position_information():
    # {'symbol': 'VETUSDT', 'positionAmt': '1660', 'entryPrice': '0.1327488795181', 'markPrice': '0.12813000', 'unRealizedProfit': '-7.66588000', 'liquidationPrice': '0.12743750', 'leverage': '20', 'maxNotionalValue': '25000', 'marginType': 'isolated', 'isolatedMargin': '3.26500776', 'isAutoAddMargin': 'false', 'positionSide': 'BOTH', 'notional': '212.69580000', 'isolatedWallet': '10.93088776', 'updateTime': 1629561601101}
    # --------------------------------------------------------------------------
    # OUTPUT VON self.client.futures_get_all_orders(): (sehr viel output, ev ein Problem mittelfristig?)
    # {'orderId': 15891537505, 'symbol': 'ADAUSDT', 'status': 'FILLED', 'clientOrderId': 'LuiVoh74hPaAmqyBWrPcPH', 'price': '0', 'avgPrice': '2.49400', 'origQty': '103', 'executedQty': '103', 'cumQuote': '256.88200', 'timeInForce': 'GTC', 'type': 'MARKET', 'reduceOnly': False, 'closePosition': False, 'side': 'BUY', 'positionSide': 'BOTH', 'stopPrice': '0', 'workingType': 'CONTRACT_PRICE', 'priceProtect': False, 'origType': 'MARKET', 'time': 1629596414966, 'updateTime': 1629596414966}

    # --------------------------------------------------------------------------
    # BUY ORDERS
    # buy orders can be identified by orderId or ClientOrderId
    # loseitall.michi_debug_print_status_of_all_sell_orders()
    # --------------------------------------------------------------------------
    # OUTPUT VON self.client.futures_get_open_orders():
    # {'orderId': 16464950183, 'symbol': 'XRPUSDT', 'status': 'FILLED', 'clientOrderId': 'autoclose-1629544376210626761', 'price': '1.2176', 'avgPrice': '1.22490', 'origQty': '218', 'executedQty': '218', 'cumQuote': '267.02820', 'timeInForce': 'IOC', 'type': 'LIMIT', 'reduceOnly': False, 'closePosition': False, 'side': 'SELL', 'positionSide': 'BOTH', 'stopPrice': '0', 'workingType': 'CONTRACT_PRICE', 'priceProtect': False, 'origType': 'LIMIT', 'time': 1629544376213, 'updateTime': 1629544376213}
    # --------------------------------------------------------------------------

    # Assign percentage of account balance to wallets
    wallet_balances = loseitall.calculate_wallet_balances(
        wallet_size_percentages)

    # Initialize wallets
    loseitall.initialize_wallets(idxs, wallet_balances)

    # Go into an endless loop
    while True:

        # Get number of open positions and open orders
        nOpenPositions = loseitall.show_open_positions()
        nOpenOrders = loseitall.show_open_orders()

        # Check status of all current orders, reset them if necessary, and
        # update wallet
        loseitall.check_status_of_all_buy_orders()
        loseitall.check_status_of_all_sell_orders()

        # Place several bets
        for i in range(len(idxs)):

            # try to avoid APIError "Too many requests" when running in dry mode
            sleep(2)
            # todo: catch and log error!

            # Get variables
            idx = idxs[i]
            symbol = symbols[i]
            # wallet = wallets[i]
            leverage = leverages[i]

            # Check if we have current orders
            if not loseitall.check_open_order(idx):

                # If we don't have current orders, place a new one
                loseitall.place_kelly_bet(symbol, leverage, idx)

        #
        # After startup of the bot, everything works fine
        # after a few hours, somtimes only 3 of 5 orders and positions are open
        # The missing positions or orders have still one of two IDs valid (not set to -1)
        # despite the fact that their status is filled !!! (-> ID should be set to -1)
        #
        # when all orders and positions are canceled, everything works fine again

        # If we don't have open positions nor orders,
        # we want to place a new bet
        # if nOpenPositions+nOpenOrders == 0:
        # #if True:
        #    loseitall.place_kelly_bet('ETHUSDT', 100)

        sleep(60)
