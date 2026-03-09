from AlgorithmImports import *
import json


class SignalStackBridge:
    def __init__(self, algorithm, config):
        self.algo = algorithm
        self.config = config

    def send(self, symbol: str, action: str, quantity: int):
        if not self.config.SS_ENABLED:
            self.algo.debug(f"[SS_DISABLED] {action} {quantity} {symbol}")
            return

        payload = json.dumps({
            "symbol": symbol,
            "action": action,
            "quantity": quantity
        })

        url = self.config.SS_LIVE_URL if self.config.SS_LIVE_URL else self.config.SS_PAPER_URL
        self.algo.notify.web(url, payload)
        self.algo._log(f"[SS_SENT] {action} {quantity} {symbol}")
