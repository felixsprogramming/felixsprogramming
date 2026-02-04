"""
StockPulse Crawler - Sentiment Analysis
Keyword-based and pattern-based sentiment analysis for financial news.
Supports German and English headlines.
"""

import re
import logging

logger = logging.getLogger(__name__)

# --- Positive keywords (weighted) ---
POSITIVE_KEYWORDS = {
    # English
    "surge": 2.0, "soar": 2.0, "rally": 1.8, "boom": 1.8,
    "record high": 2.0, "all-time high": 2.0, "breakout": 1.5,
    "bullish": 1.5, "upgrade": 1.5, "outperform": 1.5,
    "beat expectations": 2.0, "beats estimates": 2.0,
    "profit": 1.2, "growth": 1.3, "gains": 1.2, "rise": 1.0,
    "rising": 1.0, "jumps": 1.5, "climbs": 1.2, "advances": 1.0,
    "recovery": 1.3, "rebound": 1.3, "strong": 1.0,
    "positive": 1.0, "optimism": 1.3, "confidence": 1.2,
    "expansion": 1.2, "innovation": 1.0, "breakthrough": 1.5,
    "dividend": 1.0, "buyback": 1.2, "acquisition": 1.0,
    "deal": 0.8, "partnership": 0.8, "launch": 0.8,
    "exceeds": 1.5, "record revenue": 2.0, "record profit": 2.0,
    # German
    "rekord": 2.0, "allzeithoch": 2.0, "kursrally": 1.8,
    "boom": 1.8, "aufschwung": 1.5, "erholung": 1.3,
    "wachstum": 1.3, "gewinn": 1.2, "anstieg": 1.2,
    "steigt": 1.0, "zulegen": 1.0, "klettern": 1.2,
    "bullish": 1.5, "positiv": 1.0, "optimismus": 1.3,
    "kaufempfehlung": 1.8, "outperform": 1.5,
    "uebertrifft erwartungen": 2.0, "rekordumsatz": 2.0,
    "rekordgewinn": 2.0, "dividende": 1.0,
    "expansion": 1.2, "innovation": 1.0, "durchbruch": 1.5,
    "partnerschaft": 0.8, "uebernahme": 1.0,
    "zinssenkung": 1.5, "konjunkturpaket": 1.3,
    "starke nachfrage": 1.5, "aufwaertstrend": 1.5
}

# --- Negative keywords (weighted) ---
NEGATIVE_KEYWORDS = {
    # English
    "crash": 2.5, "plunge": 2.0, "collapse": 2.5, "crisis": 2.0,
    "recession": 2.0, "bear market": 2.0, "sell-off": 1.8,
    "panic": 2.0, "fear": 1.5, "warning": 1.5,
    "downgrade": 1.5, "underperform": 1.5,
    "miss expectations": 2.0, "misses estimates": 2.0,
    "loss": 1.5, "losses": 1.5, "decline": 1.2, "drop": 1.2,
    "falls": 1.2, "falling": 1.2, "slump": 1.8, "tumble": 1.8,
    "sink": 1.5, "plummet": 2.0, "weak": 1.0,
    "negative": 1.0, "pessimism": 1.3, "uncertainty": 1.2,
    "inflation": 1.3, "rate hike": 1.5, "interest rate": 0.8,
    "layoffs": 1.5, "bankruptcy": 2.5, "default": 2.0,
    "sanctions": 1.5, "tariff": 1.3, "trade war": 1.8,
    "investigation": 1.2, "lawsuit": 1.2, "fraud": 2.0,
    "war": 2.0, "conflict": 1.5, "attack": 1.5,
    "correction": 1.3, "volatility": 1.0,
    # German
    "crash": 2.5, "einbruch": 2.0, "absturz": 2.0, "krise": 2.0,
    "rezession": 2.0, "baerenmarkt": 2.0, "ausverkauf": 1.8,
    "panik": 2.0, "angst": 1.5, "warnung": 1.5,
    "verlust": 1.5, "verluste": 1.5, "rueckgang": 1.2,
    "faellt": 1.2, "fallen": 1.2, "sinkt": 1.5,
    "einbrueche": 1.8, "schwach": 1.0, "negativ": 1.0,
    "unsicherheit": 1.2, "inflation": 1.3,
    "zinserhoehung": 1.5, "zinsanstieg": 1.3,
    "entlassungen": 1.5, "insolvenz": 2.5, "pleite": 2.5,
    "sanktionen": 1.5, "zoelle": 1.3, "handelskrieg": 1.8,
    "krieg": 2.0, "konflikt": 1.5, "angriff": 1.5,
    "korrektur": 1.3, "volatilitaet": 1.0,
    "gewinnwarnung": 2.0, "umsatzrueckgang": 1.8,
    "abwaertstrend": 1.5, "belastung": 1.0,
    "eskalation": 1.5, "spannungen": 1.2
}

