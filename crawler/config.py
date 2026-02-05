"""
BBF-Trading Crawler - Configuration
All tracked stocks, indices, news sources, and settings.
NO LIMITS on data volume, article count, or number of tracked assets.
"""

import os

# Base directory for data output
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

# Crawl interval in seconds (3600 = 1 hour)
CRAWL_INTERVAL = 3600

# Default history period for yfinance (max available)
DEFAULT_HISTORY_PERIOD = "max"
# Shorter period for hourly updates
UPDATE_HISTORY_PERIOD = "5d"

# AI Model settings
AI_MODEL_DIR = os.path.join(DATA_DIR, "models")
MIN_TRAINING_SAMPLES = 50  # Minimum samples before training
PREDICTION_TIMEFRAME_DAYS = 7
# Set to True to use HuggingFace transformer for sentiment (requires GPU recommended)
USE_TRANSFORMER_SENTIMENT = False

# --- Stock / Index Configuration ---
# NO LIMIT on number of tracked assets. Add as many as needed.
STOCKS = {
    # ---- Major Indices ----
    "dax": {"ticker": "^GDAXI", "name": "DAX", "currency": "EUR", "type": "index", "sector": "index", "exchange": "XETRA"},
    "dowjones": {"ticker": "^DJI", "name": "Dow Jones", "currency": "USD", "type": "index", "sector": "index", "exchange": "NYSE"},
    "sp500": {"ticker": "^GSPC", "name": "S&P 500", "currency": "USD", "type": "index", "sector": "index", "exchange": "NYSE"},
    "nasdaq": {"ticker": "^IXIC", "name": "NASDAQ Composite", "currency": "USD", "type": "index", "sector": "index", "exchange": "NASDAQ"},
    "nasdaq100": {"ticker": "^NDX", "name": "NASDAQ 100", "currency": "USD", "type": "index", "sector": "index", "exchange": "NASDAQ"},
    "ftse100": {"ticker": "^FTSE", "name": "FTSE 100", "currency": "GBP", "type": "index", "sector": "index", "exchange": "LSE"},
    "nikkei225": {"ticker": "^N225", "name": "Nikkei 225", "currency": "JPY", "type": "index", "sector": "index", "exchange": "TSE"},
    "eurostoxx50": {"ticker": "^STOXX50E", "name": "Euro Stoxx 50", "currency": "EUR", "type": "index", "sector": "index", "exchange": "EUREX"},
    "hangseng": {"ticker": "^HSI", "name": "Hang Seng", "currency": "HKD", "type": "index", "sector": "index", "exchange": "HKEX"},
    "cac40": {"ticker": "^FCHI", "name": "CAC 40", "currency": "EUR", "type": "index", "sector": "index", "exchange": "EURONEXT"},
    "russell2000": {"ticker": "^RUT", "name": "Russell 2000", "currency": "USD", "type": "index", "sector": "index", "exchange": "NYSE"},
    "vix": {"ticker": "^VIX", "name": "VIX Volatility", "currency": "USD", "type": "index", "sector": "volatility", "exchange": "CBOE"},

    # ---- US Mega Cap / Tech ----
    "apple": {"ticker": "AAPL", "name": "Apple", "currency": "USD", "type": "stock", "sector": "technology", "exchange": "NASDAQ"},
    "microsoft": {"ticker": "MSFT", "name": "Microsoft", "currency": "USD", "type": "stock", "sector": "technology", "exchange": "NASDAQ"},
    "nvidia": {"ticker": "NVDA", "name": "NVIDIA", "currency": "USD", "type": "stock", "sector": "technology", "exchange": "NASDAQ"},
    "alphabet": {"ticker": "GOOGL", "name": "Alphabet", "currency": "USD", "type": "stock", "sector": "technology", "exchange": "NASDAQ"},
    "amazon": {"ticker": "AMZN", "name": "Amazon", "currency": "USD", "type": "stock", "sector": "technology", "exchange": "NASDAQ"},
    "meta": {"ticker": "META", "name": "Meta Platforms", "currency": "USD", "type": "stock", "sector": "technology", "exchange": "NASDAQ"},
    "tesla": {"ticker": "TSLA", "name": "Tesla", "currency": "USD", "type": "stock", "sector": "automotive", "exchange": "NASDAQ"},
    "broadcom": {"ticker": "AVGO", "name": "Broadcom", "currency": "USD", "type": "stock", "sector": "technology", "exchange": "NASDAQ"},
    "tsmc": {"ticker": "TSM", "name": "TSMC", "currency": "USD", "type": "stock", "sector": "technology", "exchange": "NYSE"},
    "oracle": {"ticker": "ORCL", "name": "Oracle", "currency": "USD", "type": "stock", "sector": "technology", "exchange": "NYSE"},
    "amd": {"ticker": "AMD", "name": "AMD", "currency": "USD", "type": "stock", "sector": "technology", "exchange": "NASDAQ"},
    "intel": {"ticker": "INTC", "name": "Intel", "currency": "USD", "type": "stock", "sector": "technology", "exchange": "NASDAQ"},
    "salesforce": {"ticker": "CRM", "name": "Salesforce", "currency": "USD", "type": "stock", "sector": "technology", "exchange": "NYSE"},
    "adobe": {"ticker": "ADBE", "name": "Adobe", "currency": "USD", "type": "stock", "sector": "technology", "exchange": "NASDAQ"},
    "netflix": {"ticker": "NFLX", "name": "Netflix", "currency": "USD", "type": "stock", "sector": "technology", "exchange": "NASDAQ"},
    "palantir": {"ticker": "PLTR", "name": "Palantir", "currency": "USD", "type": "stock", "sector": "technology", "exchange": "NYSE"},
    "snowflake": {"ticker": "SNOW", "name": "Snowflake", "currency": "USD", "type": "stock", "sector": "technology", "exchange": "NYSE"},

    # ---- US Finance ----
    "jpmorgan": {"ticker": "JPM", "name": "JPMorgan Chase", "currency": "USD", "type": "stock", "sector": "finance", "exchange": "NYSE"},
    "goldmansachs": {"ticker": "GS", "name": "Goldman Sachs", "currency": "USD", "type": "stock", "sector": "finance", "exchange": "NYSE"},
    "berkshire": {"ticker": "BRK-B", "name": "Berkshire Hathaway", "currency": "USD", "type": "stock", "sector": "finance", "exchange": "NYSE"},
    "visa": {"ticker": "V", "name": "Visa", "currency": "USD", "type": "stock", "sector": "finance", "exchange": "NYSE"},
    "mastercard": {"ticker": "MA", "name": "Mastercard", "currency": "USD", "type": "stock", "sector": "finance", "exchange": "NYSE"},

    # ---- US Healthcare / Pharma ----
    "unitedhealth": {"ticker": "UNH", "name": "UnitedHealth", "currency": "USD", "type": "stock", "sector": "healthcare", "exchange": "NYSE"},
    "jnj": {"ticker": "JNJ", "name": "Johnson & Johnson", "currency": "USD", "type": "stock", "sector": "healthcare", "exchange": "NYSE"},
    "pfizer": {"ticker": "PFE", "name": "Pfizer", "currency": "USD", "type": "stock", "sector": "healthcare", "exchange": "NYSE"},
    "lilly": {"ticker": "LLY", "name": "Eli Lilly", "currency": "USD", "type": "stock", "sector": "healthcare", "exchange": "NYSE"},
    "novonordisk": {"ticker": "NVO", "name": "Novo Nordisk", "currency": "USD", "type": "stock", "sector": "healthcare", "exchange": "NYSE"},

    # ---- US Consumer / Retail ----
    "walmart": {"ticker": "WMT", "name": "Walmart", "currency": "USD", "type": "stock", "sector": "retail", "exchange": "NYSE"},
    "costco": {"ticker": "COST", "name": "Costco", "currency": "USD", "type": "stock", "sector": "retail", "exchange": "NASDAQ"},
    "mcdonalds": {"ticker": "MCD", "name": "McDonald's", "currency": "USD", "type": "stock", "sector": "consumer", "exchange": "NYSE"},
    "cocacola": {"ticker": "KO", "name": "Coca-Cola", "currency": "USD", "type": "stock", "sector": "consumer", "exchange": "NYSE"},
    "disney": {"ticker": "DIS", "name": "Walt Disney", "currency": "USD", "type": "stock", "sector": "consumer", "exchange": "NYSE"},

    # ---- US Energy ----
    "exxon": {"ticker": "XOM", "name": "ExxonMobil", "currency": "USD", "type": "stock", "sector": "energy", "exchange": "NYSE"},
    "chevron": {"ticker": "CVX", "name": "Chevron", "currency": "USD", "type": "stock", "sector": "energy", "exchange": "NYSE"},

    # ---- German / DAX ----
    "siemens": {"ticker": "SIE.DE", "name": "Siemens", "currency": "EUR", "type": "stock", "sector": "industrial", "exchange": "XETRA"},
    "sap": {"ticker": "SAP.DE", "name": "SAP", "currency": "EUR", "type": "stock", "sector": "technology", "exchange": "XETRA"},
    "allianz": {"ticker": "ALV.DE", "name": "Allianz", "currency": "EUR", "type": "stock", "sector": "finance", "exchange": "XETRA"},
    "deutschebank": {"ticker": "DBK.DE", "name": "Deutsche Bank", "currency": "EUR", "type": "stock", "sector": "finance", "exchange": "XETRA"},
    "bmw": {"ticker": "BMW.DE", "name": "BMW", "currency": "EUR", "type": "stock", "sector": "automotive", "exchange": "XETRA"},
    "mercedes": {"ticker": "MBG.DE", "name": "Mercedes-Benz", "currency": "EUR", "type": "stock", "sector": "automotive", "exchange": "XETRA"},
    "volkswagen": {"ticker": "VOW3.DE", "name": "Volkswagen", "currency": "EUR", "type": "stock", "sector": "automotive", "exchange": "XETRA"},
    "basf": {"ticker": "BAS.DE", "name": "BASF", "currency": "EUR", "type": "stock", "sector": "chemicals", "exchange": "XETRA"},
    "bayer": {"ticker": "BAYN.DE", "name": "Bayer", "currency": "EUR", "type": "stock", "sector": "healthcare", "exchange": "XETRA"},
    "adidas": {"ticker": "ADS.DE", "name": "Adidas", "currency": "EUR", "type": "stock", "sector": "consumer", "exchange": "XETRA"},
    "deutschetelekom": {"ticker": "DTE.DE", "name": "Deutsche Telekom", "currency": "EUR", "type": "stock", "sector": "telecom", "exchange": "XETRA"},
    "infineon": {"ticker": "IFX.DE", "name": "Infineon", "currency": "EUR", "type": "stock", "sector": "technology", "exchange": "XETRA"},
    "rheinmetall": {"ticker": "RHM.DE", "name": "Rheinmetall", "currency": "EUR", "type": "stock", "sector": "defense", "exchange": "XETRA"},
    "siemensenergy": {"ticker": "ENR.DE", "name": "Siemens Energy", "currency": "EUR", "type": "stock", "sector": "energy", "exchange": "XETRA"},

    # ---- European ----
    "asml": {"ticker": "ASML", "name": "ASML", "currency": "EUR", "type": "stock", "sector": "technology", "exchange": "EURONEXT"},
    "lvmh": {"ticker": "MC.PA", "name": "LVMH", "currency": "EUR", "type": "stock", "sector": "luxury", "exchange": "EURONEXT"},
    "nestle": {"ticker": "NESN.SW", "name": "Nestle", "currency": "CHF", "type": "stock", "sector": "consumer", "exchange": "SIX"},
    "shell": {"ticker": "SHEL", "name": "Shell", "currency": "GBP", "type": "stock", "sector": "energy", "exchange": "LSE"},
    "totalenergies": {"ticker": "TTE.PA", "name": "TotalEnergies", "currency": "EUR", "type": "stock", "sector": "energy", "exchange": "EURONEXT"},
}

