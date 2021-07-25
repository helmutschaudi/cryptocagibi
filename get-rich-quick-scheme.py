#!/usr/bin/env python3

import sys, os, logging
from datetime import datetime
from time import sleep
from binance.client import Client
from kellyBet import kellyBet


class get_rich_quick_scheme():

    def __init__(self):

        self.api_key = os.environ.get('binance_api')
        self.api_secret = os.environ.get('binance_secret')

        self.client = Client(self.api_key, self.api_secret)
        self.dry_run = True

        # Create a dict of 2-tuples (key = symbol;
        #                            value = (price_precision, quantity_precision))
        self.symbol_precisions = {}
        futures_exchange_info = self.client.futures_exchange_info()
        for info in futures_exchange_info['symbols']:
            self.symbol_precisions[info['symbol']] = (info['pricePrecision'],
                                                      info['quantityPrecision']
                                                     )

        # Keep track of multiple buy and sell orders by dicts
        # self.order_ids is a dict of dicts, e.g.:
        # self.order_ids = {1: {'BUY': 1, 'SELL': 2}, 2: {'BUY': 98, 'SELL': 99}}
        # An order ID of -1  means there is no current order registered in the
        # system
        self.order_ids = {}

    def config_logger(self):
        logging.basicConfig(level=logging.INFO,
                            #format='%(name)s - %(levelname)8s - %(asctime)s - %(message)s',
                            format='%(levelname)-8s - %(asctime)s - %(message)s',
                            datefmt='%Y-%m-%d %H:%M:%S')

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
        assert len(idxs) == len(wallets), "When initializing wallets, you should define as many wallets as indexes."
        for idx, _ in enumerate(idxs):
            self.wallets[idxs[idx]] = wallets[idx]

    def check_open_order(self, idx):
        try:
            # If order IDs are -1, there are no current orders for a given
            # index
            if self.order_ids[idx]['BUY'] < 0 and \
               self.order_ids[idx]['SELL'] < 0:
                logging.info('No current orders found. [index=%d]', idx)
                return False
        except KeyError:
            # If order IDs are unset, there are no current orders for a given
            # index
            return False

        # If we reach here, order IDs are both set and positive,
        # which means we have valid current orders
        logging.info('Current BUY order ID: %s [index=%d]',
                     self.order_ids[idx]['BUY'], idx)
        logging.info('Current SELL order ID: %s [index=%d]',
                     self.order_ids[idx]['SELL'], idx)
        return True

    def reset_open_order(self, idx):
        logging.info('Reset BUY order ID %s [index=%d].',
                     self.order_ids[idx]['BUY'], idx)
        logging.info('Reset SELL order ID %s [index=%d].',
                     self.order_ids[idx]['SELL'], idx)
        self.order_ids[idx]['BUY'] = self.order_ids[idx]['SELL'] = -1

    def turn_off_dry_run(self):
        self.dry_run = False

    def get_balance(self, asset):
        for account in self.client.futures_account_balance():
            if account['asset'] == asset:
                return float(account['balance']), float(account['withdrawAvailable'])

    def get_max_leverage(self, symbol):
        return int(self.client.futures_leverage_bracket(symbol=symbol)[0]['brackets'][0]['initialLeverage'])

    def show_open_positions(self):

        # Get data
        open_positions = []
        for position in self.client.futures_position_information():
            if float(position['positionAmt']) != 0.:
                open_positions.append(position)

        logging.info('Number of open positions: %d', len(open_positions))

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

            logging.info('--> Symbol: %s', symbol)
            logging.info('    Leverage: %d/%d', leverage, leverage_max)
            logging.info('    Entry price: %.2f', price_entry)
            logging.info('    Market price: %.2f', price_market)
            logging.info('    PNL: %.2f', pnl)
            logging.info('    ROE: %.2f %%', roe)
            logging.info('    Initial margin: %.2f', margin_initial)
            logging.info('    Total margin: %.2f', margin_total)
            logging.info('    Margin type: %s', margin_type)
            logging.info('    Liquidation price: %.2f', price_liq)
            logging.info('    Quantity: %.3g', quantity)
            logging.info('    Time of request: %s', time)

        return len(open_positions)


    def show_open_orders(self):
        # Get data
        open_orders = self.client.futures_get_open_orders()

        logging.info('Number of open orders: %d', len(open_orders))

        # If there are open orders, output some info, otherwise do nothing
        for open_order in open_orders:

            # Collect info
            symbol = open_order['symbol']
            price_market = float(self.client.futures_mark_price(symbol=symbol)['markPrice'])
            price_sell = float(open_order['price'])
            quantity = float(open_orders[0]['origQty'])
            time_placement = (datetime
                             .fromtimestamp(open_order['time']/1000.)
                             .strftime('%Y-%m-%d %H:%M:%S.%f')
                            )
            client_order_id = open_order['clientOrderId']

            logging.info('--> Symbol: %s', symbol)
            logging.info('    Market price: %.2f', price_market)
            logging.info('    Sell price: %.2f', price_sell)
            logging.info('    Quantity: %.3g', quantity)
            logging.info('    Time of placement: %s', time_placement)
            logging.info('    Client Order ID: %s', client_order_id)

        return len(open_orders)

    def place_kelly_bet(self, symbol, leverage, idx):

        # Set margin type and leverage
        #self.client.futures_change_margin_type(symbol=symbol, marginType='ISOLATED')
        self.client.futures_change_leverage(symbol=symbol, leverage=leverage)

        logging.info('Placing Kelly bet for %s [index=%d].', symbol, idx)
        logging.info('Kelly options:')
        wallet_total, wallet_free = self.get_balance('USDT')
        price_market = float(self.client.futures_position_information(symbol=symbol)[0]['markPrice'])
        logging.info('    Wallet total: %.2f', wallet_total)
        logging.info('    Wallet free: %.2f', wallet_free)
        logging.info('    Market price: %.2f', price_market)
        logging.info('    Leverage: %d', leverage)

        myBet = kellyBet(wallet_free, price_market, leverage)
        myBet.kellyBet(1.4, 5.)
        #myBet.kellyBet(3.5, 2.)
        logging.info('    Bet size: %s', myBet.f)
        logging.info('    Gross odds: %s', myBet.b)

        logging.info('Kelly plan:')

        # Get precisions right for Binance API
        futures_buy = round(myBet.futures_buy,
                            self.symbol_precisions[symbol][1])
        futures_sell = round(myBet.futures_sell,
                             self.symbol_precisions[symbol][1])
        price_old = round(myBet.price_old,
                          self.symbol_precisions[symbol][0])
        price_new = round(myBet.price_new,
                          self.symbol_precisions[symbol][0])

        # Buy futures
        logging.info('    Buy %s futures at %s, pay initial margin %s.',
                     futures_buy, price_old, myBet.asset_old)
        if not self.dry_run:
            response = self.client.futures_create_order(symbol=symbol,
                                                        side='BUY',
                                                        type='MARKET',
                                                        quantity=futures_buy
                                                       )
            self.set_buy_order_id(idx, buy_id = response['orderId'])
            logging.info('    BUY order ID: %s', self.order_ids[idx]['BUY'])
        else:
            logging.warning('Dry run, do not actually buy anything.')

        # Add margin
        logging.info('    Add margin %s, pay total %s.',
                     myBet.margin_add, myBet.asset_total)
        if not self.dry_run:
            response = self.client.futures_change_position_margin(symbol=symbol,
                                                                  amount=myBet.margin_add,
                                                                  type=1
                                                                 )

        # Place sell order
        logging.info('    Sell %s futures at %s (+%.1f %%), get %s, gain %s (+%.1f %% / ROE: +%.1f %%).',
                     futures_sell, price_new,
                     100*price_new/price_old-100,
                     myBet.asset_new, myBet.gain,
                     100*myBet.gain/myBet.asset_total,
                     100*myBet.gain/myBet.asset_old)
        if not self.dry_run:
            response = self.client.futures_create_order(symbol=symbol,
                                                        side='SELL',
                                                        type='LIMIT',
                                                        quantity=futures_sell,
                                                        timeInForce='GTC', # Good til canceled
                                                        price=price_new
                                                       )
            self.set_sell_order_id(idx, sell_id = response['orderId'])
            logging.info('    SELL order ID: %s', self.order_ids[idx]['SELL'])

        # Info about liquidation
        logging.info('    Or %s futures are liquidated at ~%s (%.1f %%), lose %s (-100.0 %% / ROE: -%.2f %%).',
                     futures_sell, myBet.price_liq,
                     100*myBet.price_liq/price_old-100,
                     myBet.asset_total,
                     100*myBet.asset_total/myBet.asset_old)

    def check_sell_order_status(self):

        all_orders = looseitall.client.futures_get_all_orders()
        # Loop over current orders (stored in this instance)
        for idx, order_id in self.order_ids.items():
            # Loop over all orders (from API)
            for order in all_orders:
                # Match the two orders
                if order['orderId'] == order_id['SELL']:

                    # We found the current order for a given index
                    # Now check status
                    if order['status'] == 'NEW':
                        logging.info('Sell order with ID %s still open [index=%d].',
                                     order_id['SELL'], idx)
                    elif order['status'] == 'FILLED':
                        logging.info('Sell order withd ID %s filled [index=%d].',
                                     order_id['SELL'], idx)
                        self.reset_open_order(idx)
                    elif order['status'] == 'CANCELED':
                        logging.info('Sell order withd ID %s canceled [index=%d].',
                                     order_id['SELL'], idx)
                        self.reset_open_order(idx)


