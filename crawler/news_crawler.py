"""
StockPulse Crawler - News Crawler
Fetches financial news from RSS feeds and web scraping.
"""

import json
import os
import hashlib
import logging
from datetime import datetime, timedelta

import requests
import feedparser
from bs4 import BeautifulSoup

from .config import (
    NEWS_FEEDS, SCRAPE_TARGETS, STOCK_KEYWORDS,
    DATA_DIR, REQUEST_TIMEOUT, USER_AGENT
)
from .sentiment import analyze_sentiment

logger = logging.getLogger(__name__)

# Maximum age of news articles to keep (in hours)
MAX_NEWS_AGE_HOURS = 72


def generate_news_id(title, source):
    """Generate a unique ID for a news article."""
    raw = f"{title}:{source}".lower().strip()
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def fetch_rss_feed(feed_config):
    """
    Fetch and parse a single RSS feed.

    Args:
        feed_config: Dict with name, url, language, category

    Returns:
        List of news article dicts
    """
    logger.info("Fetching RSS: %s", feed_config["name"])
    articles = []

    try:
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(
            feed_config["url"],
            headers=headers,
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()

        feed = feedparser.parse(response.content)

        for entry in feed.entries[:30]:  # Limit per feed
            title = entry.get("title", "").strip()
            if not title:
                continue

            # Parse publication date
            published = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    published = datetime(*entry.published_parsed[:6]).isoformat()
                except (TypeError, ValueError):
                    published = datetime.now().isoformat()
            else:
                published = datetime.now().isoformat()

            # Extract summary/description
            summary = ""
            if hasattr(entry, "summary"):
                soup = BeautifulSoup(entry.summary, "html.parser")
                summary = soup.get_text()[:300].strip()
            elif hasattr(entry, "description"):
                soup = BeautifulSoup(entry.description, "html.parser")
                summary = soup.get_text()[:300].strip()

            link = entry.get("link", "")

            article = {
                "id": generate_news_id(title, feed_config["name"]),
                "title": title,
                "summary": summary,
                "source": feed_config["name"],
                "url": link,
                "published": published,
                "language": feed_config["language"],
                "category": feed_config.get("category", "general")
            }
            articles.append(article)

    except requests.RequestException as e:
        logger.warning("Failed to fetch %s: %s", feed_config["name"], str(e))
    except Exception as e:
        logger.error("Error parsing %s: %s", feed_config["name"], str(e))

    logger.info("  -> %d articles from %s", len(articles), feed_config["name"])
    return articles


def fetch_google_news(scrape_config):
    """
    Fetch news from Google News RSS search.

    Args:
        scrape_config: Dict with name, url, language

    Returns:
        List of news article dicts
    """
    logger.info("Fetching Google News: %s", scrape_config["name"])
    articles = []

    try:
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(
            scrape_config["url"],
            headers=headers,
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()

        feed = feedparser.parse(response.content)

        for entry in feed.entries[:25]:
            title = entry.get("title", "").strip()
            if not title:
                continue

            # Google News titles often end with " - Source Name"
            source_name = scrape_config["name"]
            if " - " in title:
                parts = title.rsplit(" - ", 1)
                title = parts[0].strip()
                source_name = parts[1].strip()

            published = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    published = datetime(*entry.published_parsed[:6]).isoformat()
                except (TypeError, ValueError):
                    published = datetime.now().isoformat()
            else:
                published = datetime.now().isoformat()

            article = {
                "id": generate_news_id(title, source_name),
                "title": title,
                "summary": "",
                "source": source_name,
                "url": entry.get("link", ""),
                "published": published,
                "language": scrape_config["language"],
                "category": "finance"
            }
            articles.append(article)

    except requests.RequestException as e:
        logger.warning("Failed to fetch %s: %s", scrape_config["name"], str(e))
    except Exception as e:
        logger.error("Error parsing %s: %s", scrape_config["name"], str(e))

    logger.info("  -> %d articles from Google News", len(articles))
    return articles


def match_stocks_to_article(article):
    """
    Determine which stocks are mentioned in a news article.

    Args:
        article: News article dict

    Returns:
        List of stock keys that match
    """
    text = (article["title"] + " " + article.get("summary", "")).lower()
    matched = []

    for stock_key, keywords in STOCK_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in text:
                matched.append(stock_key)
                break

    return matched


def enrich_article(article):
    """
    Add sentiment analysis and stock matching to an article.

    Args:
        article: Raw news article dict

    Returns:
        Enriched article dict
    """
    # Sentiment analysis
    sentiment_result = analyze_sentiment(
        article["title"],
        article.get("summary", "")
    )
    article["sentiment"] = sentiment_result["sentiment"]
    article["sentimentScore"] = sentiment_result["score"]

    # Match to stocks
    article["affectedStocks"] = match_stocks_to_article(article)

    # Calculate relative time
    try:
        pub_time = datetime.fromisoformat(article["published"])
        delta = datetime.now() - pub_time
        hours = int(delta.total_seconds() / 3600)
        if hours < 1:
            article["relativeTime"] = "vor wenigen Minuten"
        elif hours == 1:
            article["relativeTime"] = "vor 1 Stunde"
        elif hours < 24:
            article["relativeTime"] = f"vor {hours} Stunden"
        elif hours < 48:
            article["relativeTime"] = "gestern"
        else:
            days = hours // 24
            article["relativeTime"] = f"vor {days} Tagen"
    except (ValueError, TypeError):
        article["relativeTime"] = "unbekannt"

    return article


def deduplicate_articles(articles):
    """Remove duplicate articles based on their ID."""
    seen = set()
    unique = []
    for article in articles:
        if article["id"] not in seen:
            seen.add(article["id"])
            unique.append(article)
    return unique


def filter_old_articles(articles):
    """Remove articles older than MAX_NEWS_AGE_HOURS."""
    cutoff = datetime.now() - timedelta(hours=MAX_NEWS_AGE_HOURS)
    filtered = []

    for article in articles:
        try:
            pub_time = datetime.fromisoformat(article["published"])
            if pub_time >= cutoff:
                filtered.append(article)
        except (ValueError, TypeError):
            # Keep articles with unparseable dates
            filtered.append(article)

    return filtered


def load_existing_news():
    """Load previously saved news articles."""
    filepath = os.path.join(DATA_DIR, "news.json")
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("articles", [])
        except (json.JSONDecodeError, IOError):
            pass
    return []


def save_news_data(articles):
    """Save news articles to JSON file."""
    os.makedirs(DATA_DIR, exist_ok=True)
    filepath = os.path.join(DATA_DIR, "news.json")

    # Sort by published date (newest first)
    articles.sort(key=lambda a: a.get("published", ""), reverse=True)

    # Compute aggregate stats
    positive = sum(1 for a in articles if a.get("sentiment") == "positive")
    negative = sum(1 for a in articles if a.get("sentiment") == "negative")
    neutral = sum(1 for a in articles if a.get("sentiment") == "neutral")

    output = {
        "lastCrawl": datetime.now().isoformat(),
        "totalArticles": len(articles),
        "sentimentBreakdown": {
            "positive": positive,
            "negative": negative,
            "neutral": neutral
        },
        "articles": articles
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    logger.info("News saved to %s (%d articles)", filepath, len(articles))


def run_news_crawler():
    """Main entry point: fetch all news, analyze, and save."""
    logger.info("=== Starting news crawl ===")
    all_articles = []

    # 1. Fetch from RSS feeds
    for feed_config in NEWS_FEEDS:
        articles = fetch_rss_feed(feed_config)
        all_articles.extend(articles)

    # 2. Fetch from Google News scraping
    for scrape_config in SCRAPE_TARGETS:
        articles = fetch_google_news(scrape_config)
        all_articles.extend(articles)

    # 3. Deduplicate
    all_articles = deduplicate_articles(all_articles)
    logger.info("Total unique articles: %d", len(all_articles))

    # 4. Enrich with sentiment and stock matching
    enriched = []
    for article in all_articles:
        enriched.append(enrich_article(article))

    # 5. Merge with existing news (keep old articles that are still relevant)
    existing = load_existing_news()
    existing_ids = {a["id"] for a in enriched}
    for old_article in existing:
        if old_article["id"] not in existing_ids:
            enriched.append(old_article)

    # 6. Filter old articles
    enriched = filter_old_articles(enriched)
    enriched = deduplicate_articles(enriched)

    # 7. Save
    save_news_data(enriched)

    logger.info("=== News crawl complete: %d articles ===", len(enriched))
    return enriched
