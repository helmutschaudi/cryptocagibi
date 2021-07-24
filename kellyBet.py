#!/usr/bin/env python3

import sys

class kellyBet:

    def __init__(self, bankroll, price_old, multiplier):
        self._bankroll = bankroll
        self._price_old = price_old
        self._multiplier = multiplier

    def kellyBet(self, b, margin_factor):

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

        self._f = .125
        self._b = b
        self._margin_factor = margin_factor
        self._asset_old = self._bankroll*self._f/self._margin_factor
        self._margin_add = self._bankroll*self._f-self._asset_old
        self._asset_total = self._asset_old+self._margin_add
        self._futures_buy = self._asset_old/(self._price_old/self._multiplier)
        self._gain = self._asset_total*self._b-self._asset_total
        self._price_new = self._price_old+self._gain/self._futures_buy
        self._futures_sell = self._futures_buy
        self._asset_new = (self._margin_add+self._asset_old)*self._b
        self._price_liq = self._price_old-self._asset_total/self._futures_buy

    def kellyBetInfo(self):

        print(f'Bet size: {self._f}')
        print(f'Gross odds: {self._b}')
        print(f'Buy {round(self._futures_buy, 3)} futures at {round(self._price_old, 5)}, pay initial margin {round(self._asset_old, 2)}.')
        print(f'Add margin {round(self._margin_add, 2)}, pay total {round(self._asset_total, 2)}.')
        print(f'Sell {round(self._futures_sell, 3)} futures at {round(self._price_new, 5)} (+{round(100*self._price_new/self._price_old-100, 2)} %), get {round(self._asset_new, 2)}, gain {round(self._gain, 2)} (+{round(100*self._gain/self._asset_total, 2)} % / ROE: +{round(100*self._gain/self._asset_old, 2)} %).')
        print(f'Or {round(self._futures_sell, 3)} futures are liquidated at ~{round(self._price_liq, 5)} ({round(100*self._price_liq/self._price_old-100, 2)} %), lose {round(self._asset_total, 2)} (-100.0 % / ROE: -{round(100*self._asset_total/self._asset_old, 2)} %).')

    @property
    def f(self):
        return float(f'{float(f"{self._f:.3g}"):g}')

    @property
    def b(self):
        return float(f'{float(f"{self._b:.3g}"):g}')

    @property
    def futures_buy(self):
        return float(f'{float(f"{self._futures_buy:.3g}"):g}')

    @property
    def futures_sell(self):
        return float(f'{float(f"{self._futures_sell:.3g}"):g}')

    @property
    def price_old(self):
        return float(f'{float(f"{self._price_old:.6g}"):g}')

    @property
    def price_new(self):
        return float(f'{float(f"{self._price_new:.6g}"):g}')

    @property
    def price_liq(self):
        return float(f'{float(f"{self._price_liq:.6g}"):g}')

    @property
    def asset_old(self):
        return float(f'{float(f"{self._asset_old:.4g}"):g}')

    @property
    def asset_new(self):
        return float(f'{float(f"{self._asset_new:.4g}"):g}')

    @property
    def asset_total(self):
        return float(f'{float(f"{self._asset_total:.4g}"):g}')

    @property
    def margin_add(self):
        return float(f'{float(f"{self._margin_add:.4g}"):g}')

    @property
    def gain(self):
        return float(f'{float(f"{self._gain:.4g}"):g}')

if __name__ == '__main__':

    myBet = kellyBet(float(sys.argv[1]), float(sys.argv[2]), float(sys.argv[3]))
    myBet.kellyBet(1.4, 5.)
    myBet.kellyBetInfo()
    myBet.kellyBet(3.5, 2.)
    myBet.kellyBetInfo()
