import os
import json
import asyncio
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

import openai
import yfinance as yf

load_dotenv()

app = FastAPI(title="AI Trading War Room Backend")

# Allow CORS for local dev connecting to the VPS or local React app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Clients
KILO_API_KEY = os.getenv("KILO_API_KEY", "")

try:
    client = openai.AsyncOpenAI(
        api_key=KILO_API_KEY,
        base_url="https://api.kilo.ai/api/gateway"
    )
except Exception as e:
    print(f"Warning: OpenAI client initialization failed: {e}")
    client = None

# Map common tickers the user might type to Yahoo Finance symbols
TICKER_MAP = {
    "NQ1": "NQ=F", "NQ": "NQ=F",
    "ES1": "ES=F", "ES": "ES=F",
    "YM1": "YM=F", "YM": "YM=F",
    "RTY1": "RTY=F", "RTY": "RTY=F",
    "CL1": "CL=F", "CL": "CL=F",
    "GC1": "GC=F", "GC": "GC=F",
    "SI1": "SI=F", "SI": "SI=F",
    "ZB1": "ZB=F", "ZB": "ZB=F",
    "BTCUSD": "BTC-USD", "BTC": "BTC-USD",
    "ETHUSD": "ETH-USD", "ETH": "ETH-USD",
    "XAUUSD": "GC=F", "GOLD": "GC=F",
    "DXY": "DX-Y.NYB",
    "SPY": "SPY", "QQQ": "QQQ", "AAPL": "AAPL",
}

class AnalysisRequest(BaseModel):
    ticker: str
    timeframe: str
    riskProfile: str


def resolve_ticker(raw: str) -> str:
    """Map user-friendly tickers to Yahoo Finance symbols."""
    upper = raw.upper().strip()
    return TICKER_MAP.get(upper, upper)


def fetch_live_price_data(ticker: str, timeframe: str) -> dict:
    """
    Fetch REAL price data from Yahoo Finance.
    Returns a dict with current_price, recent bars, and a text summary.
    """
    yf_symbol = resolve_ticker(ticker)

    # Map timeframes to yfinance intervals and periods
    tf_map = {
        "1m": ("1m", "1d"),
        "2m": ("2m", "1d"),
        "5m": ("5m", "5d"),
        "15m": ("15m", "5d"),
        "1h": ("1h", "5d"),
        "4h": ("1h", "30d"),  # yf doesn't have 4h, use 1h and aggregate mentally
    }
    interval, period = tf_map.get(timeframe, ("5m", "5d"))

    try:
        tk = yf.Ticker(yf_symbol)
        df = tk.history(period=period, interval=interval)

        if df.empty:
            return {
                "current_price": None,
                "bars": [],
                "summary": f"No data returned from Yahoo Finance for {yf_symbol}. The ticker may be invalid or the market may be closed."
            }

        # Get real current price and recent bars
        current_price = round(float(df["Close"].iloc[-1]), 2)
        high = round(float(df["High"].iloc[-1]), 2)
        low = round(float(df["Low"].iloc[-1]), 2)
        volume = int(df["Volume"].iloc[-1])

        # Get the last 10 bars for context
        recent = df.tail(10)
        bars = []
        for idx, row in recent.iterrows():
            bars.append({
                "time": str(idx),
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"])
            })

        # Calculate basic stats for context
        session_high = round(float(df["High"].max()), 2)
        session_low = round(float(df["Low"].min()), 2)
        avg_volume = int(df["Volume"].mean())

        # Price movement over last N bars
        open_price = round(float(df["Open"].iloc[0]), 2)
        pct_change = round(((current_price - open_price) / open_price) * 100, 3)

        summary = (
            f"LIVE DATA for {ticker} (Yahoo: {yf_symbol}) on {interval} chart:\n"
            f"  CURRENT PRICE: {current_price}\n"
            f"  Last bar: O={bars[-1]['open']} H={bars[-1]['high']} L={bars[-1]['low']} C={bars[-1]['close']} V={bars[-1]['volume']}\n"
            f"  Session range: {session_low} - {session_high}\n"
            f"  Period % change: {pct_change}%\n"
            f"  Avg volume: {avg_volume}\n"
            f"  Last 10 bars OHLCV: {json.dumps(bars)}"
        )

        return {
            "current_price": current_price,
            "session_high": session_high,
            "session_low": session_low,
            "bars": bars,
            "summary": summary
        }

    except Exception as e:
        return {
            "current_price": None,
            "bars": [],
            "summary": f"Error fetching live data for {yf_symbol}: {str(e)}"
        }


