#!/usr/bin/env python3

import os
import logging
from math import trunc
from datetime import datetime
from time import sleep
from api.binance.binance_api import binance_api
from kellyBet import kellyBet
from kelly_wallet import kelly_wallet

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

        self.dry_run = True

        self._api = binance_api()

        # Portfolio containing all wallet objects
        # replaces all dicts from previous code versions
        # wallet_portfolio is an array of wallet objects e.g.:
        # wallet_portfolio = [wallet1, wallet2, ...}
        self.wallet_portfolio = []

        # Store binance "futures_get_all_orders()" response
        # this is an expensive call and will therefore only
        # be executed once per program cycle
        self.status_of_all_binance_orders = {}

    def add_wallet_to_portfolio(self, wallet):
        self.wallet_portfolio.append(wallet)


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
        _, account_free = self.get_account_balance('USDT')
        if self.get_total_balance_wallets() > account_free:
            logger.error('The total of requested value for wallets is higher '
                         'than your free account balance: %.2f > %.2f',
                         self.get_total_balance_wallets(), account_free)
            raise ValueError('Not enough money.')
        logger.info('Total wallets balance: %.2f',
                    self.get_total_balance_wallets())
        logger.info('Total free account balance: %.2f',
                    account_free)

    def place_new_kelly_bet_on_closed_orders(self):

        for current_wallet in self.wallet_portfolio:
            if current_wallet.buy_order_id < 0 and current_wallet.sell_order_id < 0:
                print(f'--> PLACE NEW KELLY BET ON {current_wallet.symbol} <--')
                self.place_kelly_bet(current_wallet)

            else:
                # If we reach here, order IDs are both set and positive,
                # which means we have valid current orders
                logger.info('Current BUY order ID: %s [index=%d]',
                            current_wallet.buy_order_id, current_wallet.wallet_id)
                logger.info('Current SELL order ID: %s [index=%d]',
                            current_wallet.sell_order_id, current_wallet.wallet_id)

    def reset_open_buy_order(self, wallet):
        logger.info('    Reset BUY order ID %s [index=%d].',
                    wallet.buy_order_id, wallet.wallet_id)
        wallet.reset_buy_order_id()

    def reset_open_sell_order(self, wallet):
        logger.info('    Reset SELL order ID %s [index=%d].',
                    wallet.sell_order_id, wallet.wallet_id)
        wallet.reset_sell_order_id()

    def turn_off_dry_run(self):
        self.dry_run = False

    def set_quantities(self, symbol, futures_buy, futures_sell):

        # Get quantities right for Binance API
        # See also https://binance-docs.github.io/apidocs/futures/en/#filters

        step_size = self._api.get_step_size_precision(symbol)
        step_size2 = self._api.get_step_size_precision(symbol, 'LOT_SIZE')

        logger.debug('Step size precision for %s: %s', symbol, step_size)
        logger.debug('Step size2 precision for %s: %s', symbol, step_size2)
        return (round(futures_buy, step_size),
                round(futures_sell, step_size))

    def set_prices(self, symbol, price_old, price_new):
        # Get prices right for Binance API
        # See also https://binance-docs.github.io/apidocs/futures/en/#filters

        tick_size = self._api.get_tick_size_precision(symbol)
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
        return self._api.get_account_balance(asset)

    def get_max_leverage(self, symbol):
        return self._api.get_max_leverage(symbol)

    def show_open_positions(self):

        # Get open positions
        open_positions = self._api.get_futures_open_positions()

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
        open_orders = self._api.get_futures_open_orders()

        logger.info('Number of open orders: %d', len(open_orders))

        # If there are open orders, output some info, otherwise do nothing
        for open_order in open_orders:

            # Collect info
            symbol = open_order['symbol']
            price_market = self._api.get_futures_market_price(symbol)
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
        price_market = self._api.get_futures_market_price(symbol)
        account_total, account_free = self.get_account_balance('USDT')
        logger.info('    Account balance total: %.2f', account_total)
        logger.info('    Account balance free: %.2f', account_free)
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

        # TODO: Check api.create_margin_order() if you can buy and add margin
        # in one step
        # Buy futures
        logger.info('    Buy %s futures at %s, pay initial margin %s.',
                    futures_buy, price_old, myBet.asset_old)

        if not self.dry_run:
            response = self._api.futures_create_market_order(symbol=symbol,
                                                             side='BUY',
                                                             quantity=futures_buy
                                                             )
            self.set_buy_order_id(wallet, buy_id=response['orderId'])
            logger.info('        BUY order ID: %s',
                        wallet.buy_order_id)

        else:
            logger.warning('Dry run, do not actually buy anything.')

    def add_margin(self, myBet, wallet):
        symbol = wallet.symbol
        wallet.margin_added = myBet.margin_add

        if myBet.margin_add > 0.:
            logger.info('    Add margin %s, pay total %s.',
                        myBet.margin_add, myBet.asset_total)
            if not self.dry_run:
                # Add margin
                response = (self._api.
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
            response = (self._api.
                        futures_create_limit_order(symbol=symbol,
                                                   side='SELL',
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

        # Set leverage
        self._api.futures_change_leverage(symbol=wallet.symbol,
                                          leverage=wallet.leverage)

        self.log_new_kelly_bet(wallet)

        price_market = self._api.get_futures_market_price(wallet.symbol)

        myBet = kellyBet(
            wallet.balance, price_market, wallet.leverage)

        # ----------------------------------------------------------------------
        # Define gross odds and margin factor

        gross_odds = 1.2     # 1.2 | 1.4 | 3.5
        margin_factor = 1.0  # 1.0 | 5.0 | 2.0

        myBet.kellyBet(gross_odds, margin_factor)
        # ----------------------------------------------------------------------

        self.log_kelly_bet_plan(myBet, wallet.symbol)

        self.buy_futures(myBet, wallet)

        self.add_margin(myBet, wallet)

        self.place_sell_order(myBet, wallet)

        self.log_liquidation_info(myBet)

    def get_futures_all_orders(self):
        self.status_of_all_binance_orders = self._api.get_futures_all_orders()

    def get_buy_order_liquidation_price(self,wallet):
            all_orders =self._api.get_futures_open_positions()
            
            for order in all_orders:
                if order['symbol']==wallet.symbol: # compare by symbol, API response has no orderId's
                    wallet.liquidation_price = order['liquidationPrice']
                    print(f'{wallet.symbol} WALLET LIQUIDATION PRICE: {wallet.liquidation_price}')

    def update_status_of_all_buy_orders(self):

        # Loop over current orders
        for current_wallet in self.wallet_portfolio:

            # If there is a current buy order
            if current_wallet.buy_order_id != -1:

                # Loop over all orders (from API)
                all_orders = self.status_of_all_binance_orders
                for order in all_orders:
                    # Match the two orders
                    if order['orderId'] == current_wallet.buy_order_id:
                        current_wallet.buy_order_status = order['status']
                        current_wallet.buy_order_executed_quantity = order['executedQty']
                        current_wallet.entry_price = order['avgPrice']

    def check_buy_order_status(self, current_wallet):
        wallet_idx = current_wallet.wallet_id
        buy_order_id = current_wallet.buy_order_id
        buy_order_status = current_wallet.buy_order_status
        entry_price = current_wallet.entry_price
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
                        float(entry_price),
                        wallet_idx)
            self.get_buy_order_liquidation_price(current_wallet) 
            self.reset_open_buy_order(current_wallet)
            # Update wallet
            logger.info('    Wallet balance wallet before: %.2f',
                        current_wallet.balance)
            # Subtract cost of futures
            current_wallet.balance -= (float(entry_price) *
                                       float(executed_quantity) /
                                       current_wallet.leverage
                                       )
            # Subtract added margin
            current_wallet.balance -= current_wallet.margin_added
            logger.info('    Wallet balance wallet after (ignoring fees): '
                        '%.2f', current_wallet.balance)
        else:
            logger.warning('Buy order with ID %s has unknown '
                           'state %s [index=%d].',
                           buy_order_id, buy_order_status, wallet_idx)
            print(f'BUY ORDER {current_wallet.symbol} HAS UNKNOW STATUS {buy_order_status}')

    def check_status_of_all_buy_orders(self):
        for current_wallet in self.wallet_portfolio:

            # If there is no current buy order, skip
            if current_wallet.buy_order_id < 0:
                logger.info('No current open buy order for index=%d',
                            current_wallet.wallet_id)
                # return # no, process all other positions as well, since we got the expensive get_all_orders() info

            else:
                self.check_buy_order_status(current_wallet)

    def calculate_pnl(self, executed_quantity, sell_price, wallet):
        # See dev.binance.vision/t/pnl-manual-calculation/1723
        pnl = (float(executed_quantity) *
               wallet.entry_price *
               (1/wallet.leverage-1.) +
               float(sell_price) *
               float(executed_quantity)
               )
        print(f'QTY:{executed_quantity} ENTRY_PRICE:{wallet.entry_price} SELL PRICE:{sell_price} LEVERAGE:{wallet.leverage} --> PNL: {pnl:.2f}')
        return pnl

    def update_status_of_all_sell_orders(self):

        # Loop over current orders (stored in this instance)
        for current_wallet in self.wallet_portfolio:

            # If there is a current sell order
            if current_wallet.sell_order_id != -1:

                # Loop over all orders (from API)
                all_orders = self.status_of_all_binance_orders
                for order in all_orders:
                    # Match the two orders
                    if order['orderId'] == current_wallet.sell_order_id:
                        current_wallet.sell_order_status = order['status']
                        current_wallet.sell_order_executed_quantity = order['executedQty']
                        # sell order has no 'avgPrice'
   
    def get_filled_order_avg_price(self, wallet):
            all_orders= self._api.get_futures_all_orders()
            for order in all_orders:
                if order['orderId']== wallet.sell_order_id:
                    return order['avgPrice']
            
            print('FILLED SELL ORDER NOT FOUND !!!')
            logger.error('FILLED SELL ORDER NOT FOUND !!!')

    def check_sell_order_status(self, current_wallet):
        wallet_idx = current_wallet.wallet_id
        sell_order_id = current_wallet.sell_order_id
        sell_order_status = current_wallet.sell_order_status
        executed_quantity = current_wallet.buy_order_executed_quantity

        if sell_order_status == 'NEW':
            logger.info('Sell order with ID %s still open '
                        '[index=%d].',
                        sell_order_id, wallet_idx)
        elif sell_order_status == 'FILLED':
            # We won!
            # We get money
            # Update sell order
            print(f'*** {current_wallet.symbol} WON !!! ***')
            logger.info('Sell order withd ID %s filled '
                        '[index=%d].',
                        sell_order_id, wallet_idx)
            sell_price = self.get_filled_order_avg_price(current_wallet)
            self.reset_open_sell_order(current_wallet)

            # Update wallet
            logger.info('    Balance wallet before: %.2f',
                        current_wallet.wallet_id)

            current_wallet.balance += self.calculate_pnl(
                executed_quantity, sell_price, current_wallet)
            current_wallet.balance += current_wallet.margin_added
            logger.info('    Balance wallet after (ignoring fees): '
                        '%.2f', current_wallet.balance)
        elif sell_order_status == 'CANCELED':
            # Canceled, no money
            # Update sell order
            print(f'*** {current_wallet.symbol} CANCELED ***')
            logger.info('Sell order withd ID %s canceled '
                        '[index=%d].',
                        sell_order_id, wallet_idx)
            self.reset_open_sell_order(current_wallet)
        elif sell_order_status == 'EXPIRED':
            # We lost!
            # We lose money
            # Update sell order
            print(f'*** {current_wallet.symbol} LOST !!! ***')
            logger.info('Sell order with ID %s expired '
                        '[index=%d].',
                        sell_order_id, wallet_idx)
            self.reset_open_sell_order(current_wallet)
            # Update wallet
            logger.info('Wallet balance: %.2f',
                        current_wallet.balance)
            # See dev.binance.vision/t/pnl-manual-calculation/1723
            sell_price=current_wallet.liquidation_price
            current_wallet.balance += (  # += not -= because PNL value is already negative
                self.calculate_pnl(executed_quantity, sell_price, current_wallet))
            logger.info('Wallet after (ignoring fees): '
                        '%.2f', current_wallet.balance)
        else:
            # Update sell order
            print(f'BUY ORDER {current_wallet.symbol} HAS UNKNOW STATUS {sell_order_status}')
            logger.warning('Sell order with ID %s has unknown '
                           'state %s [index=%d].',
                           sell_order_id, sell_order_status, wallet_idx)
            logger.warning('Should I reset the open order?')

    def check_status_of_all_sell_orders(self):
        # Loop over current orders (stored in this instance)
        for current_wallet in self.wallet_portfolio:

            # If there is no current sell order, skip this wallet
            if current_wallet.sell_order_id == -1:
                logger.info('No current open sell order. index=%d',
                            current_wallet.wallet_id)

            # Loop over all orders (from API)
            # for order in all_orders:
            else:
                self.check_sell_order_status(current_wallet)

    def calculate_wallet_balance(self, wallet_size_percentage):
        _, account_free = self.get_account_balance('USDT')
        wallet_balance = trunc(account_free*wallet_size_percentage/100)
        return wallet_balance

    def print_info_of_all_wallets(self):
        for current_wallet in self.wallet_portfolio:
            current_wallet.print_wallet_info()


if __name__ == '__main__':

    # Create object
    loseitall = get_rich_quick_scheme()

    # --------------------------------------------------------------------------
    # Define investment
    wallet_ids = [111,222]
    # symbols = ['BTCUSDT', 'VETUSDT', 'ADAUSDT', 'ETHUSDT', 'XRPUSDT']
    symbols = ['ADAUSDT','ETHUSDT']
    wallet_size_percentages = [66,33]  # sum <= 100
    leverages = [20,20]  # leverage max. 20 for a new account
    # --------------------------------------------------------------------------

    # --------------------------------------------------------------------------
    # Turn off dry run
    loseitall.turn_off_dry_run()
    # --------------------------------------------------------------------------

    # Create wallets, and add them to wallet portfolio
    for idx, wallet_id in enumerate(wallet_ids):

        # Create wallet with id and symbol
        current_wallet = kelly_wallet(wallet_id, symbols[idx])

        # Add known parameters
        current_wallet.leverage = leverages[idx]
        current_wallet.balance = loseitall.calculate_wallet_balance(wallet_size_percentages[idx])
        current_wallet.initial_balance = current_wallet.balance

        # Add wallet to portfolio
        loseitall.add_wallet_to_portfolio(current_wallet)

    # Check if account balance is sufficient to host wallets
    loseitall.check_sufficient_account_balance()

    # --------------------------------------------------------------------------
    # DEBUG INFO
    # --------------------------------------------------------------------------
    # OUTPUT OF self.client.futures_position_information():
    # {'symbol': 'VETUSDT', 'positionAmt': '1660', 'entryPrice': '0.1327488795181', 'markPrice': '0.12813000', 'unRealizedProfit': '-7.66588000', 'liquidationPrice': '0.12743750', 'leverage': '20', 'maxNotionalValue': '25000', 'marginType': 'isolated', 'isolatedMargin': '3.26500776', 'isAutoAddMargin': 'false', 'positionSide': 'BOTH', 'notional': '212.69580000', 'isolatedWallet': '10.93088776', 'updateTime': 1629561601101} ...
    # --------------------------------------------------------------------------
    # OUTPUT OF self.client.futures_get_all_orders(): (gives a lot of output! output will increase over time)
    # {'orderId': 15891537505, 'symbol': 'ADAUSDT', 'status': 'FILLED', 'clientOrderId': 'LuiVoh74hPaAmqyBWrPcPH', 'price': '0', 'avgPrice': '2.49400', 'origQty': '103', 'executedQty': '103', 'cumQuote': '256.88200', 'timeInForce': 'GTC', 'type': 'MARKET', 'reduceOnly': False, 'closePosition': False, 'side': 'BUY', 'positionSide': 'BOTH', 'stopPrice': '0', 'workingType': 'CONTRACT_PRICE', 'priceProtect': False, 'origType': 'MARKET', 'time': 1629596414966, 'updateTime': 1629596414966} ...
    # --------------------------------------------------------------------------
    # OUTPUT OF self.client.futures_get_open_orders():
    # {'orderId': 16464950183, 'symbol': 'XRPUSDT', 'status': 'FILLED', 'clientOrderId': 'autoclose-1629544376210626761', 'price': '1.2176', 'avgPrice': '1.22490', 'origQty': '218', 'executedQty': '218', 'cumQuote': '267.02820', 'timeInForce': 'IOC', 'type': 'LIMIT', 'reduceOnly': False, 'closePosition': False, 'side': 'SELL', 'positionSide': 'BOTH', 'stopPrice': '0', 'workingType': 'CONTRACT_PRICE', 'priceProtect': False, 'origType': 'LIMIT', 'time': 1629544376213, 'updateTime': 1629544376213} ...
    # --------------------------------------------------------------------------

    # Go into an endless loop
    while True:

        try:
            # Log open positions and open orders
            loseitall.show_open_positions()
            loseitall.show_open_orders()

            # Get status of all binance orders
            loseitall.get_futures_all_orders()

            # Update status of all wallets with information from binance
            loseitall.update_status_of_all_buy_orders()
            loseitall.update_status_of_all_sell_orders()

            # Print info of all wallet objects in portfolio
            loseitall.print_info_of_all_wallets()

            # Check status of all current orders, reset them if necessary, and
            # update wallet
            loseitall.check_status_of_all_buy_orders()
            loseitall.check_status_of_all_sell_orders()
            # SELL_ORDER = FILLED  -> WE WON
            # SELL_ORDER = EXPIRED -> WE LOST

            # Place new bets on closed orders
            loseitall.place_new_kelly_bet_on_closed_orders()
   
        except Exception as error:
            error_message = 'CAUGHT AN ERROR IN THE MAIN LOOP !!!'
            print(error_message, error)
            logger.error('%s %s', error_message, error)

        sleep(60)
