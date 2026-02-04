"""
StockPulse - AI Prediction Model
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
    AI_MODEL_DIR, MIN_TRAINING_SAMPLES, PREDICTION_TIMEFRAME_DAYS,
    USE_TRANSFORMER_SENTIMENT, STOCKS
)

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
    def build_feature_vector(technical, news):
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


# Global predictor instance
predictor = StockPredictor()
