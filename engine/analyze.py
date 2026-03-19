import sys
import time
import json
import argparse
from datetime import datetime

# Simulates the TradingAgents architecture by outputting line-by-line markers.
# These markers are parsed by the Next.js API route via Server-Sent Events (SSE).

def emit(marker, content):
    """Prints a structured line to stdout so the frontend can parse it."""
    # We use a strict format: [MARKER] JSON_Payload
    print(f"[{marker}] {json.dumps(content)}", flush=True)

def simulate_agent(marker, analysis_text, delay=1.5):
    """Simulate thinking time and emit text output."""
    time.sleep(delay)
    emit(marker, {"text": analysis_text})

def run_analysis(ticker, timeframe, risk_profile):
    print(f"Starting analysis for {ticker} on {timeframe} (Risk: {risk_profile})", flush=True)
    time.sleep(1)

    # 1. Analyst Team
    simulate_agent("FUNDAMENTAL_ANALYST", 
        f"Earnings power remains robust for {ticker}. Latest quarter showed an EPS beat of 14%. "
        "Forward guidance indicates strong datacenter demand sustaining margins.", 2.0)
    
    simulate_agent("SENTIMENT_ANALYST", 
        "Retail sentiment is extremely bullish across social channels. Institutional put/call ratio "
        "is leaning slightly bearish, indicating hedging near all-time highs.", 1.5)
    
    simulate_agent("NEWS_ANALYST", 
        "No high-impact macroeconomic news in the current session. "
        "Minor sector rotation detected, but semiconductor ETF flows remain positive.", 1.5)
    
    simulate_agent("TECHNICAL_ANALYST", 
        "Price is approaching the upper VWAP band on the 5m chart. RSI is at 68 (near overbought). "
        "Key resistance at $134.50. Volume profile shows a strong node at $132.00 acting as support.", 2.0)

    # 2. Researcher Debate
    simulate_agent("BEAR_RESEARCHER", 
        "The technical overextension combined with institutional hedging suggests a high probability of a mean-reversion pullback. "
        "Entering here carries poor R:R. We should wait for a test of the $132 support before getting long.", 2.5)
    
    simulate_agent("BULL_RESEARCHER", 
        "Fundamentals are simply too strong to fade. The lack of negative macro catalysts means trend-following algorithms will "
        "likely push this through resistance. Momentum is our friend right now.", 2.5)

    # 3. Trader & Risk
    simulate_agent("TRADER_DECISION", 
        "I favor the bull case but respect the bear's entry timing. We will look for a momentum breakout above $134.50, or buy a dip to $133.", 2.0)
    
    simulate_agent("RISK_MANAGER", 
        f"Volatility regime is elevated, but acceptable for '{risk_profile}' profile. Approved for sizing up to 0.5% account risk.", 1.5)

    # 4. Final Deterministic Signal Engine Match
    time.sleep(2)
    
    # Calculate a dynamic SL/TP for the mockup
    current_price_estimate = 134.00
    entry_min = current_price_estimate + 0.50
    entry_max = current_price_estimate + 1.00
    sl = current_price_estimate - 1.50
    
    signal_payload = {
        "ticker": ticker,
        "timestamp_utc": datetime.utcnow().isoformat() + "Z",
        "timeframe": timeframe,
        "market_regime": "trend_day_up",
        "signal": "LONG",
        "entry_zone": {"min": entry_min, "max": entry_max},
        "stop_loss": sl,
        "take_profit": [{"level": 1, "price": entry_max + 3.00}, {"level": 2, "price": entry_max + 6.00}],
        "risk_reward": 2.5,
        "confidence": 82,
        "position_size_pct": 0.5,
        "max_hold_minutes": 120,
        "invalidation_condition": "15m candle closes below VWAP",
        "reasons": [
            "Earnings momentum supports continued uptrend",
            "No bearish catalysts present in the session",
            "Clear breakout setup above $134.50 resistance"
        ],
        "agent_agreement_score": 85,
        "tv_alert": f"TICKER={ticker};TF={timeframe};SIG=LONG;ENTRY={entry_min}-{entry_max};SL={sl};TP1={entry_max+3.00};TP2={entry_max+6.00};CONF=82;EXP=120m"
    }
    
    emit("SIGNAL_ENGINE", signal_payload)
    print("FINISHED", flush=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", required=True, help="Stock ticker symbol")
    parser.add_argument("--timeframe", required=True, help="1m, 5m, 15m")
    parser.add_argument("--risk_profile", required=True, help="conservative, standard, aggressive")
    args = parser.parse_args()
    
    try:
        run_analysis(args.ticker, args.timeframe, args.risk_profile)
    except Exception as e:
        emit("ERROR", {"text": str(e)})
