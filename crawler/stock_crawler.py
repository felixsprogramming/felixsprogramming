"""
StockPulse Crawler - Stock Price Crawler
Fetches current and historical stock prices using yfinance.
Stores all data in database - NO LIMITS on history depth or stock count.
"""

import json
import os
import logging
from datetime import datetime, timedelta

import yfinance as yf

from .config import STOCKS, DATA_DIR, DEFAULT_HISTORY_PERIOD, UPDATE_HISTORY_PERIOD
from .database import db, PriceHistory

logger = logging.getLogger(__name__)


def fetch_stock_data(stock_key, stock_config, period="1y"):
    """
    Fetch historical and current price data for a single stock/index.
    No limit on data volume.
    """
    ticker_symbol = stock_config["ticker"]
    logger.info("Fetching %s (%s) period=%s...", stock_config["name"], ticker_symbol, period)

    try:
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(period=period)

        if hist.empty:
            logger.warning("No data returned for %s", ticker_symbol)
            return None

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

        current_price = price_data[-1]["close"]
        prev_price = price_data[-2]["close"]
        change_pct = round((current_price - prev_price) / prev_price * 100, 2)

        return {
            "key": stock_key,
            "name": stock_config["name"],
            "ticker": ticker_symbol,
            "currency": stock_config["currency"],
            "type": stock_config["type"],
            "sector": stock_config.get("sector", ""),
            "exchange": stock_config.get("exchange", ""),
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


def store_stock_in_db(session, stock_key, stock_config, result):
    """Store stock metadata and price history in database."""
    db.upsert_stock(
        session,
        key=stock_key,
        ticker=stock_config["ticker"],
        name=stock_config["name"],
        currency=stock_config["currency"],
        stock_type=stock_config["type"],
        sector=stock_config.get("sector", ""),
        exchange=stock_config.get("exchange", "")
    )

    inserted = db.bulk_insert_prices(session, stock_key, result["history"])
    logger.info("  %s: %d new price records (total history: %d)",
                stock_key, inserted, len(result["history"]))
    return inserted


def run_stock_crawler(initial=False):
    """
    Main entry point: fetch all stock data and store in database.
    On first run (initial=True), fetches maximum history.
    On subsequent runs, fetches recent data only.
    """
    logger.info("=== Starting stock price crawl ===")

    session = db.get_session()
    all_data = {}
    total_inserted = 0

    # Determine fetch period
    period = DEFAULT_HISTORY_PERIOD if initial else UPDATE_HISTORY_PERIOD

    # Check if DB has data already
    existing_count = db.get_price_count(session)
    if existing_count == 0:
        logger.info("Empty database detected, fetching full history (period=%s)", DEFAULT_HISTORY_PERIOD)
        period = DEFAULT_HISTORY_PERIOD

    for stock_key, stock_config in STOCKS.items():
        result = fetch_stock_data(stock_key, stock_config, period=period)
        if result:
            inserted = store_stock_in_db(session, stock_key, stock_config, result)
            total_inserted += inserted
            all_data[stock_key] = result
        else:
            logger.warning("Skipping %s - no data available", stock_key)

    session.commit()

    # Save JSON for frontend
    save_stock_json(all_data)

    price_count = db.get_price_count(session)
    session.close()

    logger.info("=== Stock crawl complete: %d stocks, %d new records, %d total in DB ===",
                len(all_data), total_inserted, price_count)
    return all_data


def save_stock_json(stock_data):
    """Save stock data to JSON file for frontend."""
    os.makedirs(DATA_DIR, exist_ok=True)
    filepath = os.path.join(DATA_DIR, "stocks.json")

    output = {
        "lastCrawl": datetime.now().isoformat(),
        "stocks": stock_data
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
