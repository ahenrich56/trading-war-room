"""
CSV Backtest Seeder — Trading War Room

Imports historical OHLCV CSV data, runs the full 5-factor signal scoring
pipeline on each bar, simulates WIN/LOSS via forward price simulation, and
seeds the SQLite DB with paired signal+outcome records to bootstrap the
XGBoost ML model.

Usage (CLI):
    python csv_backtest_seeder.py /path/to/nq_1min.csv --ticker NQ
    python csv_backtest_seeder.py /path/to/data_dir/ --ticker NQ --min-grade A
    python csv_backtest_seeder.py data.csv --max-bars 500  # smoke test

Importable:
    from csv_backtest_seeder import seed_from_csv
    stats = seed_from_csv("nq_1min.csv", ticker="NQ", min_grade="B")
"""

import argparse
import glob
import io
import json
import os
import sqlite3
import sys
import zipfile
from datetime import datetime

import pandas as pd

# Optional zstandard support (pip install zstandard)
try:
    import zstandard as zstd
    _ZST_AVAILABLE = True
except ImportError:
    _ZST_AVAILABLE = False

from db import DB_PATH, _init_db
from ict_analysis import detect_ict_concepts
from indicators import compute_indicators
from ml_signal_filter import auto_train_if_ready
from order_flow import compute_order_flow_summary
from signal_scoring import calculate_enhanced_score

# ── Constants ────────────────────────────────────────────────
WARMUP_BARS    = 50     # minimum bars before scoring starts
LOOKAHEAD      = 30     # forward bars to scan for WIN/LOSS
WINDOW         = 210    # rolling window size (covers EMA_200 warmup)
WIN_ATR_MULT   = 2.0    # 2:1 R:R — target must be 2x further than stop
LOSS_ATR_MULT  = 1.0    # stop distance = 1.0x ATR
PROGRESS_EVERY = 25     # print status every N signals stored
COMMIT_EVERY   = 50     # batch commit frequency

GRADE_ORDER = {"A+": 4, "A": 3, "B": 2, "C": 1, "F": 0}

# ── Session filter — only process high-probability trading windows ──
# London Killzone (07–10 UTC) and NY Killzone (13–16 UTC)
TRADING_HOURS_UTC = [(7, 10), (13, 16)]

# ── Additional seeder quality gates ──
SEEDER_MIN_ADX      = 20    # stronger trend required vs live gate of 18
SEEDER_MIN_VOL      = 0.5   # must be at least 50% of avg volume
SEEDER_MIN_SCORE    = 28    # aligns with new live grade-B threshold of score>27

# ── Session label mapping (UTC hour → label, modifier) ──
_SESSION_MAP_UTC = [
    ((7,  10), "LONDON_KILLZONE", 1.20),
    ((10, 13), "LONDON_SESSION",  1.10),
    ((13, 16), "NY_KILLZONE",     1.15),
    ((16, 18), "NY_LUNCH",        0.70),
    ((18, 20), "NY_PM",           0.95),
    ((20, 22), "NY_CLOSE",        0.80),
    ((22, 24), "DEAD_ZONE",       0.60),
    ((0,   7), "ASIAN",           0.85),
]

def _get_session(bar_time_str: str) -> tuple:
    """Return (session_label, session_modifier) for a UTC ISO timestamp string."""
    try:
        hour = int(bar_time_str[11:13])  # fast parse HH from ISO string
    except Exception:
        return ("ACTIVE", 1.0)
    for (start, end), label, modifier in _SESSION_MAP_UTC:
        if start <= hour < end:
            return (label, modifier)
    return ("ACTIVE", 1.0)


# ── Column name aliases (case-insensitive) ────────────────────
_COL_MAP = {
    "Open":   {"open", "o", "first", "open_price", "openprice"},
    "High":   {"high", "h", "highest", "high_price", "highprice"},
    "Low":    {"low", "l", "lowest", "low_price", "lowprice"},
    "Close":  {"close", "c", "last", "price", "close_price", "closeprice", "settlement"},
    "Volume": {"volume", "vol", "v", "qty", "quantity", "totalvolume"},
}


