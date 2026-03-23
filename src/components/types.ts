// Shared types for the Trading War Room

export interface SignalPayload {
  ticker: string;
  timeframe: string;
  signal: string;
  entry_zone: { min: number; max: number };
  stop_loss: number;
  take_profit: { level: number; price: number }[];
  confidence: number;
  risk_reward: number;
  position_size_pct: number;
  reasons: string[];
  tv_alert: string;
  market_regime?: string;
  timestamp_utc?: string;
  indicators_used?: Record<string, number | null>;
}
