import os
import json
import asyncio
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

import requests
import openai

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
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "")

try:
    client = openai.AsyncOpenAI(
        api_key=KILO_API_KEY,
        base_url="https://api.kilo.ai/api/gateway"
    )
except Exception as e:
    print(f"Warning: OpenAI client initialization failed: {e}")
    client = None

class AnalysisRequest(BaseModel):
    ticker: str
    timeframe: str
    riskProfile: str

async def fetch_alpha_vantage_data(ticker: str, timeframe: str):
    """
    Fetch intraday data from Alpha Vantage.
    Fallback to mocked data/summary if API key is missing or rate limited.
    """
    if not ALPHA_VANTAGE_API_KEY or ALPHA_VANTAGE_API_KEY == "your_alpha_vantage_key":
        return f"MOCKED OHLCV for {ticker} (No API Configured). Price currently at $134.50. Volume robust."
    
    # Map friendly timeframe to Alpha Vantage expected strings
    interval = "5min"
    if timeframe == "1m": interval = "1min"
    if timeframe == "15m": interval = "15min"

    url = f"https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol={ticker}&interval={interval}&apikey={ALPHA_VANTAGE_API_KEY}"
    
    try:
        resp = requests.get(url, timeout=5)
        data = resp.json()
        if "Information" in data and "rate limit" in data["Information"].lower():
            return f"RATE LIMITED by Alpha Vantage for {ticker}. Assume price is hovering near recent support."
        
        # Parse the dynamic 'Time Series (Xmin)' key
        ts_key = [k for k in data.keys() if "Time Series" in k]
        if not ts_key:
            return f"Failed to parse OHLCV. Raw data snippet: {str(data)[:100]}"
            
        series = data[ts_key[0]]
        recent_bars = list(series.items())[:5] # Get last 5 bars
        return f"Recent 5 bars for {ticker} ({interval}): {json.dumps(recent_bars)}"
        
    except Exception as e:
        return f"Error fetching {ticker} data: {str(e)}. Proceed with general real-time assumptions."

async def ask_ai(role: str, prompt: str, max_tokens: int = 200) -> str:
    """Wrapper for OpenAI-compatible completions via Kilo Gateway."""
    if not client:
        await asyncio.sleep(1)
        return f"[{role}] Mock response due to missing API Key."
        
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini", # Kilo free model router
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
        # 0. Fetch initial data
        market_data = await fetch_alpha_vantage_data(ticker, tf)
        
        # 1. ANALYST TEAM (Run concurrently for speed)
        analysts = {
            "FUNDAMENTAL_ANALYST": f"Analyze fundamentals for {ticker}. Timeframe {tf}. Market data: {market_data}",
            "SENTIMENT_ANALYST": f"Analyze retail and institutional sentiment for {ticker}. Timeframe {tf}.",
            "NEWS_ANALYST": f"Analyze recent macroeconomic or sector news impacting {ticker} right now.",
            "TECHNICAL_ANALYST": f"Analyze technical indicators for {ticker}. Timeframe {tf}. Market data: {market_data}"
        }
        
        analyst_outputs = {}
        
        # We process them sequentially in the stream so the UI fills perfectly, 
        # but we could 'gather' if we desired pure speed. We'll do sequential for the "typing" visual flow.
        for role, prompt in analysts.items():
            text = await ask_ai(role, prompt)
            analyst_outputs[role] = text
            yield emit(role, {"text": text})

        # 2. RESEARCHER DEBATE
        context = json.dumps(analyst_outputs)
        
        bear_prompt = f"Using this analyst data: {context}, argue the BEARISH case against entering a day trade for {ticker}. Highlight weaknesses and risks."
        bear_text = await ask_ai("BEAR_RESEARCHER", bear_prompt, 250)
        yield emit("BEAR_RESEARCHER", {"text": bear_text})
        
        bull_prompt = f"Using this analyst data: {context}, argue the BULLISH case for entering a day trade for {ticker}. Defend against the bear."
        bull_text = await ask_ai("BULL_RESEARCHER", bull_prompt, 250)
        yield emit("BULL_RESEARCHER", {"text": bull_text})

        # 3. TRADER & RISK
        trader_prompt = f"Review the bull and bear arguments. Decide how to play {ticker} on a {tf} timeframe. Be decisive."
        trader_text = await ask_ai("TRADER_DECISION", trader_prompt, 200)
        yield emit("TRADER_DECISION", {"text": trader_text})

        risk_prompt = f"Review the trader's plan for {ticker}. The user's risk profile is {risk}. Do we approve the trade? How much size?"
        risk_text = await ask_ai("RISK_MANAGER", risk_prompt, 200)
        yield emit("RISK_MANAGER", {"text": risk_text})

        # 4. SIGNAL ENGINE (Deterministic JSON)
        # We ask the AI to output strictly JSON for the final engine.
        json_prompt = f"""
        Based on all previous context for {ticker} on {tf} timeframe, and respecting a '{risk}' risk profile:
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
        signal_text = await ask_ai("SIGNAL_ENGINE", json_prompt, 400)
        
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
