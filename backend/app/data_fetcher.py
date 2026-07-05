import yfinance as yf
import requests
import difflib
from google import genai
from app.config import settings

# Dictionary of popular Indian stock names/aliases mapped to their official symbols
INDIAN_STOCKS_MAP = {
    "VEDANTA": "VEDL.NS",
    "VEDL": "VEDL.NS",
    "VEDENTA": "VEDL.NS",
    "VEDANT": "VEDL.NS",
    "TATA STEEL": "TATASTEEL.NS",
    "TATASTEEL": "TATASTEEL.NS",
    "TATA SILVER": "TATASTEEL.NS",  # Maps user's specified alias
    "TATASILVER": "TATASTEEL.NS",
    "RELIANCE": "RELIANCE.NS",
    "RELIANCE INDUSTRIES": "RELIANCE.NS",
    "INFOSYS": "INFY.NS",
    "INFY": "INFY.NS",
    "TCS": "TCS.NS",
    "TATA CONSULTANCY": "TCS.NS",
    "WIPRO": "WIPRO.NS",
    "HDFC": "HDFCBANK.NS",
    "HDFCBANK": "HDFCBANK.NS",
    "ICICI": "ICICIBANK.NS",
    "ICICIBANK": "ICICIBANK.NS",
    "SBI": "SBIN.NS",
    "SBIN": "SBIN.NS",
    "STATE BANK OF INDIA": "SBIN.NS",
}

def resolve_ticker_locally(query: str) -> str | None:
    q_clean = query.strip().upper()
    if q_clean in INDIAN_STOCKS_MAP:
        return INDIAN_STOCKS_MAP[q_clean]
    # Fuzzy matching using Python's standard library difflib
    matches = difflib.get_close_matches(q_clean, INDIAN_STOCKS_MAP.keys(), n=1, cutoff=0.7)
    if matches:
        return INDIAN_STOCKS_MAP[matches[0]]
    return None

def search_ticker_by_query(query: str) -> str | None:
    try:
        url = "https://query2.finance.yahoo.com/v1/finance/search"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        params = {
            "q": query,
            "quotesCount": 5,
            "newsCount": 0
        }
        res = requests.get(url, headers=headers, params=params, timeout=5)
        if res.ok:
            data = res.json()
            quotes = data.get("quotes", [])
            if quotes:
                # Prioritize EQUITY quotes (stocks)
                for q in quotes:
                    symbol = q.get("symbol")
                    quote_type = q.get("quoteType")
                    if symbol and quote_type == "EQUITY":
                        return symbol
                return quotes[0].get("symbol")
    except Exception as e:
        print(f"Yahoo Search API error: {e}")
    return None

def resolve_ticker_via_gemini(query: str, model_name: str = "gemini-2.5-flash") -> str | None:
    if not settings.GEMINI_API_KEY or settings.GEMINI_API_KEY == "your_gemini_api_key_here":
        return None
    try:
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        prompt = f"""You are a financial symbol mapping utility.
Given a user query which represents a stock (which might contain typos, spelling errors, or represent a company name), resolve it to the most standard, active ticker symbol on Yahoo Finance.
- If the company is primarily Indian or commonly traded in India (e.g. Vedanta, Tata Steel, Reliance, Infosys, Vedenta), return its National Stock Exchange (NSE) symbol suffixing with '.NS' (e.g. VEDL.NS, TATASTEEL.NS, RELIANCE.NS, INFY.NS).
- Otherwise, return its standard US exchange ticker (e.g. MSFT, AAPL, TSLA).
- Output ONLY the ticker symbol. Do not include markdown, comments, explanation, or whitespace.

User query: "{query}"
Resolved ticker symbol:"""
        response = client.models.generate_content(
            model=model_name,
            contents=prompt
        )
        if response.text:
            resolved = response.text.strip().upper()
            # Clean up potential markdown formatting like code blocks
            resolved = resolved.replace("`", "").strip()
            return resolved
    except Exception as e:
        print(f"Gemini ticker resolution error: {e}")
    return None

