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
  // Enhanced scoring fields
  signal_grade?: string;
  confluences?: ConfluenceFactor[];
  factors_aligned?: number;
  order_flow_agrees?: boolean;
  order_flow_bias?: string;
  mtf_confluence_label?: string;
  mtf_confluence_multiplier?: number;
  max_hold_minutes?: number;
}

export interface ConfluenceFactor {
  name: string;
  score: number;
  direction: string;
  weight: number;
  signals: string[];
}

export interface OrderFlowData {
  delta_bars: { time: number; value: number; color: string }[];
  cvd: { time: number; value: number }[];
  volume_profile: {
    levels: { price: number; volume: number; buy_vol: number; sell_vol: number }[];
    poc: number;
    vah: number;
    val: number;
    total_volume: number;
  };
  divergences: { type: string; description: string; price_level: number; bars_ago: number; strength: number }[];
  absorptions: { type: string; price: number; volume: number; volume_ratio: number; delta: number; bars_ago: number; description: string }[];
  stacked_imbalances: { direction: string; bars_count: number; start_price: number; end_price: number; cumulative_delta: number; description: string }[];
  vwap_bands: {
    vwap: { time: number; value: number }[];
    upper_1: { time: number; value: number }[];
    lower_1: { time: number; value: number }[];
    upper_2: { time: number; value: number }[];
    lower_2: { time: number; value: number }[];
    current_deviation: number;
  };
  summary: {
    overall_delta_bias: string;
    cvd_trend: string;
    recent_positive_bars: number;
    recent_negative_bars: number;
    total_recent_delta: number;
    poc: number;
    vah: number;
    val: number;
    divergence_count: number;
    absorption_count: number;
    vwap_deviation: number;
  };
}

export interface MtfOrderFlowData {
  tf_biases: Record<string, string>;
  tf_cvd: Record<string, string>;
  confluence_multiplier: number;
  confluence_label: string;
  agreement_count: number;
  total_count: number;
}
