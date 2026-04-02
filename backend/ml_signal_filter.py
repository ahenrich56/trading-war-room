"""
XGBoost Signal Filter — Trading War Room

Trains a binary classifier (WIN / LOSS) on stored signal features + outcome labels.
Activates automatically once MIN_OUTCOMES_FOR_TRAINING labeled outcomes exist.

Usage:
  - After each outcome is recorded, call auto_train_if_ready(DB_PATH).
  - In the analysis pipeline, call predict_win_probability(signal_data) to gate signals.
  - is_model_ready() returns True if a trained model exists on disk.

Feature pipeline:
  - Extracts 50+ numeric/categorical features from a stored signal dict.
  - Categorical fields are label-encoded using a saved mapping.
  - Missing values are filled with column medians from training data.

Files written to disk:
  - ml_model.pkl       : trained XGBClassifier
  - ml_meta.json       : feature list, encodings, medians, training stats
"""

import json
import os
import pickle
import sqlite3
import logging
from typing import Optional

logger = logging.getLogger("ml_signal_filter")

# ── Config ──────────────────────────────────────────────────
MIN_OUTCOMES_FOR_TRAINING = 200   # Minimum labeled outcomes before training
RETRAIN_EVERY_N = 50              # Retrain after every N new outcomes beyond minimum
MODEL_PATH = os.path.join(os.path.dirname(__file__), "ml_model.pkl")
META_PATH  = os.path.join(os.path.dirname(__file__), "ml_meta.json")
WIN_PROBABILITY_THRESHOLD = 0.50  # Block signals below this P(WIN) — 42% WR at this cutoff

# ── Categorical encodings (consistent across train/predict) ──
REGIME_MAP = {
    "TRENDING_UP": 0, "TRENDING_DOWN": 1, "RANGING": 2,
    "HIGH_VOLATILITY": 3, "LOW_LIQUIDITY": 4,
}
GRADE_MAP  = {"A+": 4, "A": 3, "B": 2, "C": 1, "F": 0}
BIAS_MAP   = {"BULLISH": 1, "NEUTRAL": 0, "BEARISH": -1}
MTF_MAP    = {"STRONG": 2, "MODERATE": 1, "NEUTRAL": 0, "CONFLICTING": -1}
SESSION_MAP = {"KILLZONE": 2, "ACTIVE": 1, "DEAD": 0}
DIRECTION_MAP = {"LONG": 1, "SHORT": -1, "NO_TRADE": 0}


# ═══════════════════════════════════════════════════════════
#  FEATURE EXTRACTION
# ═══════════════════════════════════════════════════════════