def validate_and_fetch_stock_data(ticker_symbol: str, model_name: str = "gemini-2.5-flash") -> dict:
    normalized_ticker = ticker_symbol.strip().upper()
    
    # Ticker candidates starting with the user input
    candidates = [normalized_ticker]
    
    # 1. Try local dictionary fuzzy resolver first (completely off-grid & instant)
    local_resolved = resolve_ticker_locally(normalized_ticker)
    if local_resolved:
        local_upper = local_resolved.upper()
        if local_upper not in candidates:
            candidates.append(local_upper)
            
    # 2. Try fuzzy lookup via Yahoo Search API
    searched_symbol = search_ticker_by_query(normalized_ticker)
    if searched_symbol:
        searched_upper = searched_symbol.upper()
        if searched_upper not in candidates:
            candidates.append(searched_upper)
            
    # 3. Try AI lookup via Gemini if local/Yahoo search yielded nothing new
    if len(candidates) <= 1:
        ai_symbol = resolve_ticker_via_gemini(normalized_ticker, model_name)
        if ai_symbol:
            ai_upper = ai_symbol.upper()
            if ai_upper not in candidates:
                candidates.append(ai_upper)
                
    # 4. Default suffix fallbacks
    if "." not in normalized_ticker:
        ns_cand = f"{normalized_ticker}.NS"
        bo_cand = f"{normalized_ticker}.BO"
        if ns_cand not in candidates:
            candidates.append(ns_cand)
        if bo_cand not in candidates:
            candidates.append(bo_cand)
        
    last_error = None
    for symbol in candidates:
        try:
            ticker = yf.Ticker(symbol)
            # Fetch 1 month of history to ensure we can get 7 close prices
            hist = ticker.history(period="1mo")
            if hist.empty:
                raise ValueError("No trading history returned.")
                
            close_prices = hist['Close'].tail(7).tolist()
            if len(close_prices) == 0:
                raise ValueError("No price data returned in history.")
                
            # Extract metrics from info
            info = ticker.info or {}
            
            current_price = info.get("currentPrice") or info.get("regularMarketPrice")
            if not current_price:
                current_price = hist['Close'].iloc[-1]
                
            company_name = info.get("longName") or info.get("shortName") or symbol
            trailing_pe = info.get("trailingPE")
            market_cap = info.get("marketCap")
            fifty_two_week_high = info.get("fiftyTwoWeekHigh")
            fifty_two_week_low = info.get("fiftyTwoWeekLow")
            
            # Extract trading volume
            volume = info.get("volume") or info.get("regularMarketVolume")
            if not volume and 'Volume' in hist.columns and not hist.empty:
                volume = int(hist['Volume'].iloc[-1])
                
            # Calculate 52-week bounds from 1-year history if missing
            if not fifty_two_week_high or not fifty_two_week_low:
                hist_1y = ticker.history(period="1y")
                if not hist_1y.empty:
                    if not fifty_two_week_high:
                        fifty_two_week_high = float(hist_1y['High'].max())
                    if not fifty_two_week_low:
                        fifty_two_week_low = float(hist_1y['Low'].min())
                        
            # Final fallbacks to avoid zero
            fifty_two_week_high = float(fifty_two_week_high) if fifty_two_week_high else float(current_price)
            fifty_two_week_low = float(fifty_two_week_low) if fifty_two_week_low else float(current_price)
            
            return {
                "ticker": symbol,  # Return the successfully matched candidate symbol
                "company_name": company_name,
                "current_price": float(current_price),
                "trailing_pe": float(trailing_pe) if trailing_pe else None,
                "market_cap": int(market_cap) if market_cap else None,
                "fifty_two_week_high": fifty_two_week_high,
                "fifty_two_week_low": fifty_two_week_low,
                "price_history_7d": [float(p) for p in close_prices],
                "volume": int(volume) if volume else None,
            }
        except Exception as e:
            last_error = e
            continue
            
    raise ValueError(f"Ticker '{ticker_symbol}' is invalid or could not be fetched: {str(last_error)}")

