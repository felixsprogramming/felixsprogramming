"""
BBF-Trading - AI Prediction Model
Machine learning model that predicts stock movements based on news sentiment
and technical indicators. Trains on historical correlations, predicts on current news.

Models:
  1. Gradient Boosting Classifier (direction: up/down/sideways)
  2. Gradient Boosting Regressor (predicted % change)
  3. Optional: HuggingFace transformer for advanced sentiment

Features used:
  - News sentiment aggregates (avg, min, max, count, weighted)
  - Technical indicators (SMA, RSI, volatility, momentum)
  - Market context (VIX level, sector sentiment, market trend)
"""

import os
import json
import pickle
import logging
import math
from datetime import datetime, timedelta
from collections import defaultdict

import numpy as np

from .config import (
    AI_MODEL_DIR, DATA_DIR, MIN_TRAINING_SAMPLES, PREDICTION_TIMEFRAME_DAYS,
    USE_TRANSFORMER_SENTIMENT, STOCKS
)

try:
    from .correlation import correlation_engine
except ImportError:
    correlation_engine = None

logger = logging.getLogger(__name__)

# Optional transformer import
_transformer_pipeline = None
if USE_TRANSFORMER_SENTIMENT:
    try:
        from transformers import pipeline
        _transformer_pipeline = pipeline(
            "sentiment-analysis",
            model="ProsusAI/finbert",
            tokenizer="ProsusAI/finbert"
        )
        logger.info("FinBERT transformer model loaded for sentiment analysis")
    except ImportError:
        logger.warning("transformers not installed, using keyword sentiment only")
    except Exception as e:
        logger.warning("Could not load transformer model: %s", e)


def transformer_sentiment(text):
    """
    Analyze sentiment using FinBERT transformer model.
    Returns score between -1.0 and +1.0
    """
    if _transformer_pipeline is None:
        return None

    try:
        result = _transformer_pipeline(text[:512])[0]
        label = result["label"].lower()
        score = result["score"]
        if label == "positive":
            return score
        elif label == "negative":
            return -score
        else:
            return 0.0
    except Exception:
        return None


