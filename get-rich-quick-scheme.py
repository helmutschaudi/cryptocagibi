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

        # Portfolio containing all wallet objects
        # replaces all dicts from previous code versions
        # self.wallet_portfolio is an array of wallet objects e.g.:
        # self..wallet_portfolio = [wallet1, wallet2, ...}
        self.wallet_portfolio = []

    def assign_wallets_to_portfolio(self, wallet_portfolio):
        self.wallet_portfolio = wallet_portfolio

    def initialize_order_ids(self, wallet, buy_id=-1, sell_id=-1):
        wallet.buy_order_id = buy_id
        wallet.sell_order_id = sell_id

    def set_buy_order_id(self, wallet, buy_id=-1):
        try:
            wallet.buy_order_id = buy_id
        except KeyError:
            self.initialize_order_ids(wallet, buy_id=buy_id)

    def set_sell_order_id(self, wallet, sell_id=-1):
        try:
            wallet.sell_order_id = sell_id
        except KeyError:
            self.initialize_order_ids(wallet, sell_id=sell_id)

    def get_total_balance_wallets(self):
        total = 0
        for current_wallet in self.wallet_portfolio:
            total += current_wallet.balance
        return total

    def check_sufficient_account_balance(self):
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

    def place_new_kelly_bet_on_closed_orders(self):

        for current_wallet in self.wallet_portfolio:
            if current_wallet.buy_order_id < 0 and current_wallet.sell_order_id < 0:
                self.place_kelly_bet(current_wallet)

            else:
                # If we reach here, order IDs are both set and positive,
                # which means we have valid current orders
                logger.info('Current BUY order ID: %s [index=%d]',  # log shows -1 for all buy orders?
                            current_wallet.buy_order_id, current_wallet.wallet_id)
                logger.info('Current SELL order ID: %s [index=%d]',
                            current_wallet.sell_order_id, current_wallet.wallet_id)

    # ---duplicate of kelly_wallet function
    def reset_open_buy_order(self, wallet):
        logger.info('    Reset BUY order ID %s [index=%d].',
                    wallet.buy_order_id, wallet.wallet_id)
        wallet.buy_order_id = -1

    # ---duplicate of kelly_wallet function
    def reset_open_sell_order(self, wallet):
        logger.info('    Reset SELL order ID %s [index=%d].',
                    wallet.sell_order_id, wallet.wallet_id)
        wallet.sell_order_id = -1

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

    def log_new_kelly_bet(self, wallet):
        symbol = wallet.symbol
        logger.info(
            'Placing Kelly bet for %s [index=%d].', symbol, wallet.wallet_id)
        logger.info('Kelly options:')
        price_market = float(self.client.futures_position_information
                             (symbol=symbol)[0]['markPrice'])
        wallet_total, wallet_free = self.get_account_balance('USDT')
        logger.info('    Account balance total: %.2f', wallet_total)
        logger.info('    Account balance free: %.2f', wallet_free)
        logger.info('    Wallet balance: %.2f',
                    wallet.balance)
        logger.info('    Market price: %.2f', price_market)
        logger.info('    Leverage: %d',
                    wallet.leverage)

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

    def buy_futures(self, myBet, wallet):
        symbol = wallet.symbol
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
            self.set_buy_order_id(wallet, buy_id=response['orderId'])
            logger.info('        BUY order ID: %s',
                        wallet.buy_order_id)
        else:
            logger.warning('Dry run, do not actually buy anything.')

    def add_margin(self, myBet, wallet):
        symbol = wallet.symbol
        # Add margin
        wallet.margin_added = myBet.margin_add
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

    def place_sell_order(self, myBet, wallet):
        symbol = wallet.symbol
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
            self.set_sell_order_id(wallet, sell_id=response['orderId'])
            logger.info('        SELL order ID: %s',
                        wallet.sell_order_id)

    def log_liquidation_info(self, myBet):
        logger.info('    Or %s futures are liquidated at ~%s (%.1f %%), '
                    'lose %s (-100.0 %% / ROE: -%.2f %%).',
                    myBet.futures_sell,
                    myBet.price_liq,
                    myBet.price_drop_percentage_lose,
                    myBet.asset_total,
                    myBet.roe_lose)

    def place_kelly_bet(self, wallet):

        # Store leverage
        leverage = wallet.leverage
        symbol = wallet.symbol

        # Set margin type and leverage
        # self.client.futures_change_margin_type(symbol=symbol, marginType='ISOLATED')

        self.client.futures_change_leverage(symbol=symbol, leverage=leverage)

        self.log_new_kelly_bet(wallet)

        price_market = float(self.client.futures_position_information
                             (symbol=symbol)[0]['markPrice'])

        myBet = kellyBet(
            wallet.balance, price_market, leverage)

        # ----------------------------------------------------------------------
        # Define gross odds and margin factor
        # myBet.kellyBet(3.5, 2.0)
        myBet.kellyBet(1.2, 1.0)
        # ----------------------------------------------------------------------

        self.log_kelly_bet_plan(myBet, symbol)

        self.buy_futures(myBet, wallet)

        self.add_margin(myBet, wallet)

        self.place_sell_order(myBet, wallet)

        self.log_liquidation_info(myBet)

    def update_status_of_all_buy_orders(self):
        all_orders = self.client.futures_get_all_orders()

        # Loop over current orders (stored in this instance)
        for current_wallet in self.wallet_portfolio:

            # If there is no current buy order, skip
            if current_wallet.buy_order_id < 0:
                logger.info('No current open buy order for index=%d',
                            current_wallet.wallet_id)
                # return # no, process all other positions as well, since we got the expensive get_all_orders() info

            else:
                # Loop over all orders (from API)
                for order in all_orders:
                    # Match the two orders
                    if order['orderId'] == current_wallet.buy_order_id:
                        current_wallet.buy_order_status = order['status']
                        current_wallet.buy_order_executed_quantity = order['executedQty']
                        current_wallet.buy_order_avg_price = order['avgPrice']

    def check_buy_order_status(self, current_wallet):
        wallet_idx = current_wallet.wallet_id
        buy_order_id = current_wallet.buy_order_id
        buy_order_status = current_wallet.buy_order_status
        avg_price = current_wallet.buy_order_avg_price
        executed_quantity = current_wallet.buy_order_executed_quantity

        if buy_order_status == 'NEW':
            logger.info('Buy order with ID %s still open '
                        '[index=%d].',
                        buy_order_id, wallet_idx)
        elif buy_order_status == 'FILLED':
            # Bought, we have to pay money
            # Update buy order
            logger.info('Buy order withd ID %s filled at %.2f '
                        '[index=%d].',
                        buy_order_id,
                        float(avg_price),
                        wallet_idx)
            self.reset_open_buy_order(current_wallet)
            # Update wallet
            logger.info('    Wallet balance wallet before: %.2f',
                        current_wallet.balance)
            # Subtract cost of futures
            current_wallet.balance -= (float(avg_price) *
                                       float(executed_quantity) /
                                       current_wallet.leverage
                                       )
            # Subtract added margin
            current_wallet.balance -= current_wallet.margin_added
            logger.info('    Wallet balance wallet after (ignoring fees): '
                        '%.2f', current_wallet.balance)
            # Store entry price for later usage
            current_wallet.entry_price = float(avg_price)
        else:
            logger.warning('Buy order with ID %s has unknown '
                           'state %s [index=%d].',
                           buy_order_id, buy_order_status, wallet_idx)

    def check_status_of_all_buy_orders(self):
        for current_wallet in self.wallet_portfolio:

            # If there is no current buy order, skip
            if current_wallet.buy_order_id < 0:
                logger.info('No current open buy order for index=%d',
                            current_wallet.wallet_id)
                # return # no, process all other positions as well, since we got the expensive get_all_orders() info

            else:
                self.check_buy_order_status(current_wallet)

    def calculate_pnl(self, executed_quantity, avg_price, wallet):
        pnl = (float(executed_quantity) *
               wallet.entry_price *
               (1/wallet.leverage-1.) +
               float(avg_price) *
               float(executed_quantity)
               )
        return pnl

    def update_status_of_all_sell_orders(self):
        all_orders = self.client.futures_get_all_orders()

        # Loop over current orders (stored in this instance)
        for current_wallet in self.wallet_portfolio:

            # If there is no current sell order, skip
            if current_wallet.sell_order_id < 0:
                logger.info('No current open sell order. index=%d',
                            current_wallet.wallet_id)

            # Loop over all orders (from API)
            # for order in all_orders:
            else:
                for order in all_orders:
                    # Match the two orders
                    if order['orderId'] == current_wallet.sell_order_id:
                        current_wallet.sell_order_status = order['status']
                        current_wallet.sell_order_executed_quantity = order['executedQty']
                        current_wallet.sell_order_avg_price = order['avgPrice']

    def check_sell_order_status(self, current_wallet):
        wallet_idx = current_wallet.wallet_id
        sell_order_id = current_wallet.sell_order_id
        sell_order_status = current_wallet.sell_order_status
        avg_price = current_wallet.sell_order_avg_price
        executed_quantity = current_wallet.buy_order_executed_quantity

        if sell_order_status == 'NEW':
            logger.info('Sell order with ID %s still open '
                        '[index=%d].',
                        sell_order_id, wallet_idx)
        elif sell_order_status == 'FILLED':
            # Sold, we get money
            # Update sell order
            logger.info('Sell order withd ID %s filled '
                        '[index=%d].',
                        sell_order_id, wallet_idx)
            self.reset_open_sell_order(current_wallet)

            # Update wallet
            logger.info('    Balance wallet before: %.2f',
                        self.wallets[wallet_idx])
            # See dev.binance.vision/t/pnl-manual-calculation/1723
            current_wallet.balance += self.calculate_pnl(
                executed_quantity, avg_price, current_wallet)
            current_wallet.balance += current_wallet.margin_added
            logger.info('    Balance wallet after (ignoring fees): '
                        '%.2f', current_wallet.balance)
        elif sell_order_status == 'CANCELED':
            # Canceled, no money
            # Update sell order
            logger.info('Sell order withd ID %s canceled '
                        '[index=%d].',
                        sell_order_id, wallet_idx)
            self.reset_open_sell_order(current_wallet)
        elif sell_order_status == 'EXPIRED':
            # Liquidated, we lose money
            # Update sell order
            logger.info('Sell order with ID %s expired '
                        '[index=%d].',
                        sell_order_id, wallet_idx)
            self.reset_open_sell_order(current_wallet)
            # Update wallet
            logger.info('Wallet balance: %.2f',
                        self.wallet_portfolio[wallet_idx].balance)
            # See dev.binance.vision/t/pnl-manual-calculation/1723
            current_wallet.balance -= (
                self.calculate_pnl(executed_quantity, avg_price, current_wallet))
            logger.info('Wallet after (ignoring fees): '
                        '%.2f', current_wallet.balance)
        else:
            # Update sell order
            logger.warning('Sell order with ID %s has unknown '
                           'state %s [index=%d].',
                           sell_order_id, sell_order_status, wallet_idx)
            logger.warning('Should I reset the open order?')

    def check_status_of_all_sell_orders(self):
        # Loop over current orders (stored in this instance)
        for current_wallet in self.wallet_portfolio:

            # If there is no current sell order, skip
            if current_wallet.sell_order_id < 0:
                logger.info('No current open sell order. index=%d',
                            current_wallet.wallet_id)
                # return # no, process all other positions as well, since we got the expensive get_all_orders() info

            # Loop over all orders (from API)
            # for order in all_orders:
            else:
                self.check_sell_order_status(current_wallet)

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

    def calculate_wallet_balance(self, wallet_size_percentage):
        _, wallet_free = self.get_account_balance('USDT')
        wallet_balance = trunc(wallet_free*wallet_size_percentage/100)
        return wallet_balance

    def print_info_of_all_wallets(self):
        for current_wallet in self.wallet_portfolio:
            current_wallet.print_wallet_info()