async def ask_ai(role: str, prompt: str, max_tokens: int = 200) -> str:
    """Wrapper for OpenAI-compatible completions via Kilo Gateway."""
    if not client:
        await asyncio.sleep(1)
        return f"[{role}] Mock response due to missing API Key."
        
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",  # Kilo free model router
            max_tokens=max_tokens,
            temperature=0.3,
            messages=[
                {"role": "system", "content": f"You are a hedge fund {role}. Provide a single, punchy paragraph analysis."},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error querying {role}: {str(e)}"


async def generate_analysis_stream(req: AnalysisRequest):
    ticker = req.ticker.upper()
    tf = req.timeframe
    risk = req.riskProfile

    def emit(marker: str, data: dict):
        return f"data: [{marker}] {json.dumps(data)}\n\n"

    try:
        # 0. Fetch REAL live data from Yahoo Finance
        price_data = fetch_live_price_data(ticker, tf)
        market_data = price_data["summary"]
        current_price = price_data.get("current_price")

        price_anchor = ""
        if current_price:
            price_anchor = (
                f"\n\nCRITICAL: The CURRENT LIVE PRICE of {ticker} is {current_price}. "
                f"ALL entry zones, stop losses, and take profits MUST be within a realistic "
                f"range of this price. For day trading on a {tf} timeframe, entries should be "
                f"within 0.5-2% of {current_price}. DO NOT hallucinate prices."
            )
        
        # 1. ANALYST TEAM (Run concurrently for speed)
        analysts = {
            "FUNDAMENTAL_ANALYST": f"Analyze fundamentals for {ticker}. Timeframe {tf}. Market data: {market_data}",
            "SENTIMENT_ANALYST": f"Analyze retail and institutional sentiment for {ticker}. Timeframe {tf}. Current price: {current_price}.",
            "NEWS_ANALYST": f"Analyze recent macroeconomic or sector news impacting {ticker} right now. Current price: {current_price}.",
            "TECHNICAL_ANALYST": f"Analyze technical indicators for {ticker}. Timeframe {tf}. {market_data}{price_anchor}"
        }
        
        analyst_outputs = {}
        
        for role, prompt in analysts.items():
            text = await ask_ai(role, prompt)
            analyst_outputs[role] = text
            yield emit(role, {"text": text})

        # 2. RESEARCHER DEBATE
        context = json.dumps(analyst_outputs)
        
        bear_prompt = f"Using this analyst data: {context}, argue the BEARISH case against entering a day trade for {ticker}. Current price is {current_price}. Highlight weaknesses and risks."
        bear_text = await ask_ai("BEAR_RESEARCHER", bear_prompt, 250)
        yield emit("BEAR_RESEARCHER", {"text": bear_text})
        
        bull_prompt = f"Using this analyst data: {context}, argue the BULLISH case for entering a day trade for {ticker}. Current price is {current_price}. Defend against the bear."
        bull_text = await ask_ai("BULL_RESEARCHER", bull_prompt, 250)
        yield emit("BULL_RESEARCHER", {"text": bull_text})

        # 3. TRADER & RISK
        trader_prompt = f"Review the bull and bear arguments. Decide how to play {ticker} on a {tf} timeframe. Current price: {current_price}. Be decisive."
        trader_text = await ask_ai("TRADER_DECISION", trader_prompt, 200)
        yield emit("TRADER_DECISION", {"text": trader_text})

        risk_prompt = f"Review the trader's plan for {ticker}. Current price: {current_price}. The user's risk profile is {risk}. Do we approve the trade? How much size?"
        risk_text = await ask_ai("RISK_MANAGER", risk_prompt, 200)
        yield emit("RISK_MANAGER", {"text": risk_text})

        # 4. SIGNAL ENGINE (Deterministic JSON)
        json_prompt = f"""
        Based on all previous context for {ticker} on {tf} timeframe, and respecting a '{risk}' risk profile:
        
        CRITICAL PRICE ANCHOR: The CURRENT LIVE PRICE of {ticker} is exactly {current_price}.
        - Entry zone MUST be within 0.5-2% of {current_price}
        - Stop loss MUST be within 1-3% of {current_price}
        - Take profits MUST be within 1-5% of {current_price}
        - DO NOT use any other price level. Base everything on {current_price}.
        
        Output ONLY a strictly valid JSON object representing a day trading signal. No markdown formatting, no code blocks, just raw JSON.
        Required schema:
        {{
            "ticker": "{ticker}",
            "timestamp_utc": "ISO string",
            "timeframe": "{tf}",
            "market_regime": "trend_day_up|trend_day_down|range_day|high_vol_news|low_liquidity",
            "signal": "LONG|SHORT|NO_TRADE",
            "entry_zone": {{"min": 0, "max": 0}},
            "stop_loss": 0,
            "take_profit": [{{"level": 1, "price": 0}}, {{"level": 2, "price": 0}}],
            "risk_reward": 0,
            "confidence": 0-100,
            "position_size_pct": 0,
            "max_hold_minutes": 0,
            "invalidation_condition": "string",
            "reasons": ["string", "string"],
            "agent_agreement_score": 0-100,
            "tv_alert": "TICKER={ticker};TF={tf};SIG=LONG/SHORT;ENTRY=...;SL=...;TP1=...;TP2=...;CONF=..."
        }}
        """
        signal_text = await ask_ai("SIGNAL_ENGINE", json_prompt, 500)
        
        # Cleanup any accidental markdown block Claude might wrap it in
        clean_json = signal_text.replace("```json", "").replace("```", "").strip()
        
        try:
            signal_data = json.loads(clean_json)
        except json.JSONDecodeError:
            # Fallback if AI hallucinates invalid JSON
            signal_data = {
                "ticker": ticker,
                "timestamp_utc": datetime.utcnow().isoformat() + "Z",
                "timeframe": tf,
                "market_regime": "range_day",
                "signal": "NO_TRADE",
                "entry_zone": {"min": 0, "max": 0},
                "stop_loss": 0,
                "take_profit": [{"level":1, "price":0}],
                "risk_reward": 0,
                "confidence": 0,
                "position_size_pct": 0,
                "max_hold_minutes": 0,
                "invalidation_condition": "Agent hallucinated invalid JSON",
                "reasons": ["LLM Failed to return structured valid JSON. Trade aborted for safety."],
                "agent_agreement_score": 0,
                "tv_alert": f"TICKER={ticker};TF={tf};SIG=NO_TRADE;CONF=0;"
            }
            
        yield emit("SIGNAL_ENGINE", signal_data)

    except Exception as e:
        yield emit("ERROR", {"text": f"Backend stream failed: {str(e)}"})

@app.post("/api/v1/analyze")
async def analyze_endpoint(request: AnalysisRequest):
    return StreamingResponse(
        generate_analysis_stream(request),
        media_type="text/event-stream"
    )

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "war-room-ai"}