# --- Amplifier words ---
AMPLIFIERS = {
    "very": 1.3, "extremely": 1.5, "massive": 1.5, "huge": 1.4,
    "significant": 1.3, "dramatic": 1.4, "sharp": 1.3,
    "stark": 1.3, "massiv": 1.5, "erheblich": 1.3,
    "dramatisch": 1.4, "deutlich": 1.3, "enorm": 1.4,
    "historisch": 1.5, "unprecedented": 1.5, "beispiellos": 1.5
}

# --- Negation words (flip sentiment) ---
NEGATION_WORDS = [
    "not", "no", "never", "neither", "nor", "barely",
    "nicht", "kein", "keine", "keinen", "niemals", "kaum"
]


def analyze_sentiment(title, summary=""):
    """
    Analyze the sentiment of a news article based on title and summary.

    Uses keyword matching with weights, amplifiers, and negation detection.

    Args:
        title: Article headline
        summary: Article summary/description (optional)

    Returns:
        dict with:
            - sentiment: 'positive', 'negative', or 'neutral'
            - score: float from -1.0 to +1.0
            - confidence: float from 0.0 to 1.0
            - keywords_found: list of matched keywords
    """
    # Combine title (higher weight) and summary
    title_lower = title.lower()
    summary_lower = summary.lower() if summary else ""

    positive_score = 0.0
    negative_score = 0.0
    keywords_found = []

    # Check for amplifiers in text
    text_full = title_lower + " " + summary_lower
    amplifier = 1.0
    for amp_word, amp_value in AMPLIFIERS.items():
        if amp_word in text_full:
            amplifier = max(amplifier, amp_value)

    # Check for negation near keywords
    has_negation_title = any(neg in title_lower.split() for neg in NEGATION_WORDS)

    # Score positive keywords
    for keyword, weight in POSITIVE_KEYWORDS.items():
        # Title match (2x weight)
        if keyword in title_lower:
            score = weight * 2.0 * amplifier
            if has_negation_title:
                negative_score += score * 0.8  # Negated positive -> negative
            else:
                positive_score += score
            keywords_found.append(("+" if not has_negation_title else "-", keyword))

        # Summary match (1x weight)
        elif keyword in summary_lower:
            positive_score += weight * amplifier
            keywords_found.append(("+", keyword))

    # Score negative keywords
    for keyword, weight in NEGATIVE_KEYWORDS.items():
        if keyword in title_lower:
            score = weight * 2.0 * amplifier
            if has_negation_title:
                positive_score += score * 0.5  # Negated negative -> slightly positive
            else:
                negative_score += score
            keywords_found.append(("-" if not has_negation_title else "+", keyword))

        elif keyword in summary_lower:
            negative_score += weight * amplifier
            keywords_found.append(("-", keyword))

    # Calculate final score
    total = positive_score + negative_score
    if total == 0:
        return {
            "sentiment": "neutral",
            "score": 0.0,
            "confidence": 0.2,
            "keywords_found": []
        }

    raw_score = (positive_score - negative_score) / total
    # Clamp to [-1, 1]
    score = max(-1.0, min(1.0, raw_score))

    # Determine sentiment label
    if score > 0.15:
        sentiment = "positive"
    elif score < -0.15:
        sentiment = "negative"
    else:
        sentiment = "neutral"

    # Confidence based on number and strength of signals
    signal_count = len(keywords_found)
    confidence = min(0.95, 0.3 + signal_count * 0.12 + abs(score) * 0.3)

    return {
        "sentiment": sentiment,
        "score": round(score, 3),
        "confidence": round(confidence, 3),
        "keywords_found": keywords_found
    }


def analyze_batch(articles):
    """
    Analyze sentiment for a list of articles.

    Args:
        articles: List of article dicts with 'title' and optional 'summary'

    Returns:
        List of articles enriched with sentiment data
    """
    for article in articles:
        result = analyze_sentiment(
            article.get("title", ""),
            article.get("summary", "")
        )
        article["sentiment"] = result["sentiment"]
        article["sentimentScore"] = result["score"]
        article["sentimentConfidence"] = result["confidence"]

    return articles
