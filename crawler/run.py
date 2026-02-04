#!/usr/bin/env python3
"""
StockPulse Crawler - Main Runner
Runs the stock and news crawlers on a scheduled interval.

Usage:
    python -m crawler.run              # Run once
    python -m crawler.run --daemon     # Run continuously every hour
    python -m crawler.run --stocks     # Only crawl stocks
    python -m crawler.run --news       # Only crawl news
"""

import argparse
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime

# Add parent dir to path so we can run as module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawler.stock_crawler import run_stock_crawler
from crawler.news_crawler import run_news_crawler
from crawler.config import CRAWL_INTERVAL, DATA_DIR

# --- Logging Setup ---
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    datefmt=LOG_DATE_FORMAT,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "crawler.log"
            ),
            encoding="utf-8"
        )
    ]
)

logger = logging.getLogger("StockPulse")

# Graceful shutdown flag
running = True


def signal_handler(signum, frame):
    global running
    logger.info("Shutdown signal received. Finishing current crawl...")
    running = False


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def generate_frontend_data():
    """
    Combine stock and news data into a single JSON file
    that the frontend can load directly.
    """
    stocks_file = os.path.join(DATA_DIR, "stocks.json")
    news_file = os.path.join(DATA_DIR, "news.json")
    output_file = os.path.join(DATA_DIR, "live_data.json")

    stocks_data = {}
    news_data = {}

    if os.path.exists(stocks_file):
        with open(stocks_file, "r", encoding="utf-8") as f:
            stocks_data = json.load(f)

    if os.path.exists(news_file):
        with open(news_file, "r", encoding="utf-8") as f:
            news_data = json.load(f)

    # Build combined output for frontend
    combined = {
        "lastUpdate": datetime.now().isoformat(),
        "stocks": stocks_data.get("stocks", {}),
        "news": {
            "articles": news_data.get("articles", [])[:50],  # Limit for frontend
            "sentimentBreakdown": news_data.get("sentimentBreakdown", {}),
            "totalArticles": news_data.get("totalArticles", 0)
        }
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(combined, f, ensure_ascii=False, indent=2)

    logger.info("Frontend data written to %s", output_file)


def run_full_crawl():
    """Execute a full crawl cycle: stocks + news + frontend data generation."""
    start_time = time.time()
    logger.info("=" * 60)
    logger.info("CRAWL CYCLE STARTED at %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("=" * 60)

    errors = []

    # 1. Crawl stock prices
    try:
        stock_data = run_stock_crawler()
        logger.info("Stocks: %d updated", len(stock_data))
    except Exception as e:
        logger.error("Stock crawler failed: %s", str(e))
        errors.append(f"Stock crawler: {e}")

    # 2. Crawl news
    try:
        news_data = run_news_crawler()
        logger.info("News: %d articles", len(news_data))
    except Exception as e:
        logger.error("News crawler failed: %s", str(e))
        errors.append(f"News crawler: {e}")

    # 3. Generate combined frontend data
    try:
        generate_frontend_data()
    except Exception as e:
        logger.error("Frontend data generation failed: %s", str(e))
        errors.append(f"Frontend data: {e}")

    elapsed = time.time() - start_time
    logger.info("-" * 60)
    if errors:
        logger.warning("Crawl completed with %d error(s) in %.1fs", len(errors), elapsed)
        for err in errors:
            logger.warning("  - %s", err)
    else:
        logger.info("Crawl completed successfully in %.1fs", elapsed)
    logger.info("=" * 60)


def run_daemon():
    """Run the crawler in daemon mode (every CRAWL_INTERVAL seconds)."""
    logger.info("StockPulse Crawler starting in DAEMON mode")
    logger.info("Crawl interval: %d seconds (%d minutes)",
                CRAWL_INTERVAL, CRAWL_INTERVAL // 60)
    logger.info("Data directory: %s", DATA_DIR)

    while running:
        run_full_crawl()

        if not running:
            break

        logger.info("Next crawl in %d minutes. Waiting...", CRAWL_INTERVAL // 60)

        # Sleep in small intervals to allow graceful shutdown
        sleep_end = time.time() + CRAWL_INTERVAL
        while running and time.time() < sleep_end:
            time.sleep(5)

    logger.info("StockPulse Crawler stopped.")


def main():
    parser = argparse.ArgumentParser(
        description="StockPulse Web Crawler - Fetches stock prices and financial news"
    )
    parser.add_argument(
        "--daemon", action="store_true",
        help="Run continuously with hourly crawl interval"
    )
    parser.add_argument(
        "--stocks", action="store_true",
        help="Only crawl stock prices"
    )
    parser.add_argument(
        "--news", action="store_true",
        help="Only crawl news"
    )
    parser.add_argument(
        "--interval", type=int, default=None,
        help="Custom crawl interval in seconds (daemon mode only)"
    )

    args = parser.parse_args()

    # Ensure data directory exists
    os.makedirs(DATA_DIR, exist_ok=True)

    if args.interval:
        global CRAWL_INTERVAL
        CRAWL_INTERVAL = args.interval

    if args.stocks:
        logger.info("Running stock crawler only...")
        run_stock_crawler()
        generate_frontend_data()
    elif args.news:
        logger.info("Running news crawler only...")
        run_news_crawler()
        generate_frontend_data()
    elif args.daemon:
        run_daemon()
    else:
        # Single run
        run_full_crawl()


if __name__ == "__main__":
    main()