# --- News RSS Feed Sources (NO LIMIT on feeds) ---
NEWS_FEEDS = [
    # English - Major
    {"name": "Reuters Business", "url": "https://www.reutersagency.com/feed/?best-topics=business-finance&post_type=best", "language": "en", "category": "finance"},
    {"name": "CNBC Top News", "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114", "language": "en", "category": "finance"},
    {"name": "CNBC World", "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100727362", "language": "en", "category": "finance"},
    {"name": "Yahoo Finance", "url": "https://finance.yahoo.com/news/rssindex", "language": "en", "category": "finance"},
    {"name": "MarketWatch Top", "url": "http://feeds.marketwatch.com/marketwatch/topstories/", "language": "en", "category": "finance"},
    {"name": "MarketWatch Stocks", "url": "http://feeds.marketwatch.com/marketwatch/marketpulse/", "language": "en", "category": "stocks"},
    {"name": "Bloomberg Markets", "url": "https://feeds.bloomberg.com/markets/news.rss", "language": "en", "category": "finance"},
    {"name": "Financial Times", "url": "https://www.ft.com/?format=rss", "language": "en", "category": "finance"},
    {"name": "Investing.com News", "url": "https://www.investing.com/rss/news.rss", "language": "en", "category": "finance"},
    {"name": "Seeking Alpha", "url": "https://seekingalpha.com/market_currents.xml", "language": "en", "category": "analysis"},
    {"name": "The Motley Fool", "url": "https://www.fool.com/feeds/index.aspx", "language": "en", "category": "analysis"},
    {"name": "WSJ Markets", "url": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml", "language": "en", "category": "finance"},
    {"name": "WSJ World", "url": "https://feeds.a.dj.com/rss/RSSWorldNews.xml", "language": "en", "category": "world"},
    {"name": "Barrons", "url": "https://www.barrons.com/market-data/rss", "language": "en", "category": "finance"},

    # German
    {"name": "Handelsblatt Finanzen", "url": "https://www.handelsblatt.com/contentexport/feed/finanzen", "language": "de", "category": "finance"},
    {"name": "Handelsblatt Unternehmen", "url": "https://www.handelsblatt.com/contentexport/feed/unternehmen", "language": "de", "category": "business"},
    {"name": "Tagesschau Wirtschaft", "url": "https://www.tagesschau.de/wirtschaft/index~rss2.xml", "language": "de", "category": "economy"},
    {"name": "FAZ Finanzen", "url": "https://www.faz.net/rss/aktuell/finanzen/", "language": "de", "category": "finance"},
    {"name": "Boerse.de News", "url": "https://www.boerse.de/rss/news.rss", "language": "de", "category": "stocks"},
    {"name": "Der Aktionaer", "url": "https://www.deraktionaer.de/rss/alle-news.xml", "language": "de", "category": "stocks"},
    {"name": "n-tv Boerse", "url": "https://www.n-tv.de/wirtschaft/rss", "language": "de", "category": "economy"},
    {"name": "Manager Magazin", "url": "https://www.manager-magazin.de/finanzen/index.rss", "language": "de", "category": "finance"},
    {"name": "Spiegel Wirtschaft", "url": "https://www.spiegel.de/wirtschaft/index.rss", "language": "de", "category": "economy"},
]

# --- Web Scraping Targets (Google News - unlimited results) ---
SCRAPE_TARGETS = [
    {"name": "Google News DE Aktien", "url": "https://news.google.com/rss/search?q=aktien+boerse+dax&hl=de&gl=DE&ceid=DE:de", "language": "de"},
    {"name": "Google News DE Wirtschaft", "url": "https://news.google.com/rss/search?q=wirtschaft+unternehmen+finanzen&hl=de&gl=DE&ceid=DE:de", "language": "de"},
    {"name": "Google News EN Stocks", "url": "https://news.google.com/rss/search?q=stock+market+wall+street&hl=en&gl=US&ceid=US:en", "language": "en"},
    {"name": "Google News EN Tech", "url": "https://news.google.com/rss/search?q=tech+stocks+nvidia+apple+microsoft&hl=en&gl=US&ceid=US:en", "language": "en"},
    {"name": "Google News EN Economy", "url": "https://news.google.com/rss/search?q=fed+inflation+economy+interest+rates&hl=en&gl=US&ceid=US:en", "language": "en"},
    {"name": "Google News Crypto", "url": "https://news.google.com/rss/search?q=bitcoin+crypto+ethereum&hl=en&gl=US&ceid=US:en", "language": "en"},
]

# --- Stock-related search keywords for news matching ---
# Auto-generated from STOCKS + manual additions for better matching
STOCK_KEYWORDS = {}
for _key, _cfg in STOCKS.items():
    keywords = [_key, _cfg["name"].lower(), _cfg["ticker"].lower().replace("^", "")]
    # Add ticker without exchange suffix
    if "." in _cfg["ticker"]:
        keywords.append(_cfg["ticker"].split(".")[0].lower())
    STOCK_KEYWORDS[_key] = keywords

# Manual keyword additions for better matching
_EXTRA_KEYWORDS = {
    "dax": ["deutscher aktienindex", "frankfurt", "xetra", "deutsche boerse", "leitindex"],
    "dowjones": ["dow jones", "djia", "wall street", "industrieaktien"],
    "sp500": ["s&p 500", "s&p500", "standard and poor", "standard & poor"],
    "nasdaq": ["tech stocks", "tech-aktien", "technologieboerse"],
    "apple": ["iphone", "tim cook", "apple inc", "app store", "macbook", "ios"],
    "microsoft": ["azure", "satya nadella", "windows", "copilot", "office 365", "openai partner", "bing"],
    "nvidia": ["gpu", "jensen huang", "ki-chip", "ai chip", "cuda", "geforce", "h100", "blackwell"],
    "alphabet": ["google", "sundar pichai", "youtube", "waymo", "android", "gemini ai"],
    "amazon": ["aws", "andy jassy", "prime", "alexa", "e-commerce"],
    "meta": ["facebook", "instagram", "whatsapp", "mark zuckerberg", "metaverse", "threads"],
    "tesla": ["elon musk", "elektroauto", "ev market", "gigafactory", "cybertruck", "robotaxi", "autopilot"],
    "amd": ["lisa su", "radeon", "ryzen", "epyc"],
    "jpmorgan": ["jamie dimon", "jp morgan", "chase bank"],
    "berkshire": ["warren buffett", "charlie munger"],
    "siemens": ["siemens ag", "healthineers"],
    "sap": ["sap se", "walldorf", "hana"],
    "bmw": ["bayerische motoren", "mini", "rolls-royce cars"],
    "mercedes": ["daimler", "mercedes-benz", "amg"],
    "volkswagen": ["vw", "porsche", "audi", "wolfsburg"],
    "deutschebank": ["deutsche bank"],
    "deutschetelekom": ["telekom", "t-mobile"],
    "basf": ["ludwigshafen", "basf se"],
    "bayer": ["monsanto", "bayer ag", "leverkusen"],
    "asml": ["lithografie", "euv", "halbleiter equipment"],
    "lvmh": ["louis vuitton", "bernard arnault", "dior", "luxus"],
    "pfizer": ["biontech partner", "impfstoff", "vaccine"],
    "lilly": ["eli lilly", "mounjaro", "ozempic konkurrent"],
    "novonordisk": ["novo nordisk", "wegovy", "ozempic"],
    "rheinmetall": ["ruestung", "defense", "munition", "panzer"],
}
for _k, _v in _EXTRA_KEYWORDS.items():
    if _k in STOCK_KEYWORDS:
        STOCK_KEYWORDS[_k].extend(_v)

# Request settings
REQUEST_TIMEOUT = 20
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


def add_custom_stock(stock_key, name, ticker, keywords):
    """
    Add a custom stock to the STOCKS and STOCK_KEYWORDS dictionaries.
    This allows dynamically adding user-specified stocks for tracking.

    Parameters:
        stock_key: Unique key for the stock (e.g., "aapl", "bmw_de")
        name: Display name for the stock (e.g., "Apple Inc.")
        ticker: Yahoo Finance ticker symbol (e.g., "AAPL", "BMW.DE")
        keywords: List of search keywords for news matching

    Note: This also persists the stock to the database via the db module.
    """
    # Determine currency and exchange from ticker
    currency = "USD"
    exchange = "NASDAQ"
    if ".DE" in ticker.upper():
        currency = "EUR"
        exchange = "XETRA"
    elif ".PA" in ticker.upper():
        currency = "EUR"
        exchange = "EURONEXT"
    elif ".L" in ticker.upper():
        currency = "GBP"
        exchange = "LSE"
    elif ".SW" in ticker.upper():
        currency = "CHF"
        exchange = "SIX"

    # Add to STOCKS dict
    STOCKS[stock_key] = {
        "ticker": ticker,
        "name": name,
        "currency": currency,
        "type": "stock",
        "sector": "custom",
        "exchange": exchange
    }

    # Add to STOCK_KEYWORDS
    if stock_key not in STOCK_KEYWORDS:
        STOCK_KEYWORDS[stock_key] = []
    STOCK_KEYWORDS[stock_key].extend(keywords)

    # Deduplicate keywords
    STOCK_KEYWORDS[stock_key] = list(set(STOCK_KEYWORDS[stock_key]))

    # Persist to database
    from .database import db as db_manager
    session = db_manager.get_session()
    try:
        db_manager.upsert_stock(
            session,
            key=stock_key,
            ticker=ticker,
            name=name,
            currency=currency,
            stock_type="stock",
            sector="custom",
            exchange=exchange
        )
        session.commit()
    finally:
        session.close()