def _compute_rsi(closes: list, period: int = 14) -> list:
    """Compute RSI values for a list of closing prices."""
    if len(closes) < period + 1:
        return [50.0] * len(closes)
    rsi = [None] * period
    deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    gains = [max(d, 0) for d in deltas]
    losses = [abs(min(d, 0)) for d in deltas]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(closes) - 1):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        rs = avg_gain / avg_loss if avg_loss != 0 else 100
        rsi.append(round(100 - (100 / (1 + rs)), 2))
    return rsi

def _compute_ema(closes: list, period: int) -> list:
    """Compute Exponential Moving Average."""
    ema = [None] * (period - 1)
    sma = sum(closes[:period]) / period
    ema.append(round(sma, 2))
    multiplier = 2 / (period + 1)
    for price in closes[period:]:
        ema.append(round((price - ema[-1]) * multiplier + ema[-1], 2))
    return ema

def _compute_sma(closes: list, period: int) -> list:
    """Compute Simple Moving Average."""
    sma = []
    for i in range(len(closes)):
        if i < period - 1:
            sma.append(None)
        else:
            sma.append(round(sum(closes[i - period + 1:i + 1]) / period, 2))
    return sma

def _compute_bollinger_bands(closes: list, period: int = 20, std_dev: float = 2.0) -> dict:
    """Compute Bollinger Bands (mid, upper, lower)."""
    mid, upper, lower = [], [], []
    for i in range(len(closes)):
        if i < period - 1:
            mid.append(None); upper.append(None); lower.append(None)
        else:
            window = closes[i - period + 1:i + 1]
            m = sum(window) / period
            variance = sum((x - m) ** 2 for x in window) / period
            std = variance ** 0.5
            mid.append(round(m, 2))
            upper.append(round(m + std_dev * std, 2))
            lower.append(round(m - std_dev * std, 2))
    return {"mid": mid, "upper": upper, "lower": lower}

def _compute_macd(closes: list) -> dict:
    """Compute MACD line, signal line, and histogram."""
    ema12 = _compute_ema(closes, 12)
    ema26 = _compute_ema(closes, 26)
    macd_line = [
        round(ema12[i] - ema26[i], 4) if (ema12[i] is not None and ema26[i] is not None) else None
        for i in range(len(closes))
    ]
    valid_macd = [v for v in macd_line if v is not None]
    signal_raw = _compute_ema(valid_macd, 9)
    signal_line = [None] * (len(macd_line) - len(signal_raw)) + signal_raw
    histogram = [
        round(macd_line[i] - signal_line[i], 4)
        if (macd_line[i] is not None and signal_line[i] is not None) else None
        for i in range(len(closes))
    ]
    return {"macd": macd_line, "signal": signal_line, "histogram": histogram}

