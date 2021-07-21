#!/usr/bin/env python3

import sys

def kellyBet(b, margin_factor):

    # See https://en.wikipedia.org/wiki/Kelly_criterion#Statement
    # f = p - (1-p)/(b-1)
    # where:
    # f: bet size
    # p: probability of a win
    # b: gross odds received including wager
    #
    # Fix: b = 1.4
    # Assume: p = 0.75
    #         (this is an assumption and would need to be calculated by
    #          analyzing historical data)
    # ==> f = .125

    f = .125

    bankroll = float(sys.argv[1])
    price_old = float(sys.argv[2])
    multiplier = float(sys.argv[3])
    asset_old = bankroll*f/margin_factor
    margin_add = bankroll*f-asset_old
    asset_total = asset_old+margin_add
    futures_buy = asset_old/(price_old/multiplier)
    gain = asset_total*b-asset_total
    price_new = price_old+gain/futures_buy
    futures_sell = futures_buy
    asset_new = (margin_add+asset_old)*b
    price_liq = price_old-asset_total/futures_buy

    print(f'Bet size: {f}')
    print(f'Gross odds: {b}')
    print(f'Buy {round(futures_buy, 3)} futures at {round(price_old, 5)}, pay initial margin {round(asset_old, 2)}.')
    print(f'Add margin {round(margin_add, 2)}, pay total {round(asset_total, 2)}.')
    print(f'Sell {round(futures_sell, 3)} futures at {round(price_new, 5)} (+{round(100*price_new/price_old-100, 2)} %), get {round(asset_new, 2)}, gain {round(gain, 2)} (+{round(100*gain/asset_total, 2)} % / ROE: +{round(100*gain/asset_old, 2)} %).')
    print(f'Or {round(futures_sell, 3)} futures are liquidated at ~{round(price_liq, 5)} ({round(100*price_liq/price_old-100, 2)} %), lose {round(asset_total, 2)} (-100.0 % / ROE: -{round(100*asset_total/asset_old, 2)} %).')

if __name__ == '__main__':

    kellyBet(1.4, 5.)
    kellyBet(3.5, 2.)