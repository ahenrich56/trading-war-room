import requests
from logger import log
import time

GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"

def _make_request_with_retry(method, url, **kwargs):
    retries = 3
    for i in range(retries):
        try:
            response = requests.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            log.warning(f"Request failed ({i+1}/{retries}): {e}")
            time.sleep(2 ** i) # Exponential backoff
    raise requests.exceptions.RequestException(f"Failed after {retries} retries")


def get_active_markets(min_volume=5000, limit=50) -> list:
    """Fetch active markets sorted by volume, filtered by liquidity."""
    try:
        resp = _make_request_with_retry(
            "GET",
            f"{GAMMA_API}/markets",
            params={
                "active": "true",
                "closed": "false",
                "limit": limit,
                "sort_by": "volume24hr",
                "order": "DESC"
            },
            timeout=10
        )
        markets = resp.json()

        filtered = []
        for m in markets:
            volume = float(m.get("volume24hr") or 0)
            liquidity = float(m.get("liquidity") or 0)
            if volume >= min_volume and liquidity >= 1000:
                filtered.append(m)

        log.info(f"Scanner found {len(filtered)} qualifying markets")
        return filtered

    except Exception as e:
        log.error(f"Scanner error: {e}")
        return []


def get_market_prices(condition_id: str) -> dict:
    """Fetch current YES/NO prices from CLOB orderbook."""
    try:
        resp = _make_request_with_retry(
            "GET",
            f"{CLOB_API}/markets/{condition_id}",
            timeout=10
        )
        data = resp.json()
        return {
            "yes_price": float(data.get("bestBid") or 0),
            "no_price": round(1 - float(data.get("bestBid") or 0), 4),
            "spread": float(data.get("spread") or 0),
            "token_id_yes": data.get("tokens", [{}])[0].get("token_id"),
            "token_id_no": data.get("tokens", [{}])[1].get("token_id") if len(data.get("tokens", [])) > 1 else None,
        }
    except Exception as e:
        log.error(f"Price fetch error for {condition_id}: {e}")
        return {}
