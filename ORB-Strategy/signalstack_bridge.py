from AlgorithmImports import *
import json
import socket
import http.client
import ssl
import threading


class SignalStackBridge:
    def __init__(self, algorithm, config):
        self.algo = algorithm
        self.config = config

    def send(self, symbol: str, action: str, quantity: int):
        """Fire-and-forget send, or delegate to confirm-first when active."""
        if self.config.SS_ENABLED and self.config.SS_CONFIRM_FIRST:
            self.send_and_confirm(symbol, action, quantity)
            return

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

    def _http_post(self, url, payload, timeout, result):
        """Worker function that runs in a thread. Stores result in result[0]."""
        conn = None
        try:
            clean = url.replace("https://", "").replace("http://", "")
            slash_idx = clean.find("/")
            if slash_idx == -1:
                host = clean
                path = "/"
            else:
                host = clean[:slash_idx]
                path = clean[slash_idx:]

            is_https = url.startswith("https://")

            if is_https:
                ctx = ssl.create_default_context()
                conn = http.client.HTTPSConnection(host, timeout=timeout, context=ctx)
            else:
                conn = http.client.HTTPConnection(host, timeout=timeout)

            conn.request("POST", path, body=payload,
                         headers={"Content-Type": "application/json"})
            resp = conn.getresponse()
            raw = resp.read().decode("utf-8")
            result[0] = ("ok", raw)

        except Exception as e:
            result[0] = ("error", f"{type(e).__name__}: {e}")

        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def send_and_confirm(self, symbol: str, action: str, quantity: int) -> tuple:
        """
        Synchronous POST to SignalStack with hard thread-based timeout.
        Returns (success, response_data).
        success: True only if broker status == "filled".
        """
        if not self.config.SS_ENABLED:
            return (True, {"status": "backtest"})

        payload = json.dumps({
            "symbol": symbol,
            "action": action,
            "quantity": quantity
        })

        url = self.config.SS_LIVE_URL if self.config.SS_LIVE_URL else self.config.SS_PAPER_URL
        if not url:
            self.algo._log(f"[SS_ERROR] No webhook URL configured")
            return (False, {"status": "ConfigError", "message": "No SS URL configured"})

        timeout = self.config.SS_TIMEOUT_SECONDS

        # Run HTTP call in a thread with hard timeout — prevents hanging the event loop
        result = [None]
        t = threading.Thread(target=self._http_post, args=(url, payload, timeout, result), daemon=True)
        t.start()
        t.join(timeout=timeout + 2)  # Give 2 extra seconds beyond socket timeout

        if t.is_alive() or result[0] is None:
            self.algo._log(f"[SS_TIMEOUT] {action} {quantity} {symbol} — thread exceeded {timeout}s, blocking entry")
            return (False, {"status": "Timeout", "message": f"Thread exceeded {timeout}s"})

        status, data = result[0]

        if status == "error":
            self.algo._log(f"[SS_ERROR] {action} {quantity} {symbol} — {data}")
            return (False, {"status": "Error", "message": data})

        # Parse response JSON
        try:
            response_data = json.loads(data)
        except json.JSONDecodeError:
            self.algo._log(f"[SS_PARSE_ERROR] {action} {quantity} {symbol} — bad JSON: {data[:200]}")
            return (False, {"status": "ParseError", "message": data[:200]})

        if response_data.get("status") == "filled":
            self.algo._log(f"[SS_CONFIRMED] {action} {quantity} {symbol} — {response_data}")
            return (True, response_data)
        else:
            self.algo._log(f"[SS_REJECTED] {action} {quantity} {symbol} — {response_data}")
            return (False, response_data)

    def get_fill_price(self, response_data: dict) -> float:
        """Extract fill price from SS response, or 0.0 if unavailable."""
        try:
            return float(response_data.get("price", 0))
        except (ValueError, TypeError):
            return 0.0
