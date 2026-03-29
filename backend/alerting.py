"""
Multi-Channel Alert Engine.

Sends trading signals to Discord (webhook) and enhances the existing
Telegram integration with session/correlation/COT context.

Discord webhooks require no bot token — just a webhook URL from channel settings.
"""

import os
from datetime import datetime


DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")


async def send_discord_alert(signal_data: dict, session: dict = None, correlation: dict = None, cot: dict = None):
    """
    Send a formatted signal alert to Discord via webhook.

    Args:
        signal_data: The signal payload from SIGNAL_ENGINE
        session: Session/killzone context
        correlation: Intermarket correlation data
        cot: COT positioning data
    """
    if not DISCORD_WEBHOOK_URL:
        return

    try:
        sig = signal_data.get("signal", "UNKNOWN")
        ticker = signal_data.get("ticker", "???")
        tf = signal_data.get("timeframe", "?")
        confidence = signal_data.get("confidence", 0)
        entry = signal_data.get("entry_zone", {})
        sl = signal_data.get("stop_loss", 0)
        tps = signal_data.get("take_profit", [])
        rr = signal_data.get("risk_reward", 0)
        grade = signal_data.get("signal_grade", "?")
        regime = signal_data.get("market_regime", "unknown")
        reasons = signal_data.get("reasons", [])
        factors = signal_data.get("factors_aligned", 0)

        # Color: green for LONG, red for SHORT, grey for NO_TRADE
        color = 0x00FF00 if sig == "LONG" else 0xFF0000 if sig == "SHORT" else 0x808080

        # Build target lines
        tp_text = ""
        for tp in tps:
            tp_text += f"TP{tp.get('level', '?')}: `{tp.get('price', 0)}`\n"

        # Session context
        session_text = ""
        if session:
            session_text = f"**Session:** {session.get('label', 'Unknown')}"
            if session.get("is_killzone"):
                session_text += " ⚡ KILLZONE"
            session_text += "\n"

        # Correlation context
        corr_text = ""
        if correlation and correlation.get("label") != "NEUTRAL":
            corr_text = f"**Intermarket:** {correlation.get('label', 'N/A')}"
            corr_reasons = correlation.get("reasons", [])
            if corr_reasons:
                corr_text += f" — {corr_reasons[0]}"
            corr_text += "\n"

        # COT context
        cot_text = ""
        if cot:
            interp = cot.get("interpretation", {})
            cot_bias = interp.get("bias", "NEUTRAL")
            if cot_bias != "NEUTRAL":
                cot_signals = interp.get("signals", [])
                cot_text = f"**COT Bias:** {cot_bias}"
                if cot_signals:
                    cot_text += f" — {cot_signals[0]}"
                cot_text += "\n"

        reason_text = "\n".join(f"• {r}" for r in reasons[:4])

        embed = {
            "title": f"{'🟢' if sig == 'LONG' else '🔴' if sig == 'SHORT' else '⚪'} {sig} {ticker} ({tf})",
            "color": color,
            "fields": [
                {"name": "Grade", "value": f"`{grade}`", "inline": True},
                {"name": "Confidence", "value": f"`{confidence}%`", "inline": True},
                {"name": "R:R", "value": f"`{rr}`", "inline": True},
                {"name": "Entry", "value": f"`{entry.get('min', 0)} - {entry.get('max', 0)}`", "inline": True},
                {"name": "Stop Loss", "value": f"`{sl}`", "inline": True},
                {"name": "Factors", "value": f"`{factors}/5`", "inline": True},
            ],
            "description": (
                f"{session_text}{corr_text}{cot_text}"
                f"**Regime:** {regime}\n"
                f"**Targets:**\n{tp_text}\n"
                f"**Rationale:**\n{reason_text}"
            ),
            "footer": {"text": f"War Room Signal • {datetime.utcnow().strftime('%H:%M UTC')}"},
        }

        payload = {
            "embeds": [embed],
        }

        import httpx
        async with httpx.AsyncClient() as client:
            await client.post(
                DISCORD_WEBHOOK_URL,
                json=payload,
                timeout=5,
            )

    except Exception as e:
        print(f"Discord alert failed: {e}")


def build_enhanced_telegram_message(signal_data: dict, session: dict = None, correlation: dict = None, cot: dict = None) -> str:
    """
    Build an enhanced Telegram message with session/correlation/COT context.
    Returns formatted message string for use with existing send_telegram_alert.
    """
    sig = signal_data.get("signal", "UNKNOWN")
    ticker = signal_data.get("ticker", "???")
    tf = signal_data.get("timeframe", "?")
    confidence = signal_data.get("confidence", 0)
    entry = signal_data.get("entry_zone", {})
    sl = signal_data.get("stop_loss", 0)
    tps = signal_data.get("take_profit", [])
    rr = signal_data.get("risk_reward", 0)
    grade = signal_data.get("signal_grade", "?")
    regime = signal_data.get("market_regime", "unknown")
    reasons = signal_data.get("reasons", [])
    factors = signal_data.get("factors_aligned", 0)

    emoji = "🟢" if sig == "LONG" else "🔴" if sig == "SHORT" else "⚪"

    tp_lines = ""
    for tp in tps:
        tp_lines += f"  TP{tp.get('level', '?')}: `{tp.get('price', 0)}`\n"

    reason_lines = "\n".join(f"  • {r}" for r in reasons[:3])

    # Session line
    session_line = ""
    if session:
        session_line = f"📍 Session: `{session.get('label', 'Unknown')}`"
        if session.get("is_killzone"):
            session_line += " ⚡"
        session_line += "\n"

    # Correlation line
    corr_line = ""
    if correlation and correlation.get("label") not in ("NEUTRAL", "NO_DATA", "ERROR"):
        corr_line = f"🔗 Intermarket: `{correlation.get('label', 'N/A')}` ({correlation.get('confidence_modifier', 1.0)}x)\n"

    # COT line
    cot_line = ""
    if cot:
        interp = cot.get("interpretation", {})
        cot_bias = interp.get("bias", "NEUTRAL")
        if cot_bias != "NEUTRAL":
            cot_line = f"🏛 COT: `{cot_bias}`\n"

    message = (
        f"{emoji} *WAR ROOM SIGNAL*\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"*{sig}* `{ticker}` on `{tf}` | Grade `{grade}` | {factors}/5 factors\n"
        f"Regime: `{regime}`\n"
        f"{session_line}{corr_line}{cot_line}\n"
        f"📍 *Entry:* `{entry.get('min', 0)} - {entry.get('max', 0)}`\n"
        f"🛑 *Stop:* `{sl}`\n"
        f"🎯 *Targets:*\n{tp_lines}\n"
        f"📊 R:R `{rr}` | Conf `{confidence}%`\n\n"
        f"💡 *Rationale:*\n{reason_lines}\n\n"
        f"🕐 {datetime.utcnow().strftime('%H:%M UTC')}"
    )

    return message