class FeatureExtractor:
    """Extracts ML features from price history and news data."""

    @staticmethod
    def compute_technical_features(prices):
        """
        Compute technical indicators from price data.

        Args:
            prices: List of dicts with 'close', 'high', 'low', 'volume', 'date'
                    ordered by date ascending

        Returns:
            Dict of technical features
        """
        if len(prices) < 20:
            return None

        closes = np.array([p["close"] for p in prices], dtype=float)
        highs = np.array([p.get("high", p["close"]) for p in prices], dtype=float)
        lows = np.array([p.get("low", p["close"]) for p in prices], dtype=float)
        volumes = np.array([p.get("volume", 0) for p in prices], dtype=float)

        current = closes[-1]

        # Simple Moving Averages
        sma5 = np.mean(closes[-5:])
        sma10 = np.mean(closes[-10:])
        sma20 = np.mean(closes[-20:])
        sma50 = np.mean(closes[-50:]) if len(closes) >= 50 else sma20

        # Exponential Moving Average (20-day)
        ema20 = closes[-1]
        alpha = 2 / (20 + 1)
        for c in closes[-20:]:
            ema20 = alpha * c + (1 - alpha) * ema20

        # RSI (14-day)
        rsi = FeatureExtractor._compute_rsi(closes, 14)

        # Volatility (20-day standard deviation of returns)
        returns = np.diff(closes[-21:]) / closes[-21:-1]
        volatility_20d = np.std(returns) * math.sqrt(252) if len(returns) > 1 else 0

        # Momentum (rate of change)
        momentum_5d = (closes[-1] / closes[-6] - 1) * 100 if len(closes) >= 6 else 0
        momentum_10d = (closes[-1] / closes[-11] - 1) * 100 if len(closes) >= 11 else 0
        momentum_20d = (closes[-1] / closes[-21] - 1) * 100 if len(closes) >= 21 else 0

        # Bollinger Band position
        bb_mid = sma20
        bb_std = np.std(closes[-20:])
        bb_upper = bb_mid + 2 * bb_std
        bb_lower = bb_mid - 2 * bb_std
        bb_position = (current - bb_lower) / (bb_upper - bb_lower) if bb_upper != bb_lower else 0.5

        # Average True Range (14-day)
        atr = FeatureExtractor._compute_atr(highs, lows, closes, 14)

        # Volume trend
        avg_vol_10 = np.mean(volumes[-10:]) if np.any(volumes[-10:] > 0) else 1
        avg_vol_20 = np.mean(volumes[-20:]) if np.any(volumes[-20:] > 0) else 1
        volume_ratio = avg_vol_10 / avg_vol_20 if avg_vol_20 > 0 else 1

        # Price relative to moving averages
        price_vs_sma20 = (current / sma20 - 1) * 100
        price_vs_sma50 = (current / sma50 - 1) * 100

        # Trend strength: SMA alignment
        trend_alignment = 0
        if sma5 > sma10 > sma20:
            trend_alignment = 1  # Strong uptrend
        elif sma5 < sma10 < sma20:
            trend_alignment = -1  # Strong downtrend

        return {
            "price_current": current,
            "sma5": sma5,
            "sma10": sma10,
            "sma20": sma20,
            "sma50": sma50,
            "ema20": ema20,
            "rsi_14": rsi,
            "volatility_20d": volatility_20d,
            "momentum_5d": momentum_5d,
            "momentum_10d": momentum_10d,
            "momentum_20d": momentum_20d,
            "bb_position": bb_position,
            "atr_14": atr,
            "volume_ratio": volume_ratio,
            "price_vs_sma20": price_vs_sma20,
            "price_vs_sma50": price_vs_sma50,
            "trend_alignment": trend_alignment
        }

    @staticmethod
    def compute_news_features(news_articles):
        """
        Compute aggregated news sentiment features.

        Args:
            news_articles: List of articles with 'sentiment_score', 'sentiment', 'category'

        Returns:
            Dict of news features
        """
        if not news_articles:
            return {
                "news_count": 0,
                "sentiment_avg": 0, "sentiment_max": 0, "sentiment_min": 0,
                "sentiment_std": 0, "positive_ratio": 0, "negative_ratio": 0,
                "sentiment_momentum": 0, "news_volume_signal": 0
            }

        scores = [a.get("sentiment_score", 0) for a in news_articles]
        sentiments = [a.get("sentiment", "neutral") for a in news_articles]

        n = len(scores)
        positive_count = sentiments.count("positive")
        negative_count = sentiments.count("negative")

        # Time-weighted sentiment (newer articles get more weight)
        weighted_sum = 0
        weight_total = 0
        for i, score in enumerate(scores):
            weight = 1.0 + (i / n) * 0.5  # Newer articles = higher index = more weight
            weighted_sum += score * weight
            weight_total += weight

        sentiment_weighted = weighted_sum / weight_total if weight_total > 0 else 0

        # Sentiment momentum (first half vs second half)
        mid = n // 2
        if mid > 0:
            early_avg = np.mean(scores[:mid])
            late_avg = np.mean(scores[mid:])
            sentiment_momentum = late_avg - early_avg
        else:
            sentiment_momentum = 0

        return {
            "news_count": n,
            "sentiment_avg": np.mean(scores),
            "sentiment_weighted": sentiment_weighted,
            "sentiment_max": max(scores),
            "sentiment_min": min(scores),
            "sentiment_std": np.std(scores) if n > 1 else 0,
            "positive_ratio": positive_count / n,
            "negative_ratio": negative_count / n,
            "sentiment_momentum": sentiment_momentum,
            "news_volume_signal": min(n / 10.0, 3.0)  # Normalized news volume
        }

    @staticmethod
    def compute_correlation_features(session, stock_key, days=30):
        """Compute features from reverse correlation analysis."""
        defaults = {
            "explained_ratio": 0.5,
            "sentiment_accuracy": 0.5,
            "news_lead_time": 24.0,
            "strong_correlations": 0,
            "unexplained_movements": 0,
            "news_predictive_ratio": 0.5,
        }
        if correlation_engine is None:
            return defaults
        try:
            features = correlation_engine.compute_correlation_features(session, stock_key, days)
            return {
                "explained_ratio": features.get("explained_movement_ratio", 0.5),
                "sentiment_accuracy": features.get("sentiment_accuracy", 0.5),
                "news_lead_time": features.get("avg_news_lead_time_hours", 24.0),
                "strong_correlations": features.get("strong_correlation_count", 0),
                "unexplained_movements": features.get("unexplained_movement_count", 0),
                "news_predictive_ratio": features.get("news_predictive_ratio", 0.5),
            }
        except Exception:
            return defaults

    @staticmethod
    def build_feature_vector(technical, news, session=None, stock_key=None):
        """Combine technical and news features into a single feature vector."""
        if technical is None:
            return None

        # Feature order must be consistent for training and prediction
        features = [
            # Technical (17 features)
            technical.get("rsi_14", 50),
            technical.get("volatility_20d", 0),
            technical.get("momentum_5d", 0),
            technical.get("momentum_10d", 0),
            technical.get("momentum_20d", 0),
            technical.get("bb_position", 0.5),
            technical.get("atr_14", 0),
            technical.get("volume_ratio", 1),
            technical.get("price_vs_sma20", 0),
            technical.get("price_vs_sma50", 0),
            technical.get("trend_alignment", 0),
            # News (10 features)
            news.get("news_count", 0),
            news.get("sentiment_avg", 0),
            news.get("sentiment_weighted", 0),
            news.get("sentiment_max", 0),
            news.get("sentiment_min", 0),
            news.get("sentiment_std", 0),
            news.get("positive_ratio", 0),
            news.get("negative_ratio", 0),
            news.get("sentiment_momentum", 0),
            news.get("news_volume_signal", 0),
        ]

        # Correlation features (reverse search)
        corr = FeatureExtractor.compute_correlation_features(session, stock_key) if session else {
            "explained_ratio": 0.5, "sentiment_accuracy": 0.5, "news_lead_time": 24.0,
            "strong_correlations": 0, "unexplained_movements": 0, "news_predictive_ratio": 0.5,
        }
        features.extend([
            corr["explained_ratio"],
            corr["sentiment_accuracy"],
            min(corr["news_lead_time"] / 72.0, 1.0),  # normalize to 0-1
            min(corr["strong_correlations"] / 10.0, 1.0),  # normalize
            min(corr["unexplained_movements"] / 10.0, 1.0),  # normalize
            corr["news_predictive_ratio"],
        ])

        return np.array(features, dtype=float)

    @staticmethod
    def _compute_rsi(closes, period=14):
        if len(closes) < period + 1:
            return 50.0
        deltas = np.diff(closes[-(period + 1):])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains) if len(gains) > 0 else 0
        avg_loss = np.mean(losses) if len(losses) > 0 else 0
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    @staticmethod
    def _compute_atr(highs, lows, closes, period=14):
        if len(closes) < period + 1:
            return 0.0
        trs = []
        for i in range(-period, 0):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1])
            )
            trs.append(tr)
        return np.mean(trs)