# ═══════════════════════════════════════════════════════════
#  COLUMN NORMALIZER
# ═══════════════════════════════════════════════════════════

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalise a raw CSV DataFrame into canonical Open/High/Low/Close/Volume
    columns with a DatetimeIndex.

    Handles: TradingView, NinjaTrader, Sierra Chart, Rithmic/CQG, Quandl-style,
    and generic brokerage exports.
    """
    df = df.copy()

    # ── 1. Normalise column names to lowercase for matching ──
    lower_map = {col: col.lower().strip().replace(" ", "_") for col in df.columns}
    df.rename(columns=lower_map, inplace=True)
    cols = set(df.columns)

    # ── 2. Build datetime index ──
    datetime_candidates = [
        "ts_event", "datetime", "date_time", "timestamp", "time", "date",
        "bar_time", "bar time", "bar_date", "dt",
    ]
    dt_col = None
    for cand in datetime_candidates:
        norm = cand.lower().replace(" ", "_")
        if norm in cols:
            dt_col = norm
            break

    # NinjaTrader / Sierra Chart: separate Date + Time columns
    if dt_col is None and "date" in cols and "time" in cols:
        try:
            df["datetime"] = pd.to_datetime(
                df["date"].astype(str) + " " + df["time"].astype(str),
                infer_datetime_format=True,
            )
            df.drop(columns=["date", "time"], inplace=True)
            dt_col = "datetime"
            cols = set(df.columns)
        except Exception:
            pass

    if dt_col and dt_col in df.columns:
        try:
            df[dt_col] = pd.to_datetime(df[dt_col], utc=True)
            df.set_index(dt_col, inplace=True)
        except Exception:
            pass

    # ── 3. Map OHLCV columns ──
    rename_ops = {}
    for canonical, aliases in _COL_MAP.items():
        if canonical.lower() in df.columns:
            rename_ops[canonical.lower()] = canonical
            continue
        for col in df.columns:
            clean = col.lower().replace(" ", "_").replace("-", "_")
            if clean in aliases:
                rename_ops[col] = canonical
                break

    df.rename(columns=rename_ops, inplace=True)

    # ── 4. Validate required columns exist ──
    required = {"Open", "High", "Low", "Close", "Volume"}
    missing = required - set(df.columns)
    if missing:
        available = list(df.columns)
        raise ValueError(
            f"Could not map columns {missing} from CSV. "
            f"Available columns after normalisation: {available}"
        )

    # ── 5. Keep only OHLCV (drop ticks, OI, trade-count, etc.) ──
    df = df[["Open", "High", "Low", "Close", "Volume"]]

    # ── 6. Cast types, drop NaN rows ──
    for col in ("Open", "High", "Low", "Close"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["Volume"] = pd.to_numeric(df["Volume"], errors="coerce").fillna(0).astype("int64")
    df.dropna(subset=["Open", "High", "Low", "Close"], inplace=True)

    # ── 7. Sort ascending ──
    if isinstance(df.index, pd.DatetimeIndex):
        df.sort_index(inplace=True)
    else:
        df.reset_index(drop=True, inplace=True)

    return df


# ═══════════════════════════════════════════════════════════
#  CSV LOADER
# ═══════════════════════════════════════════════════════════

def load_csv(filepath: str) -> pd.DataFrame:
    """
    Load one CSV file, a ZIP archive, or a directory of CSV/TXT/ZIP files
    into a single normalised DataFrame.
    """
    if os.path.isdir(filepath):
        files = sorted(
            glob.glob(os.path.join(filepath, "*.csv")) +
            glob.glob(os.path.join(filepath, "*.txt")) +
            glob.glob(os.path.join(filepath, "*.zip"))
        )
        if not files:
            raise FileNotFoundError(f"No CSV/TXT/ZIP files found in directory: {filepath}")
        frames = []
        for f in files:
            frames.extend(_load_file(f))
        combined = pd.concat(frames)
        if isinstance(combined.index, pd.DatetimeIndex):
            combined = combined[~combined.index.duplicated(keep="first")]
            combined.sort_index(inplace=True)
        return combined

    frames = _load_file(filepath)
    if len(frames) == 1:
        return frames[0]
    combined = pd.concat(frames)
    if isinstance(combined.index, pd.DatetimeIndex):
        combined = combined[~combined.index.duplicated(keep="first")]
        combined.sort_index(inplace=True)
    return combined


def _load_file(filepath: str) -> list:
    """Return a list of normalised DataFrames from a file (CSV, TXT, ZIP, or ZST)."""
    if zipfile.is_zipfile(filepath):
        frames = []
        with zipfile.ZipFile(filepath, "r") as zf:
            all_names = zf.namelist()
            # Skip JSON/metadata and tiny roll files (< 10 KB = likely empty or stub)
            csv_names = sorted(
                n for n in all_names
                if n.lower().endswith((".csv", ".txt", ".csv.zst"))
                and not os.path.basename(n).startswith(".")
                and not os.path.basename(n).startswith("symbology")
                and zf.getinfo(n).file_size >= 10_000
            )
            if not csv_names:
                raise ValueError(f"No usable CSV files found inside ZIP: {filepath}")
            print(f"[seeder] Found {len(csv_names)} files in ZIP")
            for name in csv_names:
                try:
                    with zf.open(name) as f:
                        if name.lower().endswith(".zst"):
                            data = _decompress_zst(f.read())
                            raw = io.StringIO(data.decode("utf-8", errors="replace"))
                        else:
                            raw = io.TextIOWrapper(f, encoding="utf-8", errors="replace")
                        frames.append(_load_single(raw))
                except Exception as e:
                    print(f"[seeder] Skipping {name}: {e}")
        return frames

    if filepath.lower().endswith(".zst"):
        with open(filepath, "rb") as f:
            data = _decompress_zst(f.read())
        raw = io.StringIO(data.decode("utf-8", errors="replace"))
        return [_load_single(raw)]

    return [_load_single(filepath)]


def _decompress_zst(data: bytes) -> bytes:
    """Decompress Zstandard (.zst) bytes."""
    if _ZST_AVAILABLE:
        dctx = zstd.ZstdDecompressor()
        return dctx.decompress(data, max_output_size=500 * 1024 * 1024)
    # Fallback: try subprocess (Windows has no built-in zstd)
    import subprocess, tempfile
    with tempfile.NamedTemporaryFile(suffix=".zst", delete=False) as tmp_in:
        tmp_in.write(data)
        tmp_in_path = tmp_in.name
    tmp_out_path = tmp_in_path[:-4]
    try:
        subprocess.run(["zstd", "-d", tmp_in_path, "-o", tmp_out_path, "-f"],
                       check=True, capture_output=True)
        with open(tmp_out_path, "rb") as f:
            return f.read()
    finally:
        for p in (tmp_in_path, tmp_out_path):
            if os.path.exists(p):
                os.unlink(p)


def _load_single(source) -> pd.DataFrame:
    """Load and normalise a single CSV file path or file-like object."""
    label = source if isinstance(source, str) else getattr(source, "name", "stream")
    for sep in (",", "\t", ";"):
        try:
            # File-like objects must be rewound between attempts
            if hasattr(source, "seek"):
                source.seek(0)
            df = pd.read_csv(source, sep=sep, low_memory=False)
            if len(df.columns) >= 5:
                return normalize_columns(df)
        except Exception:
            continue

    raise ValueError(f"Could not parse CSV: {label}")


# ═══════════════════════════════════════════════════════════
#  GRADE FILTER
# ═══════════════════════════════════════════════════════════

def _grade_passes(grade: str, min_grade: str) -> bool:
    return GRADE_ORDER.get(grade, 0) >= GRADE_ORDER.get(min_grade, 0)


# ═══════════════════════════════════════════════════════════
#  FORWARD OUTCOME SIMULATOR
# ═══════════════════════════════════════════════════════════

def simulate_outcome(
    df: pd.DataFrame,
    entry_idx: int,
    direction: str,
    atr: float,
) -> tuple:
    """
    Scan up to LOOKAHEAD bars forward to determine WIN or LOSS.

    Returns:
        ("WIN",  exit_price) — target hit
        ("LOSS", exit_price) — stop hit
        (None,   None)       — neither hit within LOOKAHEAD bars (ambiguous)
    """
    if not atr or atr <= 0:
        return (None, None)

    entry_price = float(df["Close"].iloc[entry_idx])

    if direction == "LONG":
        win_target  = entry_price + WIN_ATR_MULT  * atr
        loss_target = entry_price - LOSS_ATR_MULT * atr
    else:  # SHORT
        win_target  = entry_price - WIN_ATR_MULT  * atr
        loss_target = entry_price + LOSS_ATR_MULT * atr

    end_idx = min(entry_idx + LOOKAHEAD + 1, len(df))
    future = df.iloc[entry_idx + 1 : end_idx]

    for _, bar in future.iterrows():
        high = float(bar["High"])
        low  = float(bar["Low"])

        if direction == "LONG":
            hit_win  = high >= win_target
            hit_loss = low  <= loss_target
        else:
            hit_win  = low  <= win_target
            hit_loss = high >= loss_target

        if hit_win and hit_loss:
            # Both on same bar — conservative: stop was hit first
            return ("LOSS", round(loss_target, 4))
        if hit_win:
            return ("WIN",  round(win_target, 4))
        if hit_loss:
            return ("LOSS", round(loss_target, 4))

    return (None, None)


# ═══════════════════════════════════════════════════════════
#  DICT BUILDERS
# ═══════════════════════════════════════════════════════════

def build_signal_data(
    ticker: str,
    bar_time: str,
    enhanced: dict,
    indicators: dict,
    entry_price: float,
    atr: float,
    order_flow_data: dict = None,
    session_label: str = "ACTIVE",
    session_modifier: float = 1.0,
) -> dict:
    """
    Build the signal dict that ml_signal_filter.extract_features() expects.
    Mirrors the shape injected in main.py after AI signal generation.
    """
    direction = enhanced["direction"]
    atr_val = atr or 0.0

    # SL/TP from structure levels (already computed inside calculate_enhanced_score)
    structure = enhanced.get("structure_levels", {}) or {}
    sl = structure.get("suggested_sl") or (
        round(entry_price - 1.5 * atr_val, 4) if direction == "LONG"
        else round(entry_price + 1.5 * atr_val, 4)
    )
    tp1 = structure.get("suggested_tp1") or (
        round(entry_price + 2.0 * atr_val, 4) if direction == "LONG"
        else round(entry_price - 2.0 * atr_val, 4)
    )
    rr = abs(tp1 - entry_price) / abs(sl - entry_price) if sl and abs(sl - entry_price) > 0 else 2.0

    order_flow_bias = "NEUTRAL"
    if order_flow_data:
        order_flow_bias = (
            order_flow_data.get("summary", {}).get("overall_delta_bias", "NEUTRAL")
        )

    _scalar = (int, float, str, bool, type(None))
    raw_indicators = {
        k: v for k, v in indicators.items()
        if isinstance(v, _scalar) and k != "computation_error"
    }

    return {
        # Identity
        "ticker": ticker,
        "timestamp_utc": bar_time,
        "timeframe": "1m",
        "source": "csv_backtest",

        # Signal
        "signal": direction,
        "signal_grade": enhanced["grade"],
        "score": enhanced["score"],
        "confidence": min(abs(enhanced["score"]), 100),
        "market_regime": enhanced["regime"],

        # Risk levels
        "entry_zone": {
            "min": round(entry_price * 0.9998, 4),
            "max": round(entry_price * 1.0002, 4),
        },
        "stop_loss": round(sl, 4),
        "take_profit": [{"level": 1, "price": round(tp1, 4)}],
        "risk_reward": round(rr, 2),

        # ML features — must match extract_features() field names exactly
        "factors_aligned": enhanced["factors_aligned"],
        "order_flow_agrees": enhanced["order_flow_agrees"],
        "factor_scores": enhanced.get("factor_scores", {}),
        "confluences": enhanced.get("confluences", []),
        "order_flow_bias": order_flow_bias,

        "mtf_confluence_label": enhanced.get("mtf_confluence_label", "NEUTRAL"),
        "mtf_confluence_multiplier": enhanced.get("mtf_confluence_multiplier", 1.0),

        # Real session context derived from bar timestamp
        "session_modifier": session_modifier,
        "session_label": session_label,
        "correlation_modifier": 1.0,
        "correlation_label": "NEUTRAL",

        "structure_levels": structure,

        # Full raw indicator snapshot
        "raw_indicators": raw_indicators,

        # Provenance / extras
        "agent_agreement_score": 0,
        "reasons": enhanced.get("signals", [])[:5],
        "position_size_pct": 1.0,
        "max_hold_minutes": LOOKAHEAD,
        "invalidation_condition": "Stop loss hit",
        "tv_alert": f"TICKER={ticker};TF=1m;SIG={direction};",
    }


def build_outcome_data(
    signal_data: dict,
    result: str,
    entry_price: float,
    exit_price: float,
) -> dict:
    direction = signal_data["signal"]
    if entry_price and entry_price != 0:
        if direction == "LONG":
            pnl_pct = round((exit_price - entry_price) / entry_price * 100, 4)
        else:
            pnl_pct = round((entry_price - exit_price) / entry_price * 100, 4)
    else:
        pnl_pct = 0.0

    return {
        "ticker": signal_data["ticker"],
        "signal": direction,
        "entry": round(entry_price, 4),
        "result": result,
        "pnl_pct": pnl_pct,
        "notes": (
            f"CSV backtest: grade={signal_data['signal_grade']} "
            f"score={signal_data['score']} "
            f"regime={signal_data['market_regime']}"
        ),
        "reported_at": datetime.utcnow().isoformat() + "Z",
        "source": "csv_backtest",
    }


# ═══════════════════════════════════════════════════════════
#  DIRECT DB INSERT HELPERS (sync, bulk-friendly)
# ═══════════════════════════════════════════════════════════

def _insert_signal(conn: sqlite3.Connection, signal_data: dict) -> None:
    # resolved=1 prevents monitor_active_trades from re-checking these rows
    conn.execute(
        "INSERT INTO signals (data, resolved) VALUES (?, 1)",
        (json.dumps(signal_data),),
    )


def _insert_outcome(conn: sqlite3.Connection, outcome_data: dict) -> None:
    conn.execute(
        "INSERT INTO outcomes (data) VALUES (?)",
        (json.dumps(outcome_data),),
    )


# ═══════════════════════════════════════════════════════════
#  MAIN SEED FUNCTION
# ═══════════════════════════════════════════════════════════

def seed_from_csv(
    filepath: str,
    ticker: str = "NQ",
    min_grade: str = "B",
    max_bars: int = None,
) -> dict:
    """
    Seed the SQLite DB with signal+outcome pairs from a historical CSV file.

    Args:
        filepath:  Path to a CSV file or a directory containing CSV files.
        ticker:    Ticker symbol to label signals with (default: "NQ").
        min_grade: Minimum signal grade to store (default: "B").
                   Only signals graded at or above this level are kept.
        max_bars:  Limit the number of bars processed (useful for smoke tests).

    Returns:
        Stats dict with counts and ML training result.
    """
    _init_db()

    # ── Load data ──
    print(f"[seeder] Loading CSV: {filepath}")
    df = load_csv(filepath)
    total_available = len(df)

    if max_bars:
        df = df.iloc[:max_bars]

    total_bars = len(df)
    print(f"[seeder] Loaded {total_bars:,} bars (of {total_available:,} available)")

    min_required = WARMUP_BARS + LOOKAHEAD + 1
    if total_bars < min_required:
        return {
            "error": f"Insufficient bars: need at least {min_required}, got {total_bars}",
            "total_bars": total_bars,
        }

    # ── Counters ──
    signals_stored     = 0
    outcomes_stored    = 0
    skipped_no_trade   = 0
    skipped_grade      = 0
    skipped_ambiguous  = 0
    skipped_warmup     = 0
    skipped_session    = 0
    computation_errors = 0

    conn = sqlite3.connect(DB_PATH, timeout=60, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")  # allow concurrent reads from FastAPI
    conn.execute("PRAGMA busy_timeout=60000")  # wait up to 60s on lock
    conn.execute("BEGIN")  # start explicit transaction

    try:
        for i in range(total_bars):

            # ── Warmup ──
            if i < WARMUP_BARS:
                skipped_warmup += 1
                continue

            # ── Not enough lookahead ──
            if i + LOOKAHEAD >= total_bars:
                break

            # ── Session filter — London KZ and NY KZ only ──
            bar_time = (
                df.index[i].isoformat() + "Z"
                if isinstance(df.index, pd.DatetimeIndex)
                else datetime.utcnow().isoformat() + "Z"
            )
            sess_label, sess_modifier = _get_session(bar_time)
            if not any(start <= int(bar_time[11:13]) < end for start, end in TRADING_HOURS_UTC):
                skipped_session += 1
                continue

            # ── Rolling window ──
            start = max(0, i - WINDOW + 1)
            window = df.iloc[start : i + 1]

            # ── Indicators ──
            indicators = compute_indicators(window)
            if "error" in indicators or indicators.get("computation_error"):
                computation_errors += 1
                continue

            atr = indicators.get("ATR_14") or 0.0
            if atr <= 0:
                computation_errors += 1
                continue

            entry_price = float(df["Close"].iloc[i])
            if entry_price <= 0:
                computation_errors += 1
                continue

            # ── Seeder quality gates (tighter than live) ──
            adx_val = indicators.get("ADX") or 0.0
            if adx_val < SEEDER_MIN_ADX:
                skipped_grade += 1
                continue

            vol_ratio = indicators.get("volume_ratio") or 0.0
            if vol_ratio < SEEDER_MIN_VOL:
                skipped_grade += 1
                continue

            # ── ICT (optional — fallback to {} on any error) ──
            try:
                ict_data = detect_ict_concepts(window)
            except Exception:
                ict_data = {}

            # ── Order flow (optional) ──
            try:
                order_flow_data = compute_order_flow_summary(window)
            except Exception:
                order_flow_data = {}

            # ── Scoring ──
            enhanced = calculate_enhanced_score(indicators, ict_data, order_flow_data)
            direction = enhanced["direction"]

            if direction == "NO_TRADE":
                skipped_no_trade += 1
                continue

            if not _grade_passes(enhanced["grade"], min_grade):
                skipped_grade += 1
                continue

            # ── Minimum score gate ──
            if abs(enhanced["score"]) < SEEDER_MIN_SCORE:
                skipped_grade += 1
                continue

            # ── Simulate outcome ──
            result, exit_price = simulate_outcome(df, i, direction, atr)
            if result is None:
                skipped_ambiguous += 1
                continue

            signal_data  = build_signal_data(
                ticker, bar_time, enhanced, indicators,
                entry_price, atr, order_flow_data,
                session_label=sess_label,
                session_modifier=sess_modifier,
            )
            outcome_data = build_outcome_data(
                signal_data, result, entry_price, exit_price,
            )

            _insert_signal(conn, signal_data)
            _insert_outcome(conn, outcome_data)
            signals_stored  += 1
            outcomes_stored += 1

            # ── Batch commit ──
            if signals_stored % COMMIT_EVERY == 0:
                conn.execute("COMMIT")
                conn.execute("BEGIN")

            # ── Progress ──
            if signals_stored % PROGRESS_EVERY == 0:
                pct = i / total_bars * 100
                print(
                    f"[seeder] {i:,}/{total_bars:,} bars ({pct:.1f}%) | "
                    f"{signals_stored} signals stored"
                )

        conn.execute("COMMIT")

    finally:
        conn.close()

    # ── Post-seed: trigger ML training if threshold met ──
    ml_result = None
    try:
        ml_result = auto_train_if_ready(DB_PATH)
        if ml_result and "error" not in ml_result:
            print(
                f"[seeder] ML model trained! "
                f"Samples: {ml_result.get('n_samples')} | "
                f"Win rate: {ml_result.get('win_rate')}% | "
                f"Top feature: {ml_result.get('top_features', [['']])[0][0]}"
            )
        elif ml_result and "error" in ml_result:
            print(f"[seeder] ML not ready yet: {ml_result['error']}")
    except Exception as e:
        print(f"[seeder] ML training hook failed: {e}")

    stats = {
        "ticker": ticker,
        "min_grade": min_grade,
        "total_bars_processed": total_bars - skipped_warmup,
        "signals_stored": signals_stored,
        "outcomes_stored": outcomes_stored,
        "skipped_session": skipped_session,
        "skipped_no_trade": skipped_no_trade,
        "skipped_grade": skipped_grade,
        "skipped_ambiguous": skipped_ambiguous,
        "skipped_warmup": skipped_warmup,
        "computation_errors": computation_errors,
        "ml_training": ml_result,
    }

    print("\n[seeder] --- Done -------------------------------------------")
    print(f"  Signals stored:   {signals_stored}")
    print(f"  Outcomes stored:  {outcomes_stored}")
    print(f"  Skipped (NO_TRADE / grade / ambiguous): "
          f"{skipped_no_trade} / {skipped_grade} / {skipped_ambiguous}")
    print(f"  Computation errors: {computation_errors}")
    print(f"  ML model ready: {'YES' if ml_result and 'error' not in (ml_result or {}) else 'NO (need more data)'}")

    return stats


# ═══════════════════════════════════════════════════════════
#  CLI ENTRY POINT
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Seed Trading War Room SQLite DB with historical CSV backtest data.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python csv_backtest_seeder.py nq_1min.csv
  python csv_backtest_seeder.py nq_1min.csv --ticker NQ --min-grade B
  python csv_backtest_seeder.py ./data_dir/ --ticker NQ --min-grade A
  python csv_backtest_seeder.py nq_1min.csv --max-bars 500  # smoke test
        """,
    )
    parser.add_argument("filepath", help="Path to CSV file or directory of CSV files")
    parser.add_argument(
        "--ticker", default="NQ",
        help="Ticker symbol to label signals (default: NQ)",
    )
    parser.add_argument(
        "--min-grade", default="B",
        choices=["A+", "A", "B", "C", "F"],
        help="Minimum signal grade to store (default: B)",
    )
    parser.add_argument(
        "--max-bars", type=int, default=None,
        help="Limit bars processed — useful for smoke tests",
    )

    args = parser.parse_args()

    if not os.path.exists(args.filepath):
        print(f"Error: path not found: {args.filepath}", file=sys.stderr)
        sys.exit(1)

    result = seed_from_csv(
        filepath=args.filepath,
        ticker=args.ticker,
        min_grade=args.min_grade,
        max_bars=args.max_bars,
    )
    print(json.dumps(result, indent=2, default=str))
