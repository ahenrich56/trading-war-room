import anthropic
import json
import os
from logger import log

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def analyze_market(market: dict, current_yes_price: float) -> dict:
    """
    Send market details to Claude and get probability estimate.
    Returns: { estimated_prob, confidence, reasoning, trade_signal }
    """
    question = market.get("question", "")
    description = market.get("description", "")
    end_date = market.get("endDate", "unknown")
    category = market.get("category", "general")

    prompt = f"""You are an expert prediction market analyst. Analyze this Polymarket market and estimate the TRUE probability of the YES outcome.

MARKET QUESTION: {question}
DESCRIPTION: {description}
CATEGORY: {category}
CLOSES: {end_date}
CURRENT MARKET YES PRICE: {current_yes_price} (this represents the crowd's implied probability)

Based on your knowledge of this topic, world events, and base rates:

1. What is the TRUE probability this resolves YES? (0.0 to 1.0)
2. How confident are you in your estimate? (low/medium/high)
3. Brief reasoning (2-3 sentences max)
4. Is there a mispricing edge here? The current market price is {current_yes_price}

Respond ONLY in valid JSON format:
{{
  "estimated_prob": 0.XX,
  "confidence": "low|medium|high",
  "reasoning": "your brief reasoning here",
  "edge": 0.XX,
  "direction": "buy_yes|buy_no|no_trade",
  "urgency": "low|medium|high"
}}

If edge = |estimated_prob - {current_yes_price}| and direction = buy_yes if estimated_prob > market price, buy_no if lower."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}]
        )

        raw = response.content[0].text.strip()
        # Clean JSON if wrapped in markdown
        if "```" in raw:
            raw = raw.split("```json")[-1].split("```")[0].strip()

        result = json.loads(raw)
        result["question"] = question
        result["condition_id"] = market.get("conditionId")
        log.info(f"Claude analysis: {question[:60]}... | Edge: {result.get('edge', 0):.2f} | Dir: {result.get('direction')}")
        return result

    except json.JSONDecodeError as e:
        log.error(f"Claude JSON parse error: {e} | Raw: {raw}")
        return {"direction": "no_trade", "edge": 0}
    except Exception as e:
        log.error(f"Claude API error: {e}")
        return {"direction": "no_trade", "edge": 0}
