import logging
import yfinance as yf
from dataclasses import dataclass
from typing import Optional, List
import time

log = logging.getLogger("WhaleIntel")

@dataclass
class WhaleAlert:
    """A detected volume/smart-money anomaly for TradFi assets."""
    alert_type: str  # unusual_volume, buy_wall, panic_distribution
    ticker: str
    amount_usd: float
    magnitude: float  # how unusual (e.g. 5.0 = 5x normal volume)
    confidence: float  # 0-100 score based on magnitude
    timestamp: float
    details: dict

class TradFiWhaleDetector:
    """
    Detects unusual volume spikes and buy walls for traditional assets using Yahoo Finance.
    Adapted from crypto 'UnusualVolumeDetector'.
    """

    def __init__(self):
        self.volume_history = {}

    def analyze_ticker(self, ticker_symbol: str) -> List[WhaleAlert]:
        alerts = []
        try:
            # Download 5 days of 15m data to capture recent intraday volume baseline
            ticker = yf.Ticker(ticker_symbol)
            df = ticker.history(period="5d", interval="15m")
            
            if df.empty or len(df) < 10:
                log.warning(f"Not enough data to analyze volume for {ticker_symbol}")
                return alerts

            # Get the most recent completed period
            latest = df.iloc[-1]
            latest_volume = latest["Volume"]
            latest_close = latest["Close"]
            latest_open = latest["Open"]
            
            # If current volume is zero (market closed or illiquid), skip
            if latest_volume <= 0:
                return alerts

            # Calculate the average volume over the previous 50 periods (excluding the very last one)
            recent_history = df.iloc[-51:-1]
            avg_volume = recent_history["Volume"].mean()
            
            if avg_volume <= 0:
                return alerts

            magnitude = latest_volume / avg_volume

            # 1. Volume Spike Detection (> 3x normal volume)
            if magnitude >= 3.0:
                price_change_pct = ((latest_close - latest_open) / latest_open) * 100
                
                # Determine alert type based on price direction
                if price_change_pct > 0.5:
                    alert_type = "buy_wall"
                    label = "Heavy Accumulation (Buy Wall)"
                elif price_change_pct < -0.5:
                    alert_type = "panic_distribution"
                    label = "Heavy Distribution (Panic Sell)"
                else:
                    alert_type = "unusual_volume"
                    label = "Abnormal Volume Spike"

                confidence = min(95.0, 50 + (magnitude * 5))
                amount_usd = latest_volume * latest_close

                alert = WhaleAlert(
                    alert_type=alert_type,
                    ticker=ticker_symbol,
                    amount_usd=amount_usd,
                    magnitude=magnitude,
                    confidence=confidence,
                    timestamp=time.time(),
                    details={
                        "magnitude": f"{magnitude:.1f}x normal",
                        "latest_volume": int(latest_volume),
                        "avg_volume": int(avg_volume),
                        "price_change_pct": f"{price_change_pct:+.2f}%",
                        "label": label
                    }
                )
                alerts.append(alert)

            return alerts

        except Exception as e:
            log.error(f"Error analyzing volume for {ticker_symbol}: {e}")
            return alerts
