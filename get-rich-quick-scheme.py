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

    def config_logger(self):
        logging.basicConfig(level=logging.INFO,
                            #format='%(name)s - %(levelname)7s - %(asctime)s - %(message)s',
                            format='%(levelname)-7s - %(asctime)s - %(message)s',
                            datefmt='%Y-%m-%d %H:%M:%S')

    def turn_off_dry_run(self):
        self.dry_run = False

    def get_balance(self, asset):
        for account in self.client.futures_account_balance():
            if account['asset'] == asset:
                return account['balance']

    def get_max_leverage(self, symbol):
        return int(self.client.futures_leverage_bracket(symbol='ETHUSDT')[0]['brackets'][0]['initialLeverage'])

    def show_open_positions(self):

        # Get data
        open_positions = []
        for position in self.client.futures_position_information():
            if float(position['positionAmt']) != 0.:
                open_positions.append(position)

        logging.info('Number of open positions: %d' % len(open_positions))

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

            logging.info('    Symbol: %s', symbol)
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

        logging.info('Number of open orders: %d' % len(open_orders))

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

            logging.info('    Symbol: %s', symbol)
            logging.info('    Market price: %.2f', price_market)
            logging.info('    Sell price: %.2f', price_sell)
            logging.info('    Quantity: %.3g', quantity)
            logging.info('    Time of placement: %s', time_placement)
            logging.info('    Client Order ID: %s', client_order_id)

        return len(open_orders)

    def place_new_kelly_bet(self, symbol, leverage):

        logging.info('No open positions nor orders found. Placing Kelly bet for %s.', symbol)
        logging.info('Kelly options:')
        wallet = float(self.get_balance('USDT'))
        price_market = float(self.client.futures_position_information(symbol=symbol)[0]['markPrice'])
        logging.info('    Wallet: %.2f', wallet)
        logging.info('    Market price: %.2f', price_market)
        logging.info('    Leverage: %d', leverage)

        myBet = kellyBet(wallet, price_market, leverage)
        myBet.kellyBet(1.4, 5.)
        #myBet.kellyBet(3.5, 2.)
        logging.info('    Bet size: %s', myBet.f)
        logging.info('    Gross odds: %s', myBet.b)

        logging.info('Kelly plan:')

        # Buy futures
        logging.info('    Buy %s futures at %s, pay initial margin %s.',
                     myBet.futures_buy, myBet.price_old, myBet.asset_old)
        if not self.dry_run:
            self.client.futures_create_order(symbol=symbol,
                                             side='BUY',
                                             type='MARKET',
                                             quantity=myBet.futures_buy
                                            )

        # Add margin
        logging.info('    Add margin %s, pay total %s.',
                     myBet.margin_add, myBet.asset_total)
        if not self.dry_run:
            self.client.futures_change_position_margin(symbol=symbol,
                                                       amount=myBet.margin_add,
                                                       type=1
                                                      )

        # Place sell order
        logging.info('    Sell %s futures at %s (+%.1f %%), get %s, gain %s (+%.1f %% / ROE: +%.1f %%).',
                     myBet.futures_sell, myBet.price_new,
                     100*myBet.price_new/myBet.price_old-100,
                     myBet.asset_new, myBet.gain,
                     100*myBet.gain/myBet.asset_total,
                     100*myBet.gain/myBet.asset_old)
        if not self.dry_run:
            self.client.futures_create_order(symbol=symbol,
                                             side='SELL',
                                             type='LIMIT',
                                             quantity=myBet.futures_sell,
                                             timeInForce='GTC', # Good til canceled
                                             price=myBet.price_new
                                            )

        # Info about liquidation
        logging.info('    Or %s futures are liquidated at ~%s (%.1f %%), lose %s (-100.0 %% / ROE: -%.2f %%).',
                     myBet.futures_sell, myBet.price_liq,
                     100*myBet.price_liq/myBet.price_old-100,
                     myBet.asset_total,
                     100*myBet.asset_total/myBet.asset_old)


if __name__ == '__main__':

    looseitall = get_rich_quick_scheme()
    looseitall.config_logger()
    looseitall.turn_off_dry_run()

    while True:
        nOpenPositions = looseitall.show_open_positions()
        nOpenOrders = looseitall.show_open_orders()

        # If we don't have open positions nor orders, we want to place a new bet
        if nOpenPositions+nOpenOrders == 0:
            looseitall.place_new_kelly_bet('ETHUSDT', 100)

        sleep(60)

    #print(client.get_account())
    #print(client.get_asset_balance(asset='ETH'))
    #print(client.get_margin_account())
    #print(client.get_symbol_ticker(symbol="ETHUSDT"))
    #print(client.get_open_orders())
    #print(client.futures_account())
    #print(client.futures_account_balance())
    #print(client.futures_account_trades())
    #print(client.futures_get_open_orders())
    #print(client.futures_get_all_orders())
    #print(client.futures_get_open_orders()[0]['price'])
