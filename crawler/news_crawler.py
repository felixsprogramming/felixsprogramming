"""
BBF-Trading Crawler - News Crawler
Fetches financial news from RSS feeds and web scraping.
Stores ALL articles in database - NO LIMITS on article count.
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
from .database import db

logger = logging.getLogger(__name__)


def generate_news_id(title, source):
    """Generate a unique ID for a news article."""
    raw = f"{title}:{source}".lower().strip()
    return hashlib.md5(raw.encode()).hexdigest()


def fetch_rss_feed(feed_config):
    """Fetch and parse a single RSS feed. No article limit per feed."""
    logger.info("Fetching RSS: %s", feed_config["name"])
    articles = []

    try:
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(
            feed_config["url"], headers=headers, timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        feed = feedparser.parse(response.content)

        for entry in feed.entries:  # NO LIMIT - take all entries
            title = entry.get("title", "").strip()
            if not title:
                continue

            published = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    published = datetime(*entry.published_parsed[:6])
                except (TypeError, ValueError):
                    published = datetime.now()
            else:
                published = datetime.now()

            summary = ""
            if hasattr(entry, "summary"):
                soup = BeautifulSoup(entry.summary, "html.parser")
                summary = soup.get_text()[:500].strip()
            elif hasattr(entry, "description"):
                soup = BeautifulSoup(entry.description, "html.parser")
                summary = soup.get_text()[:500].strip()

            article = {
                "article_hash": generate_news_id(title, feed_config["name"]),
                "title": title,
                "summary": summary,
                "source": feed_config["name"],
                "url": entry.get("link", ""),
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
    """Fetch news from Google News RSS search. No limit."""
    logger.info("Fetching Google News: %s", scrape_config["name"])
    articles = []

    try:
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(
            scrape_config["url"], headers=headers, timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        feed = feedparser.parse(response.content)

        for entry in feed.entries:  # NO LIMIT
            title = entry.get("title", "").strip()
            if not title:
                continue

            source_name = scrape_config["name"]
            if " - " in title:
                parts = title.rsplit(" - ", 1)
                title = parts[0].strip()
                source_name = parts[1].strip()

            published = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    published = datetime(*entry.published_parsed[:6])
                except (TypeError, ValueError):
                    published = datetime.now()
            else:
                published = datetime.now()

            article = {
                "article_hash": generate_news_id(title, source_name),
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
    """Determine which stocks are mentioned in a news article."""
    text = (article["title"] + " " + article.get("summary", "")).lower()
    matched = []

    for stock_key, keywords in STOCK_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in text:
                matched.append(stock_key)
                break

    return matched


def enrich_article(article):
    """Add sentiment analysis and stock matching to an article."""
    sentiment_result = analyze_sentiment(
        article["title"], article.get("summary", "")
    )
    article["sentiment"] = sentiment_result["sentiment"]
    article["sentiment_score"] = sentiment_result["score"]
    article["sentiment_confidence"] = sentiment_result["confidence"]
    article["sentiment_model"] = "keyword"
    article["affected_stocks"] = ",".join(match_stocks_to_article(article))
    return article


def relative_time(published):
    """Calculate relative time string."""
    try:
        delta = datetime.now() - published
        hours = int(delta.total_seconds() / 3600)
        if hours < 1:
            return "vor wenigen Minuten"
        elif hours == 1:
            return "vor 1 Stunde"
        elif hours < 24:
            return f"vor {hours} Stunden"
        elif hours < 48:
            return "gestern"
        else:
            return f"vor {hours // 24} Tagen"
    except (ValueError, TypeError):
        return "unbekannt"


def run_news_crawler():
    """Main entry point: fetch all news, analyze, store in DB. No limits."""
    logger.info("=== Starting news crawl ===")
    all_articles = []

    # 1. Fetch from all RSS feeds
    for feed_config in NEWS_FEEDS:
        articles = fetch_rss_feed(feed_config)
        all_articles.extend(articles)

    # 2. Fetch from Google News scraping
    for scrape_config in SCRAPE_TARGETS:
        articles = fetch_google_news(scrape_config)
        all_articles.extend(articles)

    # 3. Deduplicate by hash
    seen = set()
    unique_articles = []
    for article in all_articles:
        if article["article_hash"] not in seen:
            seen.add(article["article_hash"])
            unique_articles.append(article)

    logger.info("Total unique articles this crawl: %d", len(unique_articles))

    # 4. Enrich with sentiment and stock matching
    for article in unique_articles:
        enrich_article(article)

    # 5. Store ALL in database (duplicates auto-skipped by hash)
    session = db.get_session()
    inserted = db.bulk_insert_articles(session, unique_articles)
    session.commit()

    total_in_db = db.get_news_count(session)

    # 6. Update sentiment timeseries aggregates
    update_sentiment_aggregates(session, unique_articles)
    session.commit()

    # 7. Save recent news as JSON for frontend
    save_news_json(session)

    session.close()

    logger.info("=== News crawl complete: %d new articles, %d total in DB ===",
                inserted, total_in_db)
    return unique_articles


def update_sentiment_aggregates(session, articles):
    """Update daily sentiment aggregates per stock."""
    from collections import defaultdict

    # Group articles by stock and date
    stock_date_articles = defaultdict(list)
    for article in articles:
        stocks = article.get("affected_stocks", "").split(",")
        date_str = article["published"].strftime("%Y-%m-%d") if isinstance(article["published"], datetime) else str(article["published"])[:10]
        for stock_key in stocks:
            stock_key = stock_key.strip()
            if stock_key:
                stock_date_articles[(stock_key, date_str)].append(article)

    for (stock_key, date_str), arts in stock_date_articles.items():
        scores = [a.get("sentiment_score", 0) for a in arts]
        sentiments = [a.get("sentiment", "neutral") for a in arts]
        avg_score = sum(scores) / len(scores) if scores else 0

        db.update_sentiment_timeseries(
            session, stock_key, date_str,
            avg_sentiment=round(avg_score, 3),
            news_count=len(arts),
            pos_count=sentiments.count("positive"),
            neg_count=sentiments.count("negative"),
            neu_count=sentiments.count("neutral")
        )


def save_news_json(session):
    """Save recent news to JSON for frontend consumption."""
    os.makedirs(DATA_DIR, exist_ok=True)
    filepath = os.path.join(DATA_DIR, "news.json")

    recent = db.get_recent_news(session, hours=72)

    articles_out = []
    for article in recent:
        articles_out.append({
            "id": article.article_hash,
            "title": article.title,
            "summary": article.summary,
            "source": article.source,
            "url": article.url,
            "published": article.published.isoformat() if article.published else "",
            "language": article.language,
            "category": article.category,
            "sentiment": article.sentiment,
            "sentimentScore": article.sentiment_score,
            "affectedStocks": article.affected_stocks.split(",") if article.affected_stocks else [],
            "relativeTime": relative_time(article.published) if article.published else "unbekannt"
        })

    positive = sum(1 for a in articles_out if a["sentiment"] == "positive")
    negative = sum(1 for a in articles_out if a["sentiment"] == "negative")
    neutral = sum(1 for a in articles_out if a["sentiment"] == "neutral")

    output = {
        "lastCrawl": datetime.now().isoformat(),
        "totalArticles": len(articles_out),
        "sentimentBreakdown": {
            "positive": positive, "negative": negative, "neutral": neutral
        },
        "articles": articles_out
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)


def search_news_for_stock(stock_key, keywords, session):
    """
    Search for news articles related to a specific stock using Google News RSS.
    This function is used for custom crawling of user-specified stocks.

    Parameters:
        stock_key: Unique key for the stock (e.g., "aapl", "bmw_de")
        keywords: List of keywords to search for
        session: SQLAlchemy database session

    Returns:
        int: Number of new articles found and stored
    """
    logger.info("Searching news for %s with keywords: %s", stock_key, keywords)

    all_articles = []

    # Build search queries from keywords
    for keyword in keywords[:3]:  # Limit to first 3 keywords to avoid too many requests
        # German Google News search
        de_url = f"https://news.google.com/rss/search?q={requests.utils.quote(keyword)}&hl=de&gl=DE&ceid=DE:de"
        # English Google News search
        en_url = f"https://news.google.com/rss/search?q={requests.utils.quote(keyword)}&hl=en&gl=US&ceid=US:en"

        for url, lang in [(de_url, "de"), (en_url, "en")]:
            try:
                headers = {"User-Agent": USER_AGENT}
                response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
                response.raise_for_status()
                feed = feedparser.parse(response.content)

                for entry in feed.entries[:20]:  # Limit per feed
                    title = entry.get("title", "").strip()
                    if not title:
                        continue

                    source_name = "Google News"
                    if " - " in title:
                        parts = title.rsplit(" - ", 1)
                        title = parts[0].strip()
                        source_name = parts[1].strip()

                    published = None
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        try:
                            published = datetime(*entry.published_parsed[:6])
                        except (TypeError, ValueError):
                            published = datetime.now()
                    else:
                        published = datetime.now()

                    article = {
                        "article_hash": generate_news_id(title, source_name),
                        "title": title,
                        "summary": "",
                        "source": source_name,
                        "url": entry.get("link", ""),
                        "published": published,
                        "language": lang,
                        "category": "finance"
                    }
                    all_articles.append(article)

            except Exception as e:
                logger.warning("Failed to fetch news for keyword '%s': %s", keyword, str(e))

    # Deduplicate
    seen = set()
    unique_articles = []
    for article in all_articles:
        if article["article_hash"] not in seen:
            seen.add(article["article_hash"])
            unique_articles.append(article)

    logger.info("Found %d unique articles for %s", len(unique_articles), stock_key)

    # Enrich with sentiment and stock matching
    for article in unique_articles:
        enrich_article(article)
        # Ensure this stock is marked as affected
        affected = article.get("affected_stocks", "")
        if stock_key not in affected:
            if affected:
                article["affected_stocks"] = affected + "," + stock_key
            else:
                article["affected_stocks"] = stock_key

    # Store in database
    inserted = db.bulk_insert_articles(session, unique_articles)
    session.commit()

    logger.info("Stored %d new articles for %s", inserted, stock_key)
    return inserted