if __name__ == '__main__':

    # Variables
    leverage = 100
    idxs = [55, 77, 99]
    wallets = [100, 100, 200]

    # Create object
    looseitall = get_rich_quick_scheme()

    # Configure logger
    looseitall.config_logger()

    # Turn off dry run
    looseitall.turn_off_dry_run()

    # Go into an endless loop
    while True:

        # Get number of open positions and open orders
        nOpenPositions = looseitall.show_open_positions()
        nOpenOrders = looseitall.show_open_orders()

        # Check status of all current orders and reset them if necessary
        looseitall.check_sell_order_status()

        # Place several bets
        for idx in idxs:

            # Check if we have current orders
            if not looseitall.check_open_order(idx):

                # If we don't have current orders, place a new one
                looseitall.place_kelly_bet('ETHUSDT', leverage, idx)

        ## If we don't have open positions nor orders, we want to place a new bet
        #if nOpenPositions+nOpenOrders == 0:
        ##if True:
        #    looseitall.place_kelly_bet('ETHUSDT', 100)

        sleep(60)

    #print(client.get_account())
    #print(client.get_asset_balance(asset='ETH'))
    #print(client.get_margin_account())
    #print(client.get_symbol_ticker(symbol="ETHUSDT"))
    #print(client.get_symbol_info(symbol="ETHUSDT"))
    #print(client.get_open_orders())
    #print(client.futures_account())
    #print(client.futures_account_balance())
    #print(client.futures_account_trades())
    #print(client.futures_get_open_orders())
    #print(client.futures_get_all_orders())
    #print(client.futures_get_open_orders()[0]['price'])
    #print(client.futures_get_all_orders())
