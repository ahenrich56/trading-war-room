# AI Trading War Room

A multi-agent AI system for real-time market analysis, automated trading signals, and self-learning backtesting.

![War Room Interface](https://via.placeholder.com/800x400.png?text=AI+Trading+War+Room)

## Features

- **Multi-Agent Consensus**: 8 specialized AI agents (Fundamental, Sentiment, News, Technical Analysts; Bear/Bull Researchers; Trader Decision; Risk Manager) debate and output a final signal.
- **Self-Learning Loop**: The AI tracks past win/loss performance and adjusts its prompt context to avoid repeating losing patterns.
- **Smart Money Concepts (ICT)**: Detects Break of Structure (BOS), Change of Character (CHoCH), Order Blocks (OB), and Fair Value Gaps (FVG).
- **Backtesting & sizing**: Replays historical trades to determine Win Rate, Sharpe Ratio, Max Drawdown, and optimal Kelly Criterion sizing.
- **Demo Mode**: Test the UI with offline mock data without needing backend API keys.
- **Educational Tooltips**: Hover over complex trading terms (e.g., Sharpe Ratio, FVG, Kelly %) to see clear explanations.

## Architecture

- **Frontend**: Next.js 14, Tailwind CSS, Shadcn UI, TradingView Lightweight Charts.
- **Backend**: Python FastAPI, OpenAI/Kilo.ai API, SQLite for outcome tracking.

---

## Getting Started

### Prerequisites

- Node.js 18+
- Python 3.11+
- API Key from standard OpenAI-compatible endpoints (e.g., Kilo.ai).

### Option 1: Docker (Recommended)

1. Rename the environment files:
   - `cp backend/.env.example backend/.env`
   - `cp .env.example .env`
2. Add your API keys to `backend/.env`.
3. Run the complete stack:
   ```bash
   docker-compose up --build
   ```
4. Open [http://localhost:3000](http://localhost:3000)

### Option 2: Manual Setup

#### Backend (FastAPI)
1. Navigate to the `backend/` directory.
2. Create standard Python virtual environment: `python -m venv venv` and activate it.
3. Install dependencies: `pip install -r requirements.txt`
4. Setup `.env` file with `KILO_API_KEY`.
5. Run the server: `uvicorn main:app --reload --port 8000`

#### Frontend (Next.js)
1. Install dependencies: `npm install`
2. Next.js connects to `http://localhost:8000` by default. Update `.env.local` if needed.
3. Run the development server: `npm run dev`
4. Open [http://localhost:3000](http://localhost:3000)
