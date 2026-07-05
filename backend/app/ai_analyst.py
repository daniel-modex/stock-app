import json
from google import genai
from app.config import settings

def analyze_stock(ticker: str, metrics: dict, model_name: str = "gemini-2.5-flash",
                  holding_context: dict | None = None) -> str:
    """
    Generate an AI analytical report. Returns a markdown string that ends with
    a fenced JSON block containing a structured verdict for frontend parsing:
    ```json
    {"verdict": "BUY|SELL|HOLD", "confidence": 0-100, "key_reasons": ["...", ...]}
    ```
    """
    if not settings.GEMINI_API_KEY or settings.GEMINI_API_KEY == "your_gemini_api_key_here":
        verdict_json = json.dumps({"verdict": "HOLD", "confidence": 50, "key_reasons": ["No API key configured — cannot generate real analysis."]})
        return f"""# AI Research Report: {ticker}

> [!WARNING]
> **Gemini API Key is not configured.** Please set a valid `GEMINI_API_KEY` in your `.env` configuration file to unlock full AI analytical reports.

## Captured Financial Vector
- **Current Price**: ₹{metrics.get('current_price'):,.2f}
- **Trailing P/E**: {f"{metrics.get('trailing_pe'):.2f}" if metrics.get('trailing_pe') is not None else "N/A"}
- **Market Cap**: {f"₹{metrics.get('market_cap'):,}" if metrics.get('market_cap') is not None else "N/A"}
- **52-Week Bounds**: ₹{metrics.get('fifty_two_week_low') or metrics.get('week52_low', 0):,.2f} – ₹{metrics.get('fifty_two_week_high') or metrics.get('week52_high', 0):,.2f}

```json
{verdict_json}
```"""

    holding_section = ""
    if holding_context:
        qty   = holding_context.get("quantity", 0)
        avg   = holding_context.get("average_buy_price", 0)
        curr  = metrics.get("current_price", 0)
        pnl   = (curr - avg) * qty
        pnl_p = ((curr - avg) / avg * 100) if avg else 0
        holding_section = f"""
## User's Current Position
- **Shares Held**: {qty}
- **Average Buy Price**: ₹{avg:,.2f}
- **Current Market Price**: ₹{curr:,.2f}
- **Unrealized P&L**: ₹{pnl:,.2f} ({pnl_p:+.2f}%)
Take this position into account when forming the verdict (e.g. advise SELL if the position is deeply profitable and technicals are deteriorating).
"""

    signals_section = ""
    if "signals" in metrics:
        s = metrics["signals"]
        signals_section = f"""
## Technical Indicator Signals
- **RSI ({s.get('rsi_value', 'N/A')})**: {s.get('rsi_signal', 'N/A')}
- **MA Cross**: {s.get('ma_cross', 'N/A')}
- **Bollinger Band Position**: {s.get('bb_position', 'N/A')}
- **MACD**: {s.get('macd_signal', 'N/A')}
- **Volume Trend**: {s.get('volume_trend', 'N/A')}
- **Distance from 52W High**: {s.get('price_vs_52w_high_pct', 'N/A')}%
- **Distance from 52W Low**: {s.get('price_vs_52w_low_pct', 'N/A')}%
"""

    try:
        client = genai.Client(api_key=settings.GEMINI_API_KEY)

        prompt = f"""You are an elite quantitative equity analyst covering Indian and global markets.

## Assignment
Provide a rigorous analytical report for **{ticker}** ({metrics.get('company_name', ticker)}).

## Fundamental Metrics
- Sector: {metrics.get('sector', 'N/A')} | Industry: {metrics.get('industry', 'N/A')}
- Current Price: ₹{metrics.get('current_price', 0):,.2f}
- Market Cap: {f"₹{metrics.get('market_cap'):,}" if metrics.get('market_cap') else 'N/A'}
- Trailing P/E: {metrics.get('trailing_pe', 'N/A')} | Forward P/E: {metrics.get('forward_pe', 'N/A')}
- Beta: {metrics.get('beta', 'N/A')} | Dividend Yield: {metrics.get('dividend_yield', 'N/A')}
- 52W High: ₹{metrics.get('week52_high', 0):,.2f} | 52W Low: ₹{metrics.get('week52_low', 0):,.2f}
- 7-Day Price History: {metrics.get('price_history_7d') or metrics.get('closes', [])[-7:]}
{signals_section}
{holding_section}

## Report Structure (write clean Markdown)
1. **Valuation Assessment** — P/E analysis, market cap context, sector comparison.
2. **Price Momentum & Technicals** — Interpret RSI, MA crossover, Bollinger Bands, MACD signals coherently.
3. **Risk Factors** — Macro risks, sector risks, volatility considerations.
4. **Investment Verdict** — A decisive BUY / SELL / HOLD recommendation with clear reasoning.
   {"Consider the user's existing position and P&L when advising." if holding_context else ""}

## MANDATORY — End your response with this exact fenced JSON block (fill in the values):
```json
{{"verdict": "BUY or SELL or HOLD", "confidence": <integer 0-100>, "key_reasons": ["reason 1", "reason 2", "reason 3"]}}
```
The JSON must be valid, the verdict must be exactly one of BUY/SELL/HOLD, confidence is your certainty percentage."""

        response = client.models.generate_content(model=model_name, contents=prompt)

        if not response.text:
            raise ValueError("Empty response from Gemini API.")

        return response.text

    except Exception as e:
        verdict_json = json.dumps({"verdict": "HOLD", "confidence": 0,
                                    "key_reasons": [f"Analysis failed: {str(e)[:100]}"]})
        return f"""# AI Research Report: {ticker}

> [!CAUTION]
> **AI Generation Fault**: {str(e)}

## Raw Metrics
- Current Price: ₹{metrics.get('current_price', 0):,.2f}
- 52W Range: ₹{metrics.get('week52_low', 0):,.2f} – ₹{metrics.get('week52_high', 0):,.2f}

```json
{verdict_json}
```"""