def extract_features(signal: dict) -> Optional[dict]:
    """
    Convert a stored signal dict into a flat numeric feature vector.
    Returns None if the signal lacks the minimum required fields.
    """
    raw = signal.get("raw_indicators", {})
    factor = signal.get("factor_scores", {})
    structure = signal.get("structure_levels", {}) or {}

    # Require at minimum a direction and score
    if signal.get("signal") not in ("LONG", "SHORT"):
        return None

    def _f(d, key, default=0.0):
        v = d.get(key)
        return float(v) if v is not None else default

    def _cat(mapping, val, default=0):
        return mapping.get(str(val), default)

    features = {
        # ── Signal meta ──
        "direction":              _cat(DIRECTION_MAP, signal.get("signal")),
        "grade":                  _cat(GRADE_MAP, signal.get("signal_grade", "C")),
        "score":                  _f(signal, "score"),
        "confidence":             _f(signal, "confidence") * 100 if _f(signal, "confidence") <= 1 else _f(signal, "confidence"),
        "risk_reward":            _f(signal, "risk_reward"),
        "factors_aligned":        _f(signal, "factors_aligned"),
        "order_flow_agrees":      1.0 if signal.get("order_flow_agrees") else 0.0,
        "agent_agreement_score":  _f(signal, "agent_agreement_score") * 100 if _f(signal, "agent_agreement_score") <= 1 else _f(signal, "agent_agreement_score"),

        # ── Factor scores ──
        "trend_score":       _f(factor, "trend"),
        "momentum_score":    _f(factor, "momentum"),
        "structure_score":   _f(factor, "structure"),
        "order_flow_score":  _f(factor, "order_flow"),
        "volume_score":      _f(factor, "volume"),

        # ── Regime / session / correlation ──
        "market_regime":          _cat(REGIME_MAP, signal.get("market_regime", "RANGING")),
        "mtf_confluence":         _cat(MTF_MAP, signal.get("mtf_confluence_label", "NEUTRAL")),
        "mtf_multiplier":         _f(signal, "mtf_confluence_multiplier", 1.0),
        "session_modifier":       _f(signal, "session_modifier", 1.0),
        "session_label":          _cat(SESSION_MAP, signal.get("session_label", "ACTIVE")),
        "correlation_modifier":   _f(signal, "correlation_modifier", 1.0),
        "order_flow_bias":        _cat(BIAS_MAP, signal.get("order_flow_bias", "NEUTRAL")),

        # ── Raw indicators ──
        "RSI_14":             _f(raw, "RSI_14", 50.0),
        "RSI_lag_5":          _f(raw, "RSI_lag_5", 50.0),
        "RSI_bars_above_50":  _f(raw, "RSI_bars_above_50"),
        "RSI_bars_below_50":  _f(raw, "RSI_bars_below_50"),
        "MACD_histogram":     _f(raw, "MACD_histogram"),
        "MACD_histogram_lag_3": _f(raw, "MACD_histogram_lag_3"),
        "ADX":                _f(raw, "ADX", 20.0),
        "ATR_14":             _f(raw, "ATR_14"),
        "ATR_pct":            _f(raw, "ATR_pct", 0.5),
        "ATR_acceleration":   _f(raw, "ATR_acceleration", 1.0),
        "StochRSI_K":         _f(raw, "StochRSI_K", 50.0),
        "StochRSI_D":         _f(raw, "StochRSI_D", 50.0),
        "volume_ratio":       _f(raw, "volume_ratio", 1.0),
        "VWAP_deviation_pct": _f(raw, "vwap_deviation"),   # σ units if present
        "BB_position":        _f(raw, "BB_position", 0.5), # 0=lower band, 1=upper
        "ema_stack_score":    _f(raw, "ema_stack_score"),  # -3 to +3
        "bars_since_ema_cross": _f(raw, "bars_since_ema_cross", 10.0),

        # ── Structure levels quality ──
        "sl_fallback_used":   1.0 if structure.get("fallback_used") else 0.0,

        # ── Time features ──
        "hour_utc":           _extract_hour(signal),
        "day_of_week":        _extract_dow(signal),

        # ── Specialist agreement (new pipeline) ──
        "specialist_agreement": _count_specialist_agreement(signal),
        "ict_confidence":       _get_specialist_confidence(signal, "ICT_TRADER"),
        "orderflow_confidence": _get_specialist_confidence(signal, "ORDERFLOW_TRADER"),

        # ── Liquidity grab / SFP features ──
        "liquidity_grab_present": _has_ict_feature(signal, "liquidity_grabs"),
        "sfp_present":            _has_ict_feature(signal, "swing_failure_patterns"),
        "judas_swing_present":    1.0 if _get_nested(signal, "judas_swing") else 0.0,
    }
    return features


def _extract_hour(signal: dict) -> float:
    """Extract hour (UTC) from signal timestamp."""
    ts = signal.get("timestamp_utc", "")
    try:
        from datetime import datetime as _dt
        dt = _dt.fromisoformat(ts.rstrip("Z"))
        return float(dt.hour)
    except Exception:
        return 12.0


def _extract_dow(signal: dict) -> float:
    """Extract day of week (0=Mon, 6=Sun) from signal timestamp."""
    ts = signal.get("timestamp_utc", "")
    try:
        from datetime import datetime as _dt
        dt = _dt.fromisoformat(ts.rstrip("Z"))
        return float(dt.weekday())
    except Exception:
        return 2.0