if __name__ == '__main__':

    # Create object
    loseitall = get_rich_quick_scheme()

    # --------------------------------------------------------------------------
    # Define investment
    wallet_indexes = [0, 1, 2, 3, 4]
    symbols = ['BTCUSDT', 'VETUSDT', 'ADAUSDT', 'ETHUSDT', 'XRPUSDT']
    wallet_size_percentages = [20, 20, 20, 20, 20]  # sum <= 100
    leverages = [20, 20, 20, 20, 20]  # leverage max. 20 for a new account
    # --------------------------------------------------------------------------

    # --------------------------------------------------------------------------
    # Turn off dry run
    #loseitall.turn_off_dry_run()
    # --------------------------------------------------------------------------

    # Create wallet portfolio containing all wallets
    wallet_portfolio = []

    i = 0
    for wallet_idx in wallet_indexes:

        # Add wallet to portfolio
        wallet_portfolio.append(kelly_wallet(wallet_indexes[i], symbols[i]))

        # Add known parameters to current wallet
        current_wallet = wallet_portfolio[i]
        current_wallet.leverage = leverages[i]
        current_wallet.balance = loseitall.calculate_wallet_balance(
            wallet_size_percentages[i])
        i = i+1

    loseitall.assign_wallets_to_portfolio(wallet_portfolio)

    loseitall.print_info_of_all_wallets()

    # --------------------------------------------------------------------------
    # DEBUG INFO
    # --------------------------------------------------------------------------
    # OUTPUT OF self.client.futures_position_information():
    # {'symbol': 'VETUSDT', 'positionAmt': '1660', 'entryPrice': '0.1327488795181', 'markPrice': '0.12813000', 'unRealizedProfit': '-7.66588000', 'liquidationPrice': '0.12743750', 'leverage': '20', 'maxNotionalValue': '25000', 'marginType': 'isolated', 'isolatedMargin': '3.26500776', 'isAutoAddMargin': 'false', 'positionSide': 'BOTH', 'notional': '212.69580000', 'isolatedWallet': '10.93088776', 'updateTime': 1629561601101} ...
    # --------------------------------------------------------------------------
    # OUTPUT OF self.client.futures_get_all_orders(): (sehr viel output, ev ein Problem mittelfristig?)
    # {'orderId': 15891537505, 'symbol': 'ADAUSDT', 'status': 'FILLED', 'clientOrderId': 'LuiVoh74hPaAmqyBWrPcPH', 'price': '0', 'avgPrice': '2.49400', 'origQty': '103', 'executedQty': '103', 'cumQuote': '256.88200', 'timeInForce': 'GTC', 'type': 'MARKET', 'reduceOnly': False, 'closePosition': False, 'side': 'BUY', 'positionSide': 'BOTH', 'stopPrice': '0', 'workingType': 'CONTRACT_PRICE', 'priceProtect': False, 'origType': 'MARKET', 'time': 1629596414966, 'updateTime': 1629596414966} ...
    # --------------------------------------------------------------------------
    # OUTPUT OF self.client.futures_get_open_orders():
    # {'orderId': 16464950183, 'symbol': 'XRPUSDT', 'status': 'FILLED', 'clientOrderId': 'autoclose-1629544376210626761', 'price': '1.2176', 'avgPrice': '1.22490', 'origQty': '218', 'executedQty': '218', 'cumQuote': '267.02820', 'timeInForce': 'IOC', 'type': 'LIMIT', 'reduceOnly': False, 'closePosition': False, 'side': 'SELL', 'positionSide': 'BOTH', 'stopPrice': '0', 'workingType': 'CONTRACT_PRICE', 'priceProtect': False, 'origType': 'LIMIT', 'time': 1629544376213, 'updateTime': 1629544376213} ...
    # --------------------------------------------------------------------------

    loseitall.check_sufficient_account_balance()

    # Go into an endless loop
    while True:

        # Get number of open positions and open orders
        loseitall.show_open_positions()
        loseitall.show_open_orders()

        # Update status of all wallets with information from binance
        loseitall.update_status_of_all_buy_orders()
        loseitall.update_status_of_all_sell_orders()

        loseitall.print_info_of_all_wallets()

        # Check status of all current orders, reset them if necessary, and
        # update wallet
        loseitall.check_status_of_all_buy_orders()
        loseitall.check_status_of_all_sell_orders()

        # Place new bets on closed orders
        loseitall.place_new_kelly_bet_on_closed_orders()

        # BUG (NOT SURE IF FIXED YET)
        # After startup of the bot, everything works fine
        # after a few hours, somtimes only 3 of 5 orders and positions are open
        # The missing positions or orders have still one of two IDs valid (not set to -1)
        # despite the fact that their status is filled! (-> ID should be set to -1)
        #
        # when all orders and positions are canceled, everything works fine again

        # SELL_ORDER=FILLED -> WE WON (market order filled, sell order filled, )

        # FUTURES_POSITION=FILLED --> WE LOST (limit sell order expired or canceled)
        # NOT TRUE! ---> BUY ORDER IS ALREADY FILLED WHEN IT STARTS

        sleep(60)