FEATURE_NAMES = [
    "rsi_14", "volatility_20d", "momentum_5d", "momentum_10d", "momentum_20d",
    "bb_position", "atr_14", "volume_ratio", "price_vs_sma20", "price_vs_sma50",
    "trend_alignment",
    "news_count", "sentiment_avg", "sentiment_weighted", "sentiment_max",
    "sentiment_min", "sentiment_std", "positive_ratio", "negative_ratio",
    "sentiment_momentum", "news_volume_signal"
]


class StockPredictor:
    """
    ML-based stock prediction model.
    Uses Gradient Boosting for direction classification and change regression.
    """

    def __init__(self):
        self.direction_model = None  # Classifier: up/down/sideways
        self.change_model = None     # Regressor: predicted % change
        self.is_trained = False
        self.training_stats = {}
        self.model_path = AI_MODEL_DIR

    def train(self, db_manager, session):
        """
        Train the model on historical data from the database.
        Builds training samples from aligned price+news data.
        """
        from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import accuracy_score, mean_absolute_error

        logger.info("=== Training AI Model ===")

        X_samples = []
        y_direction = []  # 0=down, 1=sideways, 2=up
        y_change = []     # actual % change

        # Build training data from each stock's history
        for stock_key in STOCKS.keys():
            prices = db_manager.get_price_history(session, stock_key, days=365 * 5)
            if len(prices) < 60:
                continue

            price_dicts = [{"date": p.date, "close": p.close, "high": p.high or p.close,
                           "low": p.low or p.close, "volume": p.volume or 0}
                          for p in prices]

            # For each day, compute features from prior data and label from future data
            for i in range(50, len(price_dicts) - PREDICTION_TIMEFRAME_DAYS):
                window = price_dicts[:i + 1]
                technical = FeatureExtractor.compute_technical_features(window)
                if technical is None:
                    continue

                # Get news for this window (last 7 days before prediction point)
                pred_date = price_dicts[i]["date"]
                week_before = (datetime.strptime(pred_date, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")

                news_in_window = db_manager.get_news_for_date_range(
                    session,
                    datetime.strptime(week_before, "%Y-%m-%d"),
                    datetime.strptime(pred_date, "%Y-%m-%d"),
                    stock_key=stock_key
                )

                news_dicts = [{"sentiment_score": n.sentiment_score, "sentiment": n.sentiment,
                              "category": n.category} for n in news_in_window]
                news_features = FeatureExtractor.compute_news_features(news_dicts)

                feature_vec = FeatureExtractor.build_feature_vector(technical, news_features)
                if feature_vec is None:
                    continue

                # Label: what happened in the next N days
                future_price = price_dicts[i + PREDICTION_TIMEFRAME_DAYS]["close"]
                current_price = price_dicts[i]["close"]
                actual_change = (future_price / current_price - 1) * 100

                if actual_change > 1.5:
                    direction = 2  # up
                elif actual_change < -1.5:
                    direction = 0  # down
                else:
                    direction = 1  # sideways

                X_samples.append(feature_vec)
                y_direction.append(direction)
                y_change.append(actual_change)

        if len(X_samples) < MIN_TRAINING_SAMPLES:
            logger.warning("Not enough training samples (%d < %d). Skipping training.",
                         len(X_samples), MIN_TRAINING_SAMPLES)
            return False

        X = np.array(X_samples)
        y_dir = np.array(y_direction)
        y_chg = np.array(y_change)

        logger.info("Training samples: %d", len(X))
        logger.info("Class distribution: down=%d, sideways=%d, up=%d",
                    np.sum(y_dir == 0), np.sum(y_dir == 1), np.sum(y_dir == 2))

        # Split data
        X_train, X_test, y_dir_train, y_dir_test, y_chg_train, y_chg_test = \
            train_test_split(X, y_dir, y_chg, test_size=0.2, random_state=42)

        # Train direction classifier
        self.direction_model = GradientBoostingClassifier(
            n_estimators=200,
            max_depth=5,
            learning_rate=0.1,
            min_samples_split=10,
            subsample=0.8,
            random_state=42
        )
        self.direction_model.fit(X_train, y_dir_train)

        # Train change regressor
        self.change_model = GradientBoostingRegressor(
            n_estimators=200,
            max_depth=5,
            learning_rate=0.1,
            min_samples_split=10,
            subsample=0.8,
            random_state=42
        )
        self.change_model.fit(X_train, y_chg_train)

        # Evaluate
        dir_pred = self.direction_model.predict(X_test)
        chg_pred = self.change_model.predict(X_test)

        accuracy = accuracy_score(y_dir_test, dir_pred)
        mae = mean_absolute_error(y_chg_test, chg_pred)

        # Feature importance
        importances = self.direction_model.feature_importances_
        top_features = sorted(zip(FEATURE_NAMES, importances),
                            key=lambda x: x[1], reverse=True)[:10]

        self.training_stats = {
            "samples": len(X),
            "accuracy": round(accuracy * 100, 1),
            "mae": round(mae, 2),
            "trained_at": datetime.now().isoformat(),
            "top_features": [(name, round(imp, 4)) for name, imp in top_features]
        }

        self.is_trained = True
        self.save_model()

        logger.info("Model trained: accuracy=%.1f%%, MAE=%.2f%%", accuracy * 100, mae)
        logger.info("Top features: %s", top_features[:5])

        return True

    def predict(self, db_manager, session, stock_key):
        """
        Generate prediction for a stock based on current news and technical state.

        Returns:
            Dict with prediction details or None
        """
        if not self.is_trained:
            self.load_model()
        if not self.is_trained:
            return self._fallback_predict(db_manager, session, stock_key)

        # Get recent prices
        prices = db_manager.get_price_history(session, stock_key, days=60)
        if len(prices) < 20:
            return None

        price_dicts = [{"date": p.date, "close": p.close, "high": p.high or p.close,
                       "low": p.low or p.close, "volume": p.volume or 0}
                      for p in prices]

        technical = FeatureExtractor.compute_technical_features(price_dicts)
        if technical is None:
            return None

        # Get recent news
        recent_news = db_manager.get_recent_news(session, hours=72, stock_key=stock_key)
        news_dicts = [{"sentiment_score": n.sentiment_score, "sentiment": n.sentiment,
                      "category": n.category} for n in recent_news]
        news_features = FeatureExtractor.compute_news_features(news_dicts)

        feature_vec = FeatureExtractor.build_feature_vector(technical, news_features)
        if feature_vec is None:
            return None

        X = feature_vec.reshape(1, -1)

        # Predict direction and change
        direction_proba = self.direction_model.predict_proba(X)[0]
        predicted_change = self.change_model.predict(X)[0]
        direction_idx = self.direction_model.predict(X)[0]

        direction_map = {0: "down", 1: "sideways", 2: "up"}
        direction = direction_map[direction_idx]
        confidence = float(direction_proba[direction_idx])

        # Build reasoning from top contributing news
        top_news = sorted(recent_news, key=lambda n: abs(n.sentiment_score), reverse=True)[:3]
        top_titles = [n.title for n in top_news]
        # Include both title and URL for clickable links in frontend
        top_news_with_urls = [
            {"title": n.title, "url": n.url or "", "sentiment": n.sentiment}
            for n in top_news
        ]

        reason = self._generate_reason(
            direction, predicted_change, news_features, technical, top_titles
        )

        stock_cfg = STOCKS.get(stock_key, {})
        return {
            "stock_key": stock_key,
            "stock_name": stock_cfg.get("name", stock_key),
            "direction": direction,
            "predicted_change_pct": round(predicted_change, 2),
            "confidence": round(confidence * 100, 1),
            "model_name": "gradient_boosting_ensemble",
            "news_sentiment_avg": round(news_features["sentiment_avg"], 3),
            "news_count": news_features["news_count"],
            "technical_signal": round(technical.get("momentum_5d", 0), 2),
            "volatility_30d": round(technical.get("volatility_20d", 0), 3),
            "reason": reason,
            "top_news_titles": top_titles,
            "top_news": top_news_with_urls,
            "timeframe_days": PREDICTION_TIMEFRAME_DAYS,
            "direction_probabilities": {
                "down": round(float(direction_proba[0]) * 100, 1),
                "sideways": round(float(direction_proba[1]) * 100, 1),
                "up": round(float(direction_proba[2]) * 100, 1)
            }
        }

    def _fallback_predict(self, db_manager, session, stock_key):
        """
        Simple rule-based prediction when ML model is not yet trained.
        Uses news sentiment as primary signal.
        """
        recent_news = db_manager.get_recent_news(session, hours=72, stock_key=stock_key)
        if not recent_news:
            return None

        news_dicts = [{"sentiment_score": n.sentiment_score, "sentiment": n.sentiment,
                      "category": n.category} for n in recent_news]
        news_features = FeatureExtractor.compute_news_features(news_dicts)

        avg = news_features["sentiment_avg"]

        if avg > 0.2:
            direction = "up"
            change = avg * 3.0
            confidence = min(75, 40 + news_features["news_count"] * 3)
        elif avg < -0.2:
            direction = "down"
            change = avg * 3.0
            confidence = min(75, 40 + news_features["news_count"] * 3)
        else:
            direction = "sideways"
            change = avg * 1.5
            confidence = 35

        top_news = sorted(recent_news, key=lambda n: abs(n.sentiment_score), reverse=True)[:3]
        top_titles = [n.title for n in top_news]
        # Include both title and URL for clickable links in frontend
        top_news_with_urls = [
            {"title": n.title, "url": n.url or "", "sentiment": n.sentiment}
            for n in top_news
        ]

        stock_cfg = STOCKS.get(stock_key, {})
        return {
            "stock_key": stock_key,
            "stock_name": stock_cfg.get("name", stock_key),
            "direction": direction,
            "predicted_change_pct": round(change, 2),
            "confidence": round(confidence, 1),
            "model_name": "news_sentiment_baseline",
            "news_sentiment_avg": round(avg, 3),
            "news_count": news_features["news_count"],
            "technical_signal": 0,
            "volatility_30d": 0,
            "reason": self._generate_reason(direction, change, news_features, {}, top_titles),
            "top_news_titles": top_titles,
            "top_news": top_news_with_urls,
            "timeframe_days": PREDICTION_TIMEFRAME_DAYS,
            "direction_probabilities": {}
        }

    def predict_all(self, db_manager, session):
        """Generate predictions for all active stocks."""
        predictions = []
        for stock_key in STOCKS.keys():
            pred = self.predict(db_manager, session, stock_key)
            if pred:
                predictions.append(pred)
        return predictions

    def _generate_reason(self, direction, change, news_features, technical, top_titles):
        """Generate human-readable prediction reasoning."""
        parts = []

        n_count = news_features.get("news_count", 0)
        pos_ratio = news_features.get("positive_ratio", 0)
        neg_ratio = news_features.get("negative_ratio", 0)
        avg_sent = news_features.get("sentiment_avg", 0)

        # News-based reasoning
        if n_count > 0:
            if avg_sent > 0.3:
                parts.append(f"Stark positive Nachrichtenlage ({n_count} Artikel, "
                           f"{int(pos_ratio * 100)}% positiv).")
            elif avg_sent > 0.1:
                parts.append(f"Leicht positive Nachrichtenlage ({n_count} Artikel).")
            elif avg_sent < -0.3:
                parts.append(f"Deutlich negative Nachrichtenlage ({n_count} Artikel, "
                           f"{int(neg_ratio * 100)}% negativ).")
            elif avg_sent < -0.1:
                parts.append(f"Leicht negative Nachrichtenlage ({n_count} Artikel).")
            else:
                parts.append(f"Gemischte Nachrichtenlage ({n_count} Artikel).")

        # Technical reasoning
        if technical:
            rsi = technical.get("rsi_14", 50)
            mom = technical.get("momentum_5d", 0)
            if rsi > 70:
                parts.append("RSI deutet auf ueberkauftes Niveau hin.")
            elif rsi < 30:
                parts.append("RSI signalisiert ueberverkaufte Bedingungen.")

            if mom > 3:
                parts.append("Starkes kurzfristiges Aufwaertsmomentum.")
            elif mom < -3:
                parts.append("Deutliches Abwaertsmomentum in den letzten Tagen.")

        # Top news reference
        if top_titles:
            parts.append(f'Wichtigste Meldung: "{top_titles[0]}".')

        if not parts:
            parts.append("Vorhersage basiert auf historischen Mustern und aktueller Datenlage.")

        return " ".join(parts)

    def save_model(self):
        """Save trained model to disk."""
        os.makedirs(self.model_path, exist_ok=True)

        if self.direction_model:
            with open(os.path.join(self.model_path, "direction_model.pkl"), "wb") as f:
                pickle.dump(self.direction_model, f)
        if self.change_model:
            with open(os.path.join(self.model_path, "change_model.pkl"), "wb") as f:
                pickle.dump(self.change_model, f)

        with open(os.path.join(self.model_path, "training_stats.json"), "w") as f:
            json.dump(self.training_stats, f, indent=2)

        logger.info("Model saved to %s", self.model_path)

    def load_model(self):
        """Load previously trained model from disk."""
        dir_path = os.path.join(self.model_path, "direction_model.pkl")
        chg_path = os.path.join(self.model_path, "change_model.pkl")
        stats_path = os.path.join(self.model_path, "training_stats.json")

        if os.path.exists(dir_path) and os.path.exists(chg_path):
            try:
                with open(dir_path, "rb") as f:
                    self.direction_model = pickle.load(f)
                with open(chg_path, "rb") as f:
                    self.change_model = pickle.load(f)
                if os.path.exists(stats_path):
                    with open(stats_path, "r") as f:
                        self.training_stats = json.load(f)
                self.is_trained = True
                logger.info("Model loaded from %s", self.model_path)
                return True
            except Exception as e:
                logger.error("Failed to load model: %s", e)

        return False

    def evaluate_past_predictions(self, db_manager, session):
        """
        Check past predictions against actual outcomes.
        Updates prediction records with actual results.
        """
        uneval = db_manager.get_unevaluated_predictions(session)
        evaluated = 0

        for pred in uneval:
            # Get actual price on prediction target date
            prices = db_manager.get_price_history(
                session, pred.stock_key,
                start_date=pred.prediction_date
            )
            if not prices:
                continue

            # Get price on the day before prediction was made
            created_date = pred.created_at.strftime("%Y-%m-%d")
            base_prices = db_manager.get_price_history(
                session, pred.stock_key,
                start_date=created_date
            )
            if not base_prices:
                continue

            base_price = base_prices[0].close
            actual_price = prices[0].close
            actual_change = (actual_price / base_price - 1) * 100

            db_manager.evaluate_prediction(session, pred.id, actual_change)
            evaluated += 1

        if evaluated > 0:
            session.commit()
            logger.info("Evaluated %d past predictions", evaluated)

        return evaluated

    def evaluate_and_adjust(self, db_manager, session):
        """
        Self-evaluation of past predictions: queries the database for past
        predictions where we now have actual price data, compares predicted
        direction and predicted change % against actual outcomes, calculates
        accuracy metrics, and stores evaluation results back in the Prediction
        table (was_correct, actual_change_pct).

        Returns:
            Dict with accuracy metrics including overall_accuracy,
            direction_accuracy per class, and MAE of % predictions.
        """
        from .database import Prediction

        # Step 1: Evaluate all unevaluated predictions that have matured
        unevaluated = db_manager.get_unevaluated_predictions(session)
        if not unevaluated:
            logger.info("No unevaluated predictions found for self-evaluation.")
            return {"evaluated": 0, "overall_accuracy": 0.0,
                    "direction_accuracy": {}, "mae_pct": 0.0}

        evaluated_count = 0
        correct_direction_count = 0
        absolute_errors = []
        direction_results = {
            "up": {"correct": 0, "total": 0},
            "down": {"correct": 0, "total": 0},
            "sideways": {"correct": 0, "total": 0},
        }

        for pred in unevaluated:
            # Get actual price at/after the prediction target date
            target_prices = db_manager.get_price_history(
                session, pred.stock_key, start_date=pred.prediction_date
            )
            if not target_prices:
                continue

            # Get base price (price when prediction was made)
            created_date = pred.created_at.strftime("%Y-%m-%d")
            base_prices = db_manager.get_price_history(
                session, pred.stock_key, start_date=created_date
            )
            if not base_prices:
                continue

            base_price = base_prices[0].close
            actual_price = target_prices[0].close
            actual_change_pct = (actual_price / base_price - 1) * 100

            # Determine actual direction using same thresholds as training
            if actual_change_pct > 1.5:
                actual_direction = "up"
            elif actual_change_pct < -1.5:
                actual_direction = "down"
            else:
                actual_direction = "sideways"

            # Store evaluation in DB via existing helper
            db_manager.evaluate_prediction(session, pred.id, actual_change_pct)

            # Track aggregated metrics
            evaluated_count += 1
            was_direction_correct = (pred.direction == actual_direction)
            if was_direction_correct:
                correct_direction_count += 1

            if pred.predicted_change_pct is not None:
                absolute_errors.append(
                    abs(pred.predicted_change_pct - actual_change_pct)
                )

            if pred.direction in direction_results:
                direction_results[pred.direction]["total"] += 1
                if was_direction_correct:
                    direction_results[pred.direction]["correct"] += 1

        if evaluated_count > 0:
            session.commit()

        # Step 2: Calculate accuracy metrics
        overall_accuracy = (
            (correct_direction_count / evaluated_count * 100)
            if evaluated_count > 0 else 0.0
        )

        direction_accuracy = {}
        for d, stats in direction_results.items():
            if stats["total"] > 0:
                direction_accuracy[d] = round(
                    stats["correct"] / stats["total"] * 100, 1
                )
            else:
                direction_accuracy[d] = 0.0

        mae = float(np.mean(absolute_errors)) if absolute_errors else 0.0

        metrics = {
            "evaluated": evaluated_count,
            "correct": correct_direction_count,
            "overall_accuracy": round(overall_accuracy, 1),
            "direction_accuracy": direction_accuracy,
            "mae_pct": round(mae, 2),
            "evaluated_at": datetime.now().isoformat(),
        }

        logger.info(
            "Self-evaluation complete: %d predictions evaluated, "
            "%.1f%% direction accuracy, MAE=%.2f%%",
            evaluated_count, overall_accuracy, mae,
        )

        return metrics

    def adjust_model_weights(self, db_manager, session):
        """
        Adjusts Gradient Boosting model hyperparameters based on evaluation
        results. Tracks performance history in data/model_performance.json.

        Strategy:
          - If accuracy < 50%: increase n_estimators, reduce learning_rate
          - Analyzes feature importance split (technical vs news)
          - If news features contributed more to correct predictions, increases
            their weight in the feature vector; otherwise favours technical
          - Saves adjusted params so next train() call can pick them up
        """
        from .database import Prediction

        # Run self-evaluation first to get fresh metrics
        metrics = self.evaluate_and_adjust(db_manager, session)

        if metrics["evaluated"] == 0:
            logger.info("No evaluated predictions available for weight adjustment.")
            return None

        # ---- Load performance history ----
        perf_path = os.path.join(DATA_DIR, "model_performance.json")
        if os.path.exists(perf_path):
            with open(perf_path, "r") as f:
                performance_history = json.load(f)
        else:
            performance_history = {"history": [], "current_params": {}}

        # Initialise current params from history or defaults
        current_params = {
            "n_estimators": 200,
            "learning_rate": 0.1,
            "max_depth": 5,
            "min_samples_split": 10,
            "subsample": 0.8,
            "feature_weights": {"technical": 1.0, "news": 1.0},
        }
        if performance_history.get("current_params"):
            current_params.update(performance_history["current_params"])

        overall_accuracy = metrics["overall_accuracy"]

        # ---- Hyperparameter adjustment based on accuracy ----
        if overall_accuracy < 50:
            # Model is underperforming -- increase complexity
            current_params["n_estimators"] = min(
                current_params["n_estimators"] + 50, 500
            )
            current_params["learning_rate"] = max(
                current_params["learning_rate"] * 0.8, 0.01
            )
            current_params["max_depth"] = min(
                current_params["max_depth"] + 1, 8
            )
            logger.info(
                "Accuracy below 50%% (%.1f%%). Adjusting: n_estimators=%d, "
                "learning_rate=%.4f, max_depth=%d",
                overall_accuracy,
                current_params["n_estimators"],
                current_params["learning_rate"],
                current_params["max_depth"],
            )
        elif overall_accuracy > 70:
            # Model is performing well -- fine-tune with smaller learning rate
            current_params["learning_rate"] = max(
                current_params["learning_rate"] * 0.95, 0.01
            )
            logger.info(
                "Good accuracy (%.1f%%). Fine-tuning learning_rate to %.4f",
                overall_accuracy, current_params["learning_rate"],
            )

        # ---- Feature group analysis (technical vs news) ----
        if self.is_trained and self.direction_model is not None:
            importances = self.direction_model.feature_importances_
            # Feature vector layout: indices 0-10 = technical, 11-20 = news
            technical_importance = float(np.sum(importances[:11]))
            news_importance = float(np.sum(importances[11:]))

            total_importance = technical_importance + news_importance
            if total_importance > 0:
                logger.info(
                    "Feature importance split: technical=%.3f, news=%.3f",
                    technical_importance, news_importance,
                )

            # Evaluate which feature group correlates more with correctness
            evaluated_preds = (
                session.query(Prediction)
                .filter(Prediction.was_correct.isnot(None))
                .order_by(Prediction.evaluated_at.desc())
                .limit(200)
                .all()
            )

            if evaluated_preds:
                correct_news_strength = []
                incorrect_news_strength = []
                correct_tech_strength = []
                incorrect_tech_strength = []

                for p in evaluated_preds:
                    news_signal = abs(p.news_sentiment_avg) if p.news_sentiment_avg else 0
                    tech_signal = abs(p.technical_signal) if p.technical_signal else 0
                    if p.was_correct:
                        correct_news_strength.append(news_signal)
                        correct_tech_strength.append(tech_signal)
                    else:
                        incorrect_news_strength.append(news_signal)
                        incorrect_tech_strength.append(tech_signal)

                avg_correct_news = (
                    float(np.mean(correct_news_strength))
                    if correct_news_strength else 0
                )
                avg_incorrect_news = (
                    float(np.mean(incorrect_news_strength))
                    if incorrect_news_strength else 0
                )
                avg_correct_tech = (
                    float(np.mean(correct_tech_strength))
                    if correct_tech_strength else 0
                )
                avg_incorrect_tech = (
                    float(np.mean(incorrect_tech_strength))
                    if incorrect_tech_strength else 0
                )

                # Adaptive: if news features contributed more to correct
                # predictions, weight them higher in the feature vector
                if avg_correct_news > avg_incorrect_news * 1.2:
                    current_params["feature_weights"]["news"] = min(
                        current_params["feature_weights"]["news"] * 1.1, 2.0
                    )
                    current_params["feature_weights"]["technical"] = max(
                        current_params["feature_weights"]["technical"] * 0.95, 0.5
                    )
                    logger.info(
                        "News features outperforming. news_weight=%.2f, tech_weight=%.2f",
                        current_params["feature_weights"]["news"],
                        current_params["feature_weights"]["technical"],
                    )
                elif avg_correct_tech > avg_incorrect_tech * 1.2:
                    current_params["feature_weights"]["technical"] = min(
                        current_params["feature_weights"]["technical"] * 1.1, 2.0
                    )
                    current_params["feature_weights"]["news"] = max(
                        current_params["feature_weights"]["news"] * 0.95, 0.5
                    )
                    logger.info(
                        "Technical features outperforming. tech_weight=%.2f, news_weight=%.2f",
                        current_params["feature_weights"]["technical"],
                        current_params["feature_weights"]["news"],
                    )

        # ---- Persist performance history ----
        record = {**metrics, "params": current_params}
        performance_history["history"].append(record)
        # Keep last 50 entries
        performance_history["history"] = performance_history["history"][-50:]
        performance_history["current_params"] = current_params

        os.makedirs(os.path.dirname(perf_path), exist_ok=True)
        with open(perf_path, "w") as f:
            json.dump(performance_history, f, indent=2)

        logger.info(
            "Model weights adjusted and saved. History entries: %d",
            len(performance_history["history"]),
        )

        return current_params

    def get_adjusted_params(self):
        """
        Load the latest adjusted hyperparameters from the performance JSON.
        Returns default params if no history exists.
        """
        perf_path = os.path.join(DATA_DIR, "model_performance.json")
        defaults = {
            "n_estimators": 200,
            "learning_rate": 0.1,
            "max_depth": 5,
            "min_samples_split": 10,
            "subsample": 0.8,
            "feature_weights": {"technical": 1.0, "news": 1.0},
        }
        if os.path.exists(perf_path):
            try:
                with open(perf_path, "r") as f:
                    data = json.load(f)
                if data.get("current_params"):
                    defaults.update(data["current_params"])
            except (json.JSONDecodeError, IOError):
                pass
        return defaults


class RecommendationEngine:
    """
    Generates buy recommendations based on AI predictions, news sentiment,
    and technical indicators.  Picks stocks predicted to move up with
    reasonable confidence, attaches supporting news sources, and produces
    a human-readable reasoning text.
    """

    def __init__(self, predictor_instance=None):
        self.predictor = predictor_instance

    def _get_predictor(self):
        """Lazy-resolve predictor so the global is available after module load."""
        if self.predictor is not None:
            return self.predictor
        return predictor  # module-level global

    def generate_recommendations(self, db_manager, session, max_count=20):
        """
        Generate buy recommendations.

        Process:
          1. Get current predictions for all stocks.
          2. Filter for direction == 'up' and confidence > 50%.
          3. For each candidate, gather 2-3+ news sources from the DB.
          4. Build reasoning text from sentiment, technicals, and confidence.
          5. Sort by confidence descending, limit to *max_count*.

        Returns:
            List of recommendation dicts with: stock_key, stock_name, ticker,
            direction, predicted_change_pct, confidence, reasoning,
            sources (list of {title, url, sentiment, date}), timestamp.
        """
        pred_engine = self._get_predictor()
        all_predictions = pred_engine.predict_all(db_manager, session)

        # Filter: "up" direction and confidence > 50%
        # (confidence in prediction dicts is already 0-100 scale)
        candidates = [
            p for p in all_predictions
            if p["direction"] == "up" and p["confidence"] > 50
        ]

        recommendations = []
        for pred in candidates:
            stock_key = pred["stock_key"]
            stock_cfg = STOCKS.get(stock_key, {})

            # Gather news articles for this stock (last 7 days)
            recent_news = db_manager.get_recent_news(
                session, hours=168, stock_key=stock_key
            )

            # Build sources list, preferring diverse sources, at least 2-3
            sources = self._gather_sources(recent_news, min_count=3)

            # Build reasoning
            reasoning = self._build_reasoning(pred, sources)

            recommendations.append({
                "stock_key": stock_key,
                "stock_name": pred.get("stock_name", stock_cfg.get("name", stock_key)),
                "ticker": stock_cfg.get("ticker", ""),
                "direction": pred["direction"],
                "predicted_change_pct": pred["predicted_change_pct"],
                "confidence": pred["confidence"],
                "reasoning": reasoning,
                "sources": sources,
                "timestamp": datetime.now().isoformat(),
            })

        # Sort by confidence descending
        recommendations.sort(key=lambda r: r["confidence"], reverse=True)

        # Limit to max_count
        recommendations = recommendations[:max_count]

        logger.info(
            "Generated %d buy recommendations from %d candidates "
            "(out of %d total predictions).",
            len(recommendations), len(candidates), len(all_predictions),
        )

        return recommendations

    @staticmethod
    def _gather_sources(news_articles, min_count=3):
        """
        Pick at least *min_count* news sources for a recommendation,
        preferring different source names for diversity.
        """
        if not news_articles:
            return []

        # Sort: positive sentiment first, then by recency
        sorted_news = sorted(
            news_articles,
            key=lambda n: (-n.sentiment_score, -(n.published.timestamp() if n.published else 0)),
        )

        seen_sources = set()
        sources = []

        for article in sorted_news:
            source_name = article.source or "Unknown"
            # Prefer articles from distinct sources
            is_new_source = source_name not in seen_sources
            if is_new_source or len(sources) < min_count:
                sources.append({
                    "title": article.title,
                    "url": article.url or "",
                    "sentiment": article.sentiment,
                    "sentiment_score": round(article.sentiment_score, 3),
                    "date": (article.published.isoformat()
                             if article.published else ""),
                    "source": source_name,
                })
                seen_sources.add(source_name)

            # Stop once we have enough diverse sources (at least min_count,
            # and at least 2 distinct source names when possible)
            if len(sources) >= max(min_count, 3) and len(seen_sources) >= 2:
                break

        # If we still have fewer than min_count, pad from remaining articles
        if len(sources) < min_count:
            for article in sorted_news:
                if not any(s["title"] == article.title for s in sources):
                    sources.append({
                        "title": article.title,
                        "url": article.url or "",
                        "sentiment": article.sentiment,
                        "sentiment_score": round(article.sentiment_score, 3),
                        "date": (article.published.isoformat()
                                 if article.published else ""),
                        "source": article.source or "Unknown",
                    })
                if len(sources) >= min_count:
                    break

        return sources

    @staticmethod
    def _build_reasoning(prediction, sources):
        """
        Build a human-readable reasoning text explaining WHY the stock is
        recommended, based on news sentiment, technical indicators, and
        model confidence.
        """
        parts = []
        confidence = prediction["confidence"]
        change = prediction["predicted_change_pct"]
        sentiment_avg = prediction.get("news_sentiment_avg", 0)
        tech_signal = prediction.get("technical_signal", 0)
        news_count = prediction.get("news_count", 0)
        timeframe = prediction.get("timeframe_days", PREDICTION_TIMEFRAME_DAYS)

        # --- Model confidence ---
        if confidence > 75:
            parts.append(
                f"Hohe Modell-Konfidenz ({confidence}%) fuer einen Kursanstieg "
                f"von ca. {change:+.1f}% in den naechsten {timeframe} Tagen."
            )
        elif confidence > 60:
            parts.append(
                f"Moderate Modell-Konfidenz ({confidence}%) fuer "
                f"ca. {change:+.1f}% Aufwaertsbewegung."
            )
        else:
            parts.append(
                f"Modell prognostiziert Aufwaertsbewegung ({confidence}% "
                f"Konfidenz, {change:+.1f}% erwartet)."
            )

        # --- News sentiment ---
        if sentiment_avg > 0.3 and news_count > 3:
            parts.append(
                f"Unterstuetzt durch stark positive Nachrichtenlage "
                f"(Sentiment: {sentiment_avg:+.2f}, {news_count} Artikel)."
            )
        elif sentiment_avg > 0.1 and news_count > 0:
            parts.append(
                f"Leicht positives Nachrichtensentiment "
                f"({sentiment_avg:+.2f}, {news_count} Artikel)."
            )
        elif news_count > 0:
            parts.append(
                f"Gemischte Nachrichtenlage "
                f"({news_count} Artikel, Sentiment: {sentiment_avg:+.2f})."
            )

        # --- Technical indicators ---
        if tech_signal > 3:
            parts.append("Starkes technisches Aufwaertsmomentum.")
        elif tech_signal > 0:
            parts.append("Positives kurzfristiges Momentum.")
        elif tech_signal < -3:
            parts.append(
                "Trotz negativem Momentum sieht das Modell Erholungspotenzial."
            )

        # --- Direction probabilities ---
        dir_probs = prediction.get("direction_probabilities", {})
        if dir_probs:
            up_prob = dir_probs.get("up", 0)
            down_prob = dir_probs.get("down", 0)
            if up_prob > 0 and down_prob > 0:
                parts.append(
                    f"Wahrscheinlichkeiten: Anstieg {up_prob}%, "
                    f"Seitwaerts {dir_probs.get('sideways', 0)}%, "
                    f"Rueckgang {down_prob}%."
                )

        # --- Top supporting news source ---
        positive_sources = [
            s for s in sources if s.get("sentiment") == "positive"
        ]
        if positive_sources:
            top = positive_sources[0]
            parts.append(
                f'Positive Berichterstattung u.a.: "{top["title"]}" '
                f'({top.get("source", "")}).'
            )
        elif sources:
            top = sources[0]
            parts.append(
                f'Juengste Meldung: "{top["title"]}" ({top.get("source", "")}).'
            )

        if not parts:
            parts.append(
                "Empfehlung basiert auf KI-Modell, historischen Mustern "
                "und aktueller Nachrichtenlage."
            )

        return " ".join(parts)

    def save_recommendations_json(self, db_manager, session, max_count=20):
        """
        Generate recommendations and save them to data/recommendations.json.

        Returns:
            Path to the written JSON file.
        """
        recommendations = self.generate_recommendations(
            db_manager, session, max_count
        )

        output = {
            "generated_at": datetime.now().isoformat(),
            "count": len(recommendations),
            "max_requested": max_count,
            "recommendations": recommendations,
        }

        output_path = os.path.join(DATA_DIR, "recommendations.json")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        logger.info(
            "Saved %d recommendations to %s", len(recommendations), output_path
        )

        return output_path


# Global predictor instance
predictor = StockPredictor()

# Global recommendation engine instance
recommendation_engine = RecommendationEngine()