def _count_specialist_agreement(signal: dict) -> float:
    """Count how many specialists agreed with the final signal direction."""
    votes = signal.get("specialist_votes", {})
    final_dir = signal.get("signal", "NO_TRADE")
    if not votes or final_dir == "NO_TRADE":
        return 0.0
    return float(sum(1 for v in votes.values() if v.get("direction") == final_dir))


def _get_specialist_confidence(signal: dict, specialist: str) -> float:
    """Get a specific specialist's confidence score."""
    votes = signal.get("specialist_votes", {})
    return float(votes.get(specialist, {}).get("confidence", 50))


def _has_ict_feature(signal: dict, key: str) -> float:
    """Check if ICT data within the signal's raw data has a given feature list."""
    # The ICT data is embedded in the signal during analysis
    raw = signal.get("raw_indicators", {})
    # Check top-level signal data (we store ict features at signal level)
    items = signal.get(key, [])
    if items and len(items) > 0:
        return 1.0
    return 0.0


def _get_nested(signal: dict, key: str):
    """Get a nested value from signal dict."""
    return signal.get(key)


# ═══════════════════════════════════════════════════════════
#  DATASET BUILDER
# ═══════════════════════════════════════════════════════════

def _build_dataset(db_path: str):
    """
    Join signals + outcomes from SQLite, extract features and labels.
    Pairs by row index (seeder inserts signal[i] with outcome[i]).
    Returns (X: list[dict], y: list[int]) where y=1 for WIN, 0 for LOSS.
    """
    conn = sqlite3.connect(db_path)

    signals_raw = conn.execute(
        "SELECT data FROM signals WHERE resolved = 1 ORDER BY id ASC"
    ).fetchall()
    outcomes_raw = conn.execute(
        "SELECT data FROM outcomes ORDER BY id ASC"
    ).fetchall()
    conn.close()

    signals = [json.loads(r[0]) for r in signals_raw]
    outcomes = [json.loads(r[0]) for r in outcomes_raw]

    X, y = [], []
    # Pair by index — seeder inserts signal[i] with outcome[i]
    for i in range(min(len(signals), len(outcomes))):
        s = signals[i]
        o = outcomes[i]
        # Validate they match (same ticker)
        if s.get("ticker", "").upper() != o.get("ticker", "").upper():
            continue
        label = 1 if o.get("result") == "WIN" else 0
        feats = extract_features(s)
        if feats is None:
            continue
        X.append(feats)
        y.append(label)

    return X, y


# ═══════════════════════════════════════════════════════════
#  TRAINING
# ═══════════════════════════════════════════════════════════

def train_model(db_path: str) -> dict:
    """
    Train XGBoost classifier on stored signal/outcome data.
    Returns training stats dict. Saves model + meta to disk.
    """
    try:
        import xgboost as xgb
        import numpy as np
    except ImportError:
        return {"error": "xgboost not installed — run: pip install xgboost"}

    X_dicts, y = _build_dataset(db_path)
    if len(X_dicts) < MIN_OUTCOMES_FOR_TRAINING:
        return {"error": f"Need {MIN_OUTCOMES_FOR_TRAINING} labeled outcomes, have {len(X_dicts)}"}

    # Get consistent feature order from first sample
    feature_names = sorted(X_dicts[0].keys())

    # Build numeric matrix, fill missing with column median
    X_raw = []
    for row in X_dicts:
        X_raw.append([row.get(f, float("nan")) for f in feature_names])

    X_np = np.array(X_raw, dtype=float)
    y_np = np.array(y, dtype=int)

    # Per-column median imputation
    medians = {}
    for i, fname in enumerate(feature_names):
        col = X_np[:, i]
        col_valid = col[~np.isnan(col)]
        med = float(np.median(col_valid)) if len(col_valid) > 0 else 0.0
        medians[fname] = med
        X_np[np.isnan(X_np[:, i]), i] = med

    # Class balance check
    n_wins = int(y_np.sum())
    n_losses = int(len(y_np) - n_wins)
    scale_pos_weight = n_losses / max(n_wins, 1)

    model = xgb.XGBClassifier(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=scale_pos_weight,
        eval_metric="logloss",
        use_label_encoder=False,
        random_state=42,
        verbosity=0,
    )
    model.fit(X_np, y_np)

    # Feature importance (top 10)
    importances = dict(zip(feature_names, model.feature_importances_.tolist()))
    top_features = sorted(importances.items(), key=lambda x: x[1], reverse=True)[:10]

    # Save model
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)

    meta = {
        "feature_names": feature_names,
        "medians": medians,
        "n_samples": len(y),
        "n_wins": n_wins,
        "n_losses": n_losses,
        "win_rate": round(n_wins / len(y) * 100, 1),
        "top_features": top_features,
        "threshold": WIN_PROBABILITY_THRESHOLD,
    }
    with open(META_PATH, "w") as f:
        json.dump(meta, f, indent=2)

    logger.info(f"[ML] Model trained: {len(y)} samples, {n_wins}W/{n_losses}L ({meta['win_rate']}% WR)")
    logger.info(f"[ML] Top features: {[f for f, _ in top_features[:5]]}")
    return meta


