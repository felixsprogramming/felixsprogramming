"""
StockPulse Crawler - Stock Price Crawler
Fetches current and historical stock prices using yfinance.
"""

import json
import os
import logging
from datetime import datetime, timedelta

import yfinance as yf

from .config import STOCKS, DATA_DIR

logger = logging.getLogger(__name__)


def fetch_stock_data(stock_key, stock_config, period="1y"):
    """
    Fetch historical and current price data for a single stock/index.

    Args:
        stock_key: Internal key (e.g. 'dax', 'apple')
        stock_config: Config dict with ticker, name, etc.
        period: yfinance period string ('1mo', '3mo', '6mo', '1y', '5y')

    Returns:
        dict with stock data or None on failure
    """
    ticker_symbol = stock_config["ticker"]
    logger.info("Fetching data for %s (%s)...", stock_config["name"], ticker_symbol)

    try:
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(period=period)

        if hist.empty:
            logger.warning("No data returned for %s", ticker_symbol)
            return None

        # Convert to list of {date, open, high, low, close, volume}
        price_data = []
        for date, row in hist.iterrows():
            price_data.append({
                "date": date.strftime("%Y-%m-%d"),
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"])
            })

        if len(price_data) < 2:
            return None

        # Current values
        current_price = price_data[-1]["close"]
        prev_price = price_data[-2]["close"]
        change_pct = round((current_price - prev_price) / prev_price * 100, 2)

        return {
            "key": stock_key,
            "name": stock_config["name"],
            "ticker": ticker_symbol,
            "currency": stock_config["currency"],
            "type": stock_config["type"],
            "currentPrice": current_price,
            "previousClose": prev_price,
            "changePercent": change_pct,
            "dayHigh": price_data[-1]["high"],
            "dayLow": price_data[-1]["low"],
            "volume": price_data[-1]["volume"],
            "history": price_data,
            "lastUpdated": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error("Error fetching %s: %s", ticker_symbol, str(e))
        return None


def fetch_all_stocks():
    """
    Fetch data for all configured stocks and indices.

    Returns:
        dict mapping stock_key -> stock data
    """
    all_data = {}

    for stock_key, stock_config in STOCKS.items():
        result = fetch_stock_data(stock_key, stock_config, period="1y")
        if result:
            all_data[stock_key] = result
        else:
            logger.warning("Skipping %s - no data available", stock_key)

    return all_data


def fetch_long_history():
    """
    Fetch 5-year history for indices (used for historical analysis page).

    Returns:
        dict mapping index_key -> price history
    """
    indices = {k: v for k, v in STOCKS.items() if v["type"] == "index"}
    long_data = {}

    for stock_key, stock_config in indices.items():
        result = fetch_stock_data(stock_key, stock_config, period="5y")
        if result:
            long_data[stock_key] = result["history"]

    return long_data


def save_stock_data(stock_data):
    """Save stock data to JSON file."""
    os.makedirs(DATA_DIR, exist_ok=True)
    filepath = os.path.join(DATA_DIR, "stocks.json")

    output = {
        "lastCrawl": datetime.now().isoformat(),
        "stocks": stock_data
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    logger.info("Stock data saved to %s (%d stocks)", filepath, len(stock_data))


def save_long_history(history_data):
    """Save long-term history to separate JSON file."""
    os.makedirs(DATA_DIR, exist_ok=True)
    filepath = os.path.join(DATA_DIR, "history.json")

    output = {
        "lastCrawl": datetime.now().isoformat(),
        "indices": history_data
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    logger.info("Long history saved to %s", filepath)


def run_stock_crawler():
    """Main entry point: fetch all stock data and save."""
    logger.info("=== Starting stock price crawl ===")
    stock_data = fetch_all_stocks()
    save_stock_data(stock_data)

    # Fetch long history less frequently (check if file is older than 24h)
    history_file = os.path.join(DATA_DIR, "history.json")
    should_fetch_history = True

    if os.path.exists(history_file):
        mod_time = datetime.fromtimestamp(os.path.getmtime(history_file))
        if datetime.now() - mod_time < timedelta(hours=24):
            should_fetch_history = False
            logger.info("Long history is recent, skipping...")

    if should_fetch_history:
        logger.info("Fetching long-term history...")
        long_data = fetch_long_history()
        save_long_history(long_data)

    logger.info("=== Stock crawl complete: %d stocks updated ===", len(stock_data))
    return stock_data
