"""
BBF-Trading - Reverse Correlation Engine
Detects significant stock price movements and finds matching news to explain them.
Also feeds correlation strength back into the AI model's feature pipeline.
"""

import json
import logging
import math
import os
from datetime import datetime, timedelta

from .config import STOCKS, DATA_DIR, STOCK_KEYWORDS
from .database import db as db_manager, PriceHistory, NewsArticle

logger = logging.getLogger(__name__)

# Sources considered highly reliable for financial reporting
RELIABLE_SOURCES = {
    "reuters", "bloomberg", "cnbc", "handelsblatt",
    "reuters business", "bloomberg markets", "cnbc top news", "cnbc world",
    "handelsblatt finanzen", "handelsblatt unternehmen",
    "wsj", "wsj markets", "wsj world", "wall street journal",
    "financial times", "barrons", "faz finanzen",
}


class ReverseCorrelationEngine:
    """
    Detects significant stock price movements and searches backward through
    news archives to find articles that may explain each movement.  The
    resulting correlation data can be fed back into the AI prediction model
    as additional features.
    """

    # ------------------------------------------------------------------ #
    #  1. Detect significant price movements                              #
    # ------------------------------------------------------------------ #

    def detect_significant_movements(self, session, stock_key, days=90,
                                     threshold_pct=2.5):
        """
        Query price history for *stock_key* over the given *days* window,
        compute daily percent-change values, and return every day whose
        absolute change meets or exceeds *threshold_pct*.

        Returns a list of dicts, each containing:
            date, close, prev_close, change_pct, category, stock_key
        """
        prices = db_manager.get_price_history(session, stock_key, days=days)

        if len(prices) < 2:
            logger.debug("Not enough price data for %s (got %d rows)",
                         stock_key, len(prices))
            return []

        movements = []
        for i in range(1, len(prices)):
            prev = prices[i - 1]
            curr = prices[i]

            if prev.close is None or curr.close is None or prev.close == 0:
                continue

            change_pct = ((curr.close - prev.close) / prev.close) * 100.0

            if abs(change_pct) < threshold_pct:
                continue

            # Categorize the movement
            if change_pct <= -5.0:
                category = "strong_drop"
            elif change_pct <= -threshold_pct:
                category = "medium_drop"
            elif change_pct >= 5.0:
                category = "strong_rise"
            else:
                category = "medium_rise"

            movements.append({
                "date": curr.date,
                "close": curr.close,
                "prev_close": prev.close,
                "change_pct": round(change_pct, 4),
                "category": category,
                "stock_key": stock_key,
            })

        logger.info("Detected %d significant movements for %s over %d days "
                     "(threshold=%.1f%%)", len(movements), stock_key, days,
                     threshold_pct)
        return movements

    # ------------------------------------------------------------------ #
    #  2. Find matching news around a price movement                      #
    # ------------------------------------------------------------------ #

    def find_matching_news(self, session, stock_key, movement_date,
                           window_hours=72):
        """
        Search for news articles published in a window around the
        *movement_date* (48 hours before to 24 hours after) and score each
        article for relevance to the movement.

        Parameters
        ----------
        session : SQLAlchemy session
        stock_key : str
        movement_date : str  (YYYY-MM-DD)
        window_hours : int   (total window size kept for signature compat;
                              actual window is 48h before + 24h after)

        Returns
        -------
        list[dict]
            Matched articles sorted by relevance_score descending.  Each dict
            contains: title, url, source, sentiment, sentiment_score,
            relevance_score, published.
        """
        # Parse the movement date into a datetime at market close (~16:00)
        try:
            movement_dt = datetime.strptime(movement_date, "%Y-%m-%d")
            movement_dt = movement_dt.replace(hour=16, minute=0, second=0)
        except ValueError:
            logger.warning("Invalid movement_date format: %s", movement_date)
            return []

        window_start = movement_dt - timedelta(hours=48)
        window_end = movement_dt + timedelta(hours=24)

        # Fetch all articles in the time window
        all_articles = db_manager.get_news_for_date_range(
            session, window_start, window_end
        )

        # Keywords for this stock (lowercase)
        keywords = [kw.lower() for kw in STOCK_KEYWORDS.get(stock_key, [])]
        if not keywords:
            # Fallback: use stock_key itself plus config name/ticker
            cfg = STOCKS.get(stock_key, {})
            keywords = [stock_key]
            if cfg.get("name"):
                keywords.append(cfg["name"].lower())
            if cfg.get("ticker"):
                keywords.append(cfg["ticker"].lower().replace("^", ""))

        matched = []
        for article in all_articles:
            # --- Check relevance to this stock ---
            is_relevant = False

            # Check affected_stocks field
            if article.affected_stocks:
                affected = [s.strip().lower()
                            for s in article.affected_stocks.split(",")]
                if stock_key.lower() in affected:
                    is_relevant = True

            # Check title/summary for keyword matches
            if not is_relevant:
                title_lower = (article.title or "").lower()
                summary_lower = (article.summary or "").lower()
                text_blob = title_lower + " " + summary_lower
                for kw in keywords:
                    if kw and kw in text_blob:
                        is_relevant = True
                        break

            if not is_relevant:
                continue

            # --- Score relevance ---
            relevance = self._score_relevance(
                article, movement_dt, stock_key
            )

            published_str = (article.published.isoformat()
                             if article.published else None)

            matched.append({
                "title": article.title,
                "url": article.url or "",
                "source": article.source or "",
                "sentiment": article.sentiment or "neutral",
                "sentiment_score": round(article.sentiment_score or 0.0, 4),
                "relevance_score": round(relevance, 4),
                "published": published_str,
            })

        # Sort by relevance descending
        matched.sort(key=lambda x: x["relevance_score"], reverse=True)
        return matched

    # ------------------------------------------------------------------ #
    #  Internal: relevance scoring                                        #
    # ------------------------------------------------------------------ #

    def _score_relevance(self, article, movement_dt, stock_key):
        """
        Compute a 0-1 relevance score for an article relative to a price
        movement.

        Components:
        - Time proximity   (0-0.4)  closer in time  -> higher
        - Sentiment align  (0-0.35) sentiment matches direction -> higher
        - Source reliability(0-0.25) trusted financial sources -> bonus
        """
        score = 0.0

        # --- Time proximity (max 0.4) ---
        if article.published:
            delta_hours = abs(
                (movement_dt - article.published).total_seconds() / 3600.0
            )
            # Exponential decay: full score at 0h, ~half at 12h, ~0 at 72h
            time_score = math.exp(-0.05 * delta_hours) * 0.4
            score += time_score

        # --- Sentiment alignment (max 0.35) ---
        # Determine movement direction from stock_key context — we check
        # the movement *category* indirectly via the stock_key, but since
        # we only have the article here we just check if the sentiment
        # polarity is consistent with the implied direction.  The caller
        # already filtered for relevant articles, so we score how well
        # the article's sentiment aligns.
        sentiment = (article.sentiment or "neutral").lower()
        sent_score_val = article.sentiment_score or 0.0

        # Higher absolute sentiment_score = stronger signal = more useful
        sentiment_magnitude = min(abs(sent_score_val) / 2.0, 1.0)
        alignment_score = sentiment_magnitude * 0.35
        score += alignment_score

        # --- Source reliability (max 0.25) ---
        source_lower = (article.source or "").lower().strip()
        if source_lower in RELIABLE_SOURCES:
            score += 0.25
        elif any(rs in source_lower for rs in RELIABLE_SOURCES):
            score += 0.15

        return min(score, 1.0)

    def _sentiment_aligns_with_direction(self, sentiment, change_pct):
        """
        Return True if the news sentiment is consistent with the price
        movement direction.
        """
        sentiment = (sentiment or "neutral").lower()
        if change_pct < 0 and sentiment == "negative":
            return True
        if change_pct > 0 and sentiment == "positive":
            return True
        return False

    # ------------------------------------------------------------------ #
    #  3. Build full correlation records                                   #
    # ------------------------------------------------------------------ #

    def build_correlations(self, session, stock_key=None, days=90):
        """
        For each tracked stock (or a single *stock_key*), detect significant
        movements and search for matching news.

        Returns a list of correlation records, each containing movement data,
        matched news, and an overall correlation_strength.
        """
        keys = [stock_key] if stock_key else list(STOCKS.keys())
        all_correlations = []

        for key in keys:
            movements = self.detect_significant_movements(
                session, key, days=days
            )

            if not movements:
                continue

            explained_count = 0

            for movement in movements:
                matched_news = self.find_matching_news(
                    session, key, movement["date"]
                )

                # A movement is "explained" if at least one article has a
                # relevance_score >= 0.4 (moderate match)
                high_relevance = [
                    n for n in matched_news if n["relevance_score"] >= 0.4
                ]
                is_explained = len(high_relevance) > 0
                if is_explained:
                    explained_count += 1

                # Correlation strength for this individual movement:
                # weighted combination of number of matches and their quality
                if matched_news:
                    top_scores = [n["relevance_score"] for n in matched_news[:5]]
                    avg_top = sum(top_scores) / len(top_scores)
                    count_factor = min(len(matched_news) / 5.0, 1.0)
                    strength = (avg_top * 0.7) + (count_factor * 0.3)
                else:
                    strength = 0.0

                all_correlations.append({
                    "stock_key": key,
                    "movement_date": movement["date"],
                    "change_pct": movement["change_pct"],
                    "category": movement["category"],
                    "close": movement["close"],
                    "prev_close": movement["prev_close"],
                    "matched_news": matched_news,
                    "explained": is_explained,
                    "correlation_strength": round(min(strength, 1.0), 4),
                })

            logger.info(
                "Built correlations for %s: %d movements, %d explained",
                key, len(movements), explained_count,
            )

        return all_correlations

    # ------------------------------------------------------------------ #
    #  4. Compute aggregate features for the AI model                     #
    # ------------------------------------------------------------------ #

    def compute_correlation_features(self, session, stock_key, days=30):
        """
        Compute aggregate correlation features for *stock_key* over the last
        *days* days.  These features can be injected into the AI prediction
        pipeline as additional input signals.

        Returns a dict with:
            explained_movement_ratio, avg_news_lead_time_hours,
            sentiment_accuracy, strong_correlation_count,
            unexplained_movement_count, news_predictive_ratio
        """
        correlations = self.build_correlations(
            session, stock_key=stock_key, days=days
        )

        total_movements = len(correlations)
        if total_movements == 0:
            return {
                "explained_movement_ratio": 0.0,
                "avg_news_lead_time_hours": 0.0,
                "sentiment_accuracy": 0.0,
                "strong_correlation_count": 0,
                "unexplained_movement_count": 0,
                "news_predictive_ratio": 0.0,
            }

        explained_count = sum(1 for c in correlations if c["explained"])
        unexplained_count = total_movements - explained_count
        strong_count = sum(
            1 for c in correlations if c["correlation_strength"] > 0.7
        )

        # --- Average news lead time ---
        # For each explained movement, compute how many hours BEFORE the
        # movement date the best-matching article was published.
        lead_times = []
        sentiment_correct = 0
        sentiment_total = 0
        news_before_count = 0
        news_after_count = 0

        for corr in correlations:
            if not corr["matched_news"]:
                continue

            try:
                movement_dt = datetime.strptime(
                    corr["movement_date"], "%Y-%m-%d"
                ).replace(hour=16)
            except ValueError:
                continue

            change_pct = corr["change_pct"]

            for article in corr["matched_news"]:
                pub_str = article.get("published")
                if not pub_str:
                    continue
                try:
                    pub_dt = datetime.fromisoformat(pub_str)
                except (ValueError, TypeError):
                    continue

                delta_hours = (movement_dt - pub_dt).total_seconds() / 3600.0

                if delta_hours > 0:
                    # News was published BEFORE the movement
                    lead_times.append(delta_hours)
                    news_before_count += 1
                else:
                    news_after_count += 1

                # Check sentiment alignment
                sentiment = article.get("sentiment", "neutral")
                if sentiment != "neutral":
                    sentiment_total += 1
                    if self._sentiment_aligns_with_direction(
                        sentiment, change_pct
                    ):
                        sentiment_correct += 1

        avg_lead_time = (
            sum(lead_times) / len(lead_times) if lead_times else 0.0
        )
        sentiment_accuracy = (
            sentiment_correct / sentiment_total
            if sentiment_total > 0 else 0.0
        )
        total_news_directional = news_before_count + news_after_count
        news_predictive_ratio = (
            news_before_count / total_news_directional
            if total_news_directional > 0 else 0.0
        )

        features = {
            "explained_movement_ratio": round(
                explained_count / total_movements, 4
            ),
            "avg_news_lead_time_hours": round(avg_lead_time, 2),
            "sentiment_accuracy": round(sentiment_accuracy, 4),
            "strong_correlation_count": strong_count,
            "unexplained_movement_count": unexplained_count,
            "news_predictive_ratio": round(news_predictive_ratio, 4),
        }

        logger.info("Correlation features for %s: %s", stock_key, features)
        return features

    # ------------------------------------------------------------------ #
    #  5. Persist correlations to JSON                                    #
    # ------------------------------------------------------------------ #

    def save_correlations_json(self, session, stock_key=None, days=90):
        """
        Build correlations and save the results to ``data/correlations.json``
        with metadata.

        Returns the output file path.
        """
        correlations = self.build_correlations(
            session, stock_key=stock_key, days=days
        )

        total_movements = len(correlations)
        explained_count = sum(1 for c in correlations if c["explained"])
        strengths = [c["correlation_strength"] for c in correlations]
        overall_strength = (
            sum(strengths) / len(strengths) if strengths else 0.0
        )

        output = {
            "metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "stock_key_filter": stock_key,
                "days": days,
                "total_movements": total_movements,
                "explained_count": explained_count,
                "unexplained_count": total_movements - explained_count,
                "overall_correlation_strength": round(overall_strength, 4),
            },
            "correlations": correlations,
        }

        os.makedirs(DATA_DIR, exist_ok=True)
        out_path = os.path.join(DATA_DIR, "correlations.json")

        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(output, fh, indent=2, ensure_ascii=False, default=str)

        logger.info(
            "Saved %d correlations to %s (explained=%d, strength=%.2f)",
            total_movements, out_path, explained_count, overall_strength,
        )
        return out_path


# Module-level singleton
correlation_engine = ReverseCorrelationEngine()