# ═══════════════════════════════════════════════════════════
#  INFERENCE
# ═══════════════════════════════════════════════════════════

def is_model_ready() -> bool:
    """Returns True if a trained model file exists on disk."""
    return os.path.exists(MODEL_PATH) and os.path.exists(META_PATH)


def predict_win_probability(signal: dict) -> float:
    """
    Returns P(WIN) for a signal dict using the trained model.
    Returns 0.5 (neutral) if model not available or feature extraction fails.
    """
    if not is_model_ready():
        return 0.5

    try:
        import numpy as np

        with open(MODEL_PATH, "rb") as f:
            model = pickle.load(f)
        with open(META_PATH) as f:
            meta = json.load(f)

        feature_names = meta["feature_names"]
        medians = meta["medians"]

        feats = extract_features(signal)
        if feats is None:
            return 0.5

        x = np.array([[feats.get(k, medians.get(k, 0.0)) for k in feature_names]])
        proba = model.predict_proba(x)[0][1]  # P(WIN)
        return float(round(proba, 4))

    except Exception as e:
        logger.warning(f"[ML] Inference failed: {e}")
        return 0.5


# ═══════════════════════════════════════════════════════════
#  AUTO-TRAIN HOOK
# ═══════════════════════════════════════════════════════════

def auto_train_if_ready(db_path: str) -> Optional[dict]:
    """
    Call this after every new outcome is recorded.
    Trains the model if the minimum threshold is reached, then retrains
    every RETRAIN_EVERY_N outcomes beyond that.
    Returns training stats if training ran, else None.
    """
    try:
        conn = sqlite3.connect(db_path)
        n_outcomes = conn.execute("SELECT COUNT(*) FROM outcomes").fetchone()[0]
        conn.close()

        if n_outcomes < MIN_OUTCOMES_FOR_TRAINING:
            remaining = MIN_OUTCOMES_FOR_TRAINING - n_outcomes
            logger.debug(f"[ML] {n_outcomes} outcomes — need {remaining} more before training")
            return None

        # Check if we should retrain
        should_train = False
        if not is_model_ready():
            should_train = True
        else:
            # Retrain every RETRAIN_EVERY_N outcomes after the minimum
            extra = n_outcomes - MIN_OUTCOMES_FOR_TRAINING
            if extra % RETRAIN_EVERY_N == 0:
                should_train = True

        if should_train:
            logger.info(f"[ML] Auto-training with {n_outcomes} outcomes...")
            return train_model(db_path)

    except Exception as e:
        logger.warning(f"[ML] auto_train_if_ready failed: {e}")

    return None


# ═══════════════════════════════════════════════════════════
#  TRAINING STATS (for API endpoint)
# ═══════════════════════════════════════════════════════════

def get_model_stats() -> dict:
    """Return model metadata for display in the UI."""
    if not is_model_ready():
        return {"status": "not_trained", "message": f"Need {MIN_OUTCOMES_FOR_TRAINING} labeled outcomes to activate"}
    try:
        with open(META_PATH) as f:
            meta = json.load(f)
        return {"status": "active", **meta}
    except Exception:
        return {"status": "error"}
