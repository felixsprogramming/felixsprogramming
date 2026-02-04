"""
StockPulse Crawler - Configuration
Defines all tracked stocks, indices, news sources, and settings.
"""

import os

# Base directory for data output
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

# Crawl interval in seconds (3600 = 1 hour)
CRAWL_INTERVAL = 3600

# --- Stock / Index Configuration ---
# Yahoo Finance ticker symbols
STOCKS = {
    "dax": {
        "ticker": "^GDAXI",
        "name": "DAX",
        "currency": "EUR",
        "type": "index"
    },
    "dowjones": {
        "ticker": "^DJI",
        "name": "Dow Jones",
        "currency": "USD",
        "type": "index"
    },
    "sp500": {
        "ticker": "^GSPC",
        "name": "S&P 500",
        "currency": "USD",
        "type": "index"
    },
    "nasdaq": {
        "ticker": "^IXIC",
        "name": "NASDAQ",
        "currency": "USD",
        "type": "index"
    },
    "apple": {
        "ticker": "AAPL",
        "name": "Apple",
        "currency": "USD",
        "type": "stock"
    },
    "microsoft": {
        "ticker": "MSFT",
        "name": "Microsoft",
        "currency": "USD",
        "type": "stock"
    },
    "tesla": {
        "ticker": "TSLA",
        "name": "Tesla",
        "currency": "USD",
        "type": "stock"
    },
    "nvidia": {
        "ticker": "NVDA",
        "name": "NVIDIA",
        "currency": "USD",
        "type": "stock"
    },
    "amazon": {
        "ticker": "AMZN",
        "name": "Amazon",
        "currency": "USD",
        "type": "stock"
    },
    "alphabet": {
        "ticker": "GOOGL",
        "name": "Alphabet",
        "currency": "USD",
        "type": "stock"
    },
    "siemens": {
        "ticker": "SIE.DE",
        "name": "Siemens",
        "currency": "EUR",
        "type": "stock"
    },
    "sap": {
        "ticker": "SAP.DE",
        "name": "SAP",
        "currency": "EUR",
        "type": "stock"
    }
}

# --- News RSS Feed Sources ---
NEWS_FEEDS = [
    {
        "name": "Reuters Business",
        "url": "https://www.reutersagency.com/feed/?best-topics=business-finance&post_type=best",
        "language": "en",
        "category": "finance"
    },
    {
        "name": "CNBC Top News",
        "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
        "language": "en",
        "category": "finance"
    },
    {
        "name": "Yahoo Finance",
        "url": "https://finance.yahoo.com/news/rssindex",
        "language": "en",
        "category": "finance"
    },
    {
        "name": "MarketWatch",
        "url": "http://feeds.marketwatch.com/marketwatch/topstories/",
        "language": "en",
        "category": "finance"
    },
    {
        "name": "Handelsblatt",
        "url": "https://www.handelsblatt.com/contentexport/feed/finanzen",
        "language": "de",
        "category": "finance"
    },
    {
        "name": "Tagesschau Wirtschaft",
        "url": "https://www.tagesschau.de/wirtschaft/index~rss2.xml",
        "language": "de",
        "category": "economy"
    },
    {
        "name": "Financial Times",
        "url": "https://www.ft.com/?format=rss",
        "language": "en",
        "category": "finance"
    },
    {
        "name": "Bloomberg Markets",
        "url": "https://feeds.bloomberg.com/markets/news.rss",
        "language": "en",
        "category": "finance"
    }
]

# --- Web Scraping Targets (fallback news sources) ---
SCRAPE_TARGETS = [
    {
        "name": "Google Finance News",
        "url": "https://news.google.com/rss/search?q=stock+market+aktien&hl=de&gl=DE&ceid=DE:de",
        "language": "de"
    },
    {
        "name": "Google Finance News EN",
        "url": "https://news.google.com/rss/search?q=stock+market+nasdaq+dow+jones&hl=en&gl=US&ceid=US:en",
        "language": "en"
    }
]

# --- Stock-related search keywords for news matching ---
STOCK_KEYWORDS = {
    "dax": ["dax", "deutscher aktienindex", "frankfurt", "xetra", "deutsche boerse"],
    "dowjones": ["dow jones", "dow", "djia", "wall street"],
    "sp500": ["s&p 500", "s&p500", "sp500", "standard and poor"],
    "nasdaq": ["nasdaq", "tech stocks", "tech-aktien"],
    "apple": ["apple", "aapl", "iphone", "tim cook", "apple inc"],
    "microsoft": ["microsoft", "msft", "azure", "satya nadella", "windows", "copilot"],
    "tesla": ["tesla", "tsla", "elon musk", "elektroauto", "ev market"],
    "nvidia": ["nvidia", "nvda", "gpu", "jensen huang", "ki-chip", "ai chip"],
    "amazon": ["amazon", "amzn", "aws", "jeff bezos", "andy jassy"],
    "alphabet": ["alphabet", "google", "googl", "sundar pichai", "youtube"],
    "siemens": ["siemens", "sie.de", "siemens ag"],
    "sap": ["sap", "sap se", "sap.de", "walldorf"]
}

# Request settings
REQUEST_TIMEOUT = 15
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
