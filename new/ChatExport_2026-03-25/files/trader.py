import os
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType
from py_clob_client.constants import POLYGON
from logger import log, send_telegram
import time

HOST = "https://clob.polymarket.com"

# Simple rate limiting
LAST_API_CALL_TIME = 0
API_CALL_INTERVAL = 1 # seconds

def init_client() -> ClobClient:
    key = os.getenv("POLYGON_WALLET_PRIVATE_KEY")
    client = ClobClient(HOST, key=key, chain_id=POLYGON)
    client.set_api_creds(client.create_or_derive_api_creds())
    return client


def _rate_limited_post_order(client: ClobClient, signed_order, order_type):
    global LAST_API_CALL_TIME
    current_time = time.time()
    time_since_last_call = current_time - LAST_API_CALL_TIME

    if time_since_last_call < API_CALL_INTERVAL:
        sleep_time = API_CALL_INTERVAL - time_since_last_call
        time.sleep(sleep_time)

    resp = client.post_order(signed_order, order_type)
    LAST_API_CALL_TIME = time.time()
    return resp


def execute_trade(client: ClobClient, token_id: str, price: float, size: float, side: str, paper_trading: bool) -> dict:
    """
    Place a limit order on Polymarket CLOB.
    side: 'BUY' or 'SELL'
    """
    if paper_trading:
        log.info(f"PAPER TRADE: {side} {size} of {token_id} @ {price}")
        send_telegram(f"📝 PAPER TRADE: {side} {size} of {token_id} @ {price}")
        return {"success": True, "orderID": "PAPER_TRADE_ORDER"}

    try:
        order_args = OrderArgs(
            token_id=token_id,
            price=round(price, 2),
            size=round(size / price, 2),  # size in shares = USDC / price
            side=side,
        )
        signed_order = client.create_order(order_args)
        resp = _rate_limited_post_order(client, signed_order, OrderType.GTC)

        if resp.get("success"):
            order_id = resp.get("orderID", "N/A")
            msg_lines = [
                "🚀 *Trade Executed*",
                f"Side: {side}",
                f"Price: {price}",
                f"Size: ${size}",
                f"Order ID: {order_id}"
            ]
            msg = "\n".join(msg_lines)
            log.info(f"Order placed: {resp}")
            send_telegram(msg)
            return resp
        else:
            log.error(f"Order failed: {resp}")
            return {}

    except Exception as e:
        log.error(f"Trade execution error: {e}")
        return {}


def close_position(client: ClobClient, token_id: str, current_price: float, size_shares: float, paper_trading: bool) -> dict:
    """Sell existing position to close it."""
    return execute_trade(client, token_id, current_price, size_shares * current_price, "SELL", paper_trading)
