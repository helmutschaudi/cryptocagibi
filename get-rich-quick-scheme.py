#!/usr/bin/env python3

import os
import logging
from datetime import datetime
from time import sleep
from binance.client import Client
from kellyBet import kellyBet


def setup_logger(name, log_file, level=logging.INFO):

    formatter = logging.Formatter('%(levelname)-8s - %(asctime)s - '
                                  '%(message)s')

    handler = logging.FileHandler(log_file)
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)

    return logger

# Configure logger
logger = setup_logger('default_logger', 'log.out')

class get_rich_quick_scheme():

    def __init__(self):

        self.api_key = os.environ.get('binance_api')
        self.api_secret = os.environ.get('binance_secret')

        self.client = Client(self.api_key, self.api_secret)
        self.dry_run = True

        # Create a dict of 2-tuples (key = symbol;
        #                            value = (price_precision,
        #                                     quantity_precision))
        self.symbol_precisions = {}
        futures_exchange_info = self.client.futures_exchange_info()
        for info in futures_exchange_info['symbols']:
            self.symbol_precisions[info['symbol']] = (info['pricePrecision'],
                                                      info['quantityPrecision']
                                                      )

        # Keep track of multiple buy and sell orders by dicts
        # self.order_ids is a dict of dicts, e.g.:
        # self.order_ids = {1: {'BUY': 1, 'SELL': 2}, 2: {'BUY': 9, 'SELL': 8}}
        # An order ID of -1  means there is no current order registered in the
        # system
        self.order_ids = {}

        # Keep track of multiple wallets by dicts
        # self.wallets is a dict, e.g.:
        # self.wallets = {1: 100, 2: 300}
        self.wallets = {}

        # Keep track of different entry prices
        # (needed when calculating profits)
        # self.entry_prices is a dict, e.g.:
        # self.entry_prices = {1: 1.10, 2: 7.70}
        self.entry_prices = {}

        # Keep track of different leverages
        # (needed when calculating profits)
        # self.leverages is a dict, e.g.:
        # self.leverages = {1: 100, 2: 125}
        self.leverages = {}

        # Keep track of different added margins
        # (needed when calculating profits)
        # self.margins_added is a dict, e.g.:
        # self.margins_added = {1: 0, 2: 6.66}
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

    def initialize_wallets(self, idxs, wallets):
        assert len(idxs) == len(wallets), 'When initializing wallets, '
        'you should define as many wallets as indexes.'
        for idx, _ in enumerate(idxs):
            self.wallets[idxs[idx]] = wallets[idx]
        self.check_wallets()

    def get_total_index_wallets(self):
        total = 0
        for _, value in self.wallets.items():
            total += value
        return total

    def check_wallets(self):
        _, wallet_free = self.get_balance('USDT')
        if self.get_total_index_wallets() > wallet_free:
            logger.error('The total of requested index wallets is higher '
                          'than your free wallet: %.2f > %.2f',
                          self.get_total_index_wallets(), wallet_free)
            raise ValueError('Not enough money.')
        logger.info('Total index wallets balance: %.2f',
                     self.get_total_index_wallets())
        logger.info('Total free wallet balance: %.2f',
                     wallet_free)

    def check_open_order(self, idx):
        try:
            # If order IDs are -1, there are no current orders for a given
            # index
            if self.order_ids[idx]['BUY'] < 0 and \
               self.order_ids[idx]['SELL'] < 0:
                logger.info('No current orders found. [index=%d]', idx)
                return False
        except KeyError:
            # If order IDs are unset, there are no current orders for a given
            # index
            return False

        # If we reach here, order IDs are both set and positive,
        # which means we have valid current orders
        logger.info('Current BUY order ID: %s [index=%d]',
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

    def get_balance(self, asset):
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

    def place_kelly_bet(self, symbol, leverage, idx):

        # Store leverage
        self.leverages[idx] = leverage

        # Set margin type and leverage
        # self.client.futures_change_margin_type(symbol=symbol,
        #                                        marginType='ISOLATED')
        self.client.futures_change_leverage(symbol=symbol, leverage=leverage)

        logger.info('Placing Kelly bet for %s [index=%d].', symbol, idx)
        logger.info('Kelly options:')
        price_market = float(self.client.futures_position_information
                             (symbol=symbol)[0]['markPrice'])
        wallet_total, wallet_free = self.get_balance('USDT')
        logger.info('    Wallet total: %.2f', wallet_total)
        logger.info('    Wallet free: %.2f', wallet_free)
        logger.info('    Wallet index: %.2f', self.wallets[idx])
        logger.info('    Market price: %.2f', price_market)
        logger.info('    Leverage: %d', leverage)

        myBet = kellyBet(self.wallets[idx], price_market, leverage)
        # myBet.kellyBet(1.2, 1.)
        myBet.kellyBet(1.4, 5.)
        # myBet.kellyBet(3.5, 2.)
        logger.info('    Bet size: %s', myBet.f)
        logger.info('    Gross odds: %s', myBet.b)

        logger.info('Kelly plan:')

        # Get significant figures right for Binance API
        futures_buy = float('%s' %
                            float(f'%.{self.symbol_precisions[symbol][1]}g' %
                                  myBet.futures_buy))
        futures_sell = float('%s' %
                             float(f'%.{self.symbol_precisions[symbol][1]}g' %
                                   myBet.futures_sell))
        price_old = float('%s' %
                          float(f'%.{self.symbol_precisions[symbol][0]}g' %
                                myBet.price_old))
        price_new = float('%s' %
                          float(f'%.{self.symbol_precisions[symbol][0]}g' %
                                myBet.price_new))

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

        # Place sell order
        logger.info('    Sell %s futures at %s (+%.1f %%), get %s, '
                     'gain %s (+%.1f %% / ROE: +%.1f %%).',
                     futures_sell, price_new,
                     100*price_new/price_old-100,
                     myBet.asset_new, myBet.gain,
                     100*myBet.gain/myBet.asset_total,
                     100*myBet.gain/myBet.asset_old)
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

        # Info about liquidation
        logger.info('    Or %s futures are liquidated at ~%s (%.1f %%), '
                     'lose %s (-100.0 %% / ROE: -%.2f %%).',
                     futures_sell, myBet.price_liq,
                     100*myBet.price_liq/price_old-100,
                     myBet.asset_total,
                     100*myBet.asset_total/myBet.asset_old)

    def check_buy_order_status(self):

        all_orders = self.client.futures_get_all_orders()
        # Loop over current orders (stored in this instance)
        for idx, order_id in self.order_ids.items():

            # If there is no current buy order, skip
            if self.order_ids[idx]['BUY'] < 0:
                logger.info('No current open buy order.')
                return

            # Loop over all orders (from API)
            for order in all_orders:
                # Match the two orders
                if order['orderId'] == order_id['BUY']:

                    # Log order
                    logger.debug(order)

                    # We found the current order for a given index
                    # Now check status
                    if order['status'] == 'NEW':
                        logger.info('Buy order with ID %s still open '
                                     '[index=%d].',
                                     order_id['BUY'], idx)
                    elif order['status'] == 'FILLED':
                        # Bought, we have to pay money
                        # Update buy order
                        logger.info('Buy order withd ID %s filled at %.2f '
                                     '[index=%d].',
                                     order_id['BUY'],
                                     float(order['avgPrice']),
                                     idx)
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

    def check_sell_order_status(self):

        all_orders = self.client.futures_get_all_orders()
        # Loop over current orders (stored in this instance)
        for idx, order_id in self.order_ids.items():

            # If there is no current sell order, skip
            if self.order_ids[idx]['SELL'] < 0:
                logger.info('No current open sell order.')
                return

            # Loop over all orders (from API)
            for order in all_orders:
                # Match the two orders
                if order['orderId'] == order_id['SELL']:

                    # Log order
                    logger.debug(order)

                    # We found the current order for a given index
                    # Now check status
                    if order['status'] == 'NEW':
                        logger.info('Sell order with ID %s still open '
                                     '[index=%d].',
                                     order_id['SELL'], idx)
                    elif order['status'] == 'FILLED':
                        # Sold, we get money
                        # Update sell order
                        logger.info('Sell order withd ID %s filled '
                                     '[index=%d].',
                                     order_id['SELL'], idx)
                        self.reset_open_sell_order(idx)

                        # Update wallet
                        logger.info('    Index wallet before: %.2f',
                                     self.wallets[idx])
                        # See dev.binance.vision/t/pnl-manual-calculation/1723
                        self.wallets[idx] += (float(order['executedQty']) *
                                              self.entry_prices[idx] *
                                              (1/self.leverages[idx]-1.) +
                                              float(order['avgPrice']) *
                                              float(order['executedQty'])
                                              )
                        self.wallets[idx] += self.margins_added[idx]
                        logger.info('    Index wallet after (ignoring fees): '
                                     '%.2f', self.wallets[idx])
                    elif order['status'] == 'CANCELED':
                        # Canceled, no money
                        # Update sell order
                        logger.info('Sell order withd ID %s canceled '
                                     '[index=%d].',
                                     order_id['SELL'], idx)
                        self.reset_open_sell_order(idx)
                    elif order['status'] == 'EXPIRED':
                        # Liquidated, we lose money
                        # Update sell order
                        logger.info('Sell order with ID %s expired '
                                     '[index=%d].',
                                     order_id['SELL'], idx)
                        self.reset_open_sell_order(idx)
                        # Update wallet
                        logger.info('Index wallet before: %.2f',
                                     self.wallets[idx])
                        # See dev.binance.vision/t/pnl-manual-calculation/1723
                        self.wallets[idx] -= (float(order['executedQty']) *
                                              self.entry_prices[idx] *
                                              (1/self.leverages[idx]-1.) +
                                              float(order['avgPrice']) *
                                              float(order['executedQty'])
                                              )
                        logger.info('Index wallet after (ignoring fees): '
                                     '%.2f', self.wallets[idx])
                    else:
                        # Update sell order
                        logger.warning('Sell order with ID %s has unknown '
                                        'state %s [index=%d].',
                                        order_id['SELL'], order['status'], idx)
                        logger.warning('Should I reset the open order?')


if __name__ == '__main__':

    # Variables
    # idxs = [55, 77, 99]
    # symbols = ['ETHUSDT', 'BTCUSDT', 'SOLUSDT']
    # wallets = [50, 50, 50]
    # leverages = [100, 125, 50]
    idxs = [55, 77]
    symbols = ['VETUSDT', 'ADAUSDT']
    wallets = [100, 100]
    leverages = [50, 50]

    # Create object
    loseitall = get_rich_quick_scheme()

    # Turn off dry run
    loseitall.turn_off_dry_run()

    # Initialize wallets
    loseitall.initialize_wallets(idxs, wallets)

    # Go into an endless loop
    while True:

        # Get number of open positions and open orders
        nOpenPositions = loseitall.show_open_positions()
        nOpenOrders = loseitall.show_open_orders()

        # Check status of all current orders, reset them if necessary, and
        # update wallet
        loseitall.check_buy_order_status()
        loseitall.check_sell_order_status()

        # Place several bets
        for i in range(len(idxs)):

            # Get variables
            idx = idxs[i]
            symbol = symbols[i]
            wallet = wallets[i]
            leverage = leverages[i]

            # Check if we have current orders
            if not loseitall.check_open_order(idx):

                # If we don't have current orders, place a new one
                loseitall.place_kelly_bet(symbol, leverage, idx)

        # If we don't have open positions nor orders,
        # we want to place a new bet
        # if nOpenPositions+nOpenOrders == 0:
        # #if True:
        #    loseitall.place_kelly_bet('ETHUSDT', 100)

        sleep(60)

    # print(client.get_account())
    # print(client.get_asset_balance(asset='ETH'))
    # print(client.get_margin_account())
    # print(client.get_symbol_ticker(symbol="ETHUSDT"))
    # print(client.get_symbol_info(symbol="ETHUSDT"))
    # print(client.get_open_orders())
    # print(client.futures_account())
    # print(client.futures_account_balance())
    # print(client.futures_account_trades())
    # print(client.futures_get_open_orders())
    # print(client.futures_get_all_orders())
    # print(client.futures_get_open_orders()[0]['price'])
    # print(client.futures_get_all_orders())