def fetch_rich_market_data(ticker_symbol: str, period: str = "3mo") -> dict:
    """
    Fetch full OHLCV history plus computed technical indicators for a ticker.
    period can be: 1mo, 3mo, 6mo, 1y
    """
    ticker = yf.Ticker(ticker_symbol)
    hist = ticker.history(period=period)
    if hist.empty:
        raise ValueError(f"No market data available for {ticker_symbol}")

    dates = [d.strftime("%Y-%m-%d") for d in hist.index]
    opens   = [round(float(v), 2) for v in hist["Open"].tolist()]
    highs   = [round(float(v), 2) for v in hist["High"].tolist()]
    lows    = [round(float(v), 2) for v in hist["Low"].tolist()]
    closes  = [round(float(v), 2) for v in hist["Close"].tolist()]
    volumes = [int(v) for v in hist["Volume"].tolist()]

    info = ticker.info or {}
    current_price = info.get("currentPrice") or info.get("regularMarketPrice") or closes[-1]
    company_name  = info.get("longName") or info.get("shortName") or ticker_symbol
    market_cap    = info.get("marketCap")
    trailing_pe   = info.get("trailingPE")
    forward_pe    = info.get("forwardPE")
    dividend_yield = info.get("dividendYield")
    beta          = info.get("beta")
    sector        = info.get("sector") or "N/A"
    industry      = info.get("industry") or "N/A"
    week52_high   = info.get("fiftyTwoWeekHigh") or max(highs)
    week52_low    = info.get("fiftyTwoWeekLow") or min(lows)
    avg_volume    = info.get("averageVolume") or (sum(volumes) // len(volumes) if volumes else 0)

    # Technical indicators
    ma20  = _compute_sma(closes, 20)
    ma50  = _compute_sma(closes, 50)
    ma200 = _compute_sma(closes, 200)
    rsi   = _compute_rsi(closes, 14)
    bb    = _compute_bollinger_bands(closes, 20)
    macd  = _compute_macd(closes)

    # Latest indicator snapshot for signal panel
    last_rsi   = next((v for v in reversed(rsi) if v is not None), 50)
    last_ma20  = next((v for v in reversed(ma20) if v is not None), None)
    last_ma50  = next((v for v in reversed(ma50) if v is not None), None)
    last_bb_upper = next((v for v in reversed(bb["upper"]) if v is not None), None)
    last_bb_lower = next((v for v in reversed(bb["lower"]) if v is not None), None)
    last_macd_hist = next((v for v in reversed(macd["histogram"]) if v is not None), 0)

    signals = {
        "rsi_value": last_rsi,
        "rsi_signal": "OVERBOUGHT" if last_rsi > 70 else ("OVERSOLD" if last_rsi < 30 else "NEUTRAL"),
        "ma_cross": (
            "GOLDEN_CROSS" if (last_ma20 and last_ma50 and last_ma20 > last_ma50)
            else "DEATH_CROSS" if (last_ma20 and last_ma50 and last_ma20 < last_ma50)
            else "NEUTRAL"
        ),
        "bb_position": (
            "NEAR_UPPER" if (last_bb_upper and closes[-1] >= last_bb_upper * 0.98)
            else "NEAR_LOWER" if (last_bb_lower and closes[-1] <= last_bb_lower * 1.02)
            else "MID"
        ),
        "volume_trend": "ABOVE_AVG" if (volumes and avg_volume and volumes[-1] > avg_volume) else "BELOW_AVG",
        "macd_signal": "BULLISH" if last_macd_hist > 0 else "BEARISH",
        "price_vs_52w_high_pct": round((closes[-1] / week52_high - 1) * 100, 2) if week52_high else 0,
        "price_vs_52w_low_pct":  round((closes[-1] / week52_low  - 1) * 100, 2) if week52_low else 0,
    }

    return {
        "ticker": ticker_symbol,
        "company_name": company_name,
        "current_price": float(current_price),
        "market_cap": int(market_cap) if market_cap else None,
        "trailing_pe": float(trailing_pe) if trailing_pe else None,
        "forward_pe":  float(forward_pe)  if forward_pe  else None,
        "dividend_yield": float(dividend_yield) if dividend_yield else None,
        "beta": float(beta) if beta else None,
        "sector": sector,
        "industry": industry,
        "week52_high": float(week52_high),
        "week52_low":  float(week52_low),
        "avg_volume": int(avg_volume),
        "period": period,
        "dates":   dates,
        "opens":   opens,
        "highs":   highs,
        "lows":    lows,
        "closes":  closes,
        "volumes": volumes,
        "ma20":  ma20,
        "ma50":  ma50,
        "ma200": ma200,
        "rsi":    rsi,
        "bb":     bb,
        "macd":   macd,
        "signals": signals,
    }

