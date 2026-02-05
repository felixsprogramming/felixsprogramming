"""
BBF-Trading - Database Layer
SQLAlchemy-based storage for stock prices, news, and predictions.
Designed for millions of rows with proper indexing.
"""

import os
import logging
from datetime import datetime, timedelta

from sqlalchemy import (
    create_engine, Column, Integer, Float, String, Text, DateTime,
    Boolean, Index, func, and_, text
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.pool import QueuePool

from .config import DATA_DIR

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(DATA_DIR, "stockpulse.db")
DB_URL = f"sqlite:///{DB_PATH}"

Base = declarative_base()


# ---- Models ----

class Stock(Base):
    """Tracked stock/index metadata."""
    __tablename__ = "stocks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(50), unique=True, nullable=False, index=True)
    ticker = Column(String(20), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    currency = Column(String(10), default="USD")
    stock_type = Column(String(20), default="stock")  # stock, index, etf, crypto
    sector = Column(String(50), default="")
    exchange = Column(String(50), default="")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PriceHistory(Base):
    """Historical and current price data. Core table, millions of rows."""
    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_key = Column(String(50), nullable=False, index=True)
    date = Column(String(10), nullable=False)  # YYYY-MM-DD
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float, nullable=False)
    volume = Column(Integer, default=0)
    adj_close = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_price_stock_date", "stock_key", "date", unique=True),
        Index("idx_price_date", "date"),
    )


class NewsArticle(Base):
    """Crawled news articles. No limits on storage."""
    __tablename__ = "news_articles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    article_hash = Column(String(32), unique=True, nullable=False, index=True)
    title = Column(Text, nullable=False)
    summary = Column(Text, default="")
    source = Column(String(100), default="")
    url = Column(Text, default="")
    published = Column(DateTime, index=True)
    language = Column(String(5), default="en")
    category = Column(String(50), default="general")

    # Sentiment analysis results
    sentiment = Column(String(10), default="neutral")  # positive, negative, neutral
    sentiment_score = Column(Float, default=0.0)
    sentiment_confidence = Column(Float, default=0.0)
    sentiment_model = Column(String(50), default="keyword")  # keyword, transformer, ensemble

    # Stock associations (comma-separated keys)
    affected_stocks = Column(Text, default="")

    crawled_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_news_published", "published"),
        Index("idx_news_sentiment", "sentiment"),
        Index("idx_news_source", "source"),
    )


class Prediction(Base):
    """AI-generated predictions, stored for tracking accuracy."""
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_key = Column(String(50), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    prediction_date = Column(String(10), nullable=False)  # Target date YYYY-MM-DD
    timeframe_days = Column(Integer, default=7)

    # Prediction
    direction = Column(String(10), nullable=False)  # up, down, sideways
    predicted_change_pct = Column(Float, default=0.0)
    confidence = Column(Float, default=0.0)
    model_name = Column(String(50), default="ensemble")

    # Features used
    news_sentiment_avg = Column(Float, default=0.0)
    news_count = Column(Integer, default=0)
    technical_signal = Column(Float, default=0.0)
    volatility_30d = Column(Float, default=0.0)

    # Reasoning
    reason = Column(Text, default="")
    top_news_titles = Column(Text, default="")

    # Actual result (filled later for accuracy tracking)
    actual_change_pct = Column(Float)
    was_correct = Column(Boolean)
    evaluated_at = Column(DateTime)

    __table_args__ = (
        Index("idx_pred_stock_date", "stock_key", "prediction_date"),
    )


class SentimentTimeseries(Base):
    """Aggregated sentiment per stock per day for fast lookups."""
    __tablename__ = "sentiment_timeseries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_key = Column(String(50), nullable=False)
    date = Column(String(10), nullable=False)
    avg_sentiment = Column(Float, default=0.0)
    news_count = Column(Integer, default=0)
    positive_count = Column(Integer, default=0)
    negative_count = Column(Integer, default=0)
    neutral_count = Column(Integer, default=0)

    __table_args__ = (
        Index("idx_senti_stock_date", "stock_key", "date", unique=True),
    )


class User(Base):
    """User accounts for authentication and admin management."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(80), unique=True, nullable=False, index=True)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)


# ---- Database Manager ----

class DatabaseManager:
    """Manages database connections and operations."""

    def __init__(self, db_url=None):
        self.db_url = db_url or DB_URL
        os.makedirs(DATA_DIR, exist_ok=True)

        self.engine = create_engine(
            self.db_url,
            poolclass=QueuePool,
            pool_size=5,
            max_overflow=10,
            echo=False,
            # SQLite optimizations for large datasets
            connect_args={"check_same_thread": False}
        )
        self.SessionFactory = sessionmaker(bind=self.engine)

    def init_db(self):
        """Create all tables if they don't exist."""
        Base.metadata.create_all(self.engine)
        # Apply SQLite performance pragmas
        with self.engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL;"))
            conn.execute(text("PRAGMA synchronous=NORMAL;"))
            conn.execute(text("PRAGMA cache_size=-64000;"))  # 64MB cache
            conn.execute(text("PRAGMA temp_store=MEMORY;"))
            conn.commit()
        logger.info("Database initialized at %s", self.db_url)

    def get_session(self) -> Session:
        return self.SessionFactory()

    # ---- Stock Operations ----

    def upsert_stock(self, session, key, ticker, name, currency="USD",
                     stock_type="stock", sector="", exchange=""):
        """Insert or update a stock entry."""
        existing = session.query(Stock).filter_by(key=key).first()
        if existing:
            existing.ticker = ticker
            existing.name = name
            existing.currency = currency
            existing.stock_type = stock_type
            existing.sector = sector
            existing.exchange = exchange
            existing.updated_at = datetime.utcnow()
        else:
            session.add(Stock(
                key=key, ticker=ticker, name=name, currency=currency,
                stock_type=stock_type, sector=sector, exchange=exchange
            ))

    def get_active_stocks(self, session):
        """Get all active stocks."""
        return session.query(Stock).filter_by(is_active=True).all()

    # ---- Price Operations ----

    def bulk_insert_prices(self, session, stock_key, price_rows):
        """
        Insert price data in bulk, skipping duplicates.
        price_rows: list of dicts with date, open, high, low, close, volume
        """
        if not price_rows:
            return 0

        inserted = 0
        for row in price_rows:
            existing = session.query(PriceHistory).filter_by(
                stock_key=stock_key, date=row["date"]
            ).first()

            if not existing:
                session.add(PriceHistory(
                    stock_key=stock_key,
                    date=row["date"],
                    open=row.get("open"),
                    high=row.get("high"),
                    low=row.get("low"),
                    close=row["close"],
                    volume=row.get("volume", 0),
                    adj_close=row.get("adj_close")
                ))
                inserted += 1
            else:
                # Update if close price changed
                if existing.close != row["close"]:
                    existing.close = row["close"]
                    existing.high = row.get("high", existing.high)
                    existing.low = row.get("low", existing.low)
                    existing.volume = row.get("volume", existing.volume)

        return inserted

    def get_price_history(self, session, stock_key, days=None, start_date=None):
        """Get price history for a stock."""
        query = session.query(PriceHistory).filter_by(stock_key=stock_key)
        if start_date:
            query = query.filter(PriceHistory.date >= start_date)
        elif days:
            cutoff = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
            query = query.filter(PriceHistory.date >= cutoff)
        return query.order_by(PriceHistory.date.asc()).all()

    def get_latest_price(self, session, stock_key):
        """Get the most recent price entry."""
        return session.query(PriceHistory).filter_by(
            stock_key=stock_key
        ).order_by(PriceHistory.date.desc()).first()

    def get_price_count(self, session, stock_key=None):
        """Count total price records."""
        query = session.query(func.count(PriceHistory.id))
        if stock_key:
            query = query.filter_by(stock_key=stock_key)
        return query.scalar()

    # ---- News Operations ----

    def insert_article(self, session, article_dict):
        """Insert a news article, skip if duplicate."""
        existing = session.query(NewsArticle).filter_by(
            article_hash=article_dict["article_hash"]
        ).first()
        if existing:
            return False

        session.add(NewsArticle(**article_dict))
        return True

    def bulk_insert_articles(self, session, articles):
        """Insert multiple articles, skip duplicates."""
        inserted = 0
        for article in articles:
            if self.insert_article(session, article):
                inserted += 1
        return inserted

    def get_recent_news(self, session, hours=72, stock_key=None, limit=None):
        """Get recent news articles."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        query = session.query(NewsArticle).filter(
            NewsArticle.published >= cutoff
        )
        if stock_key:
            query = query.filter(
                NewsArticle.affected_stocks.contains(stock_key)
            )
        query = query.order_by(NewsArticle.published.desc())
        if limit:
            query = query.limit(limit)
        return query.all()

    def get_news_count(self, session):
        """Count total news articles."""
        return session.query(func.count(NewsArticle.id)).scalar()

    def get_news_for_date_range(self, session, start_date, end_date, stock_key=None):
        """Get news articles within a date range."""
        query = session.query(NewsArticle).filter(
            and_(
                NewsArticle.published >= start_date,
                NewsArticle.published <= end_date
            )
        )
        if stock_key:
            query = query.filter(
                NewsArticle.affected_stocks.contains(stock_key)
            )
        return query.order_by(NewsArticle.published.asc()).all()

    # ---- Prediction Operations ----

    def save_prediction(self, session, prediction_dict):
        """Save a new prediction."""
        session.add(Prediction(**prediction_dict))

    def get_latest_predictions(self, session, stock_key=None):
        """Get the most recent predictions."""
        query = session.query(Prediction)
        if stock_key:
            query = query.filter_by(stock_key=stock_key)
        return query.order_by(Prediction.created_at.desc()).limit(50).all()

    def get_unevaluated_predictions(self, session):
        """Get predictions that haven't been checked against actual results."""
        return session.query(Prediction).filter(
            Prediction.was_correct.is_(None),
            Prediction.prediction_date <= datetime.utcnow().strftime("%Y-%m-%d")
        ).all()

    def evaluate_prediction(self, session, prediction_id, actual_change_pct):
        """Evaluate a prediction against actual results."""
        pred = session.query(Prediction).filter_by(id=prediction_id).first()
        if not pred:
            return
        pred.actual_change_pct = actual_change_pct
        if pred.direction == "up":
            pred.was_correct = actual_change_pct > 0
        elif pred.direction == "down":
            pred.was_correct = actual_change_pct < 0
        else:
            pred.was_correct = abs(actual_change_pct) < 2.0
        pred.evaluated_at = datetime.utcnow()

    def get_prediction_accuracy(self, session, stock_key=None, days=90):
        """Calculate prediction accuracy over a time period."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        query = session.query(Prediction).filter(
            Prediction.was_correct.isnot(None),
            Prediction.created_at >= cutoff
        )
        if stock_key:
            query = query.filter_by(stock_key=stock_key)

        predictions = query.all()
        if not predictions:
            return {"total": 0, "correct": 0, "accuracy": 0.0}

        correct = sum(1 for p in predictions if p.was_correct)
        return {
            "total": len(predictions),
            "correct": correct,
            "accuracy": round(correct / len(predictions) * 100, 1)
        }

    # ---- Sentiment Timeseries ----

    def update_sentiment_timeseries(self, session, stock_key, date_str,
                                     avg_sentiment, news_count,
                                     pos_count, neg_count, neu_count):
        """Update aggregated sentiment for a stock/date."""
        existing = session.query(SentimentTimeseries).filter_by(
            stock_key=stock_key, date=date_str
        ).first()
        if existing:
            existing.avg_sentiment = avg_sentiment
            existing.news_count = news_count
            existing.positive_count = pos_count
            existing.negative_count = neg_count
            existing.neutral_count = neu_count
        else:
            session.add(SentimentTimeseries(
                stock_key=stock_key, date=date_str,
                avg_sentiment=avg_sentiment, news_count=news_count,
                positive_count=pos_count, negative_count=neg_count,
                neutral_count=neu_count
            ))

    def get_sentiment_history(self, session, stock_key, days=90):
        """Get sentiment timeseries for a stock."""
        cutoff = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
        return session.query(SentimentTimeseries).filter(
            SentimentTimeseries.stock_key == stock_key,
            SentimentTimeseries.date >= cutoff
        ).order_by(SentimentTimeseries.date.asc()).all()

    # ---- Stats ----

    def get_db_stats(self, session):
        """Get database statistics."""
        return {
            "stocks": session.query(func.count(Stock.id)).scalar(),
            "price_records": session.query(func.count(PriceHistory.id)).scalar(),
            "news_articles": session.query(func.count(NewsArticle.id)).scalar(),
            "predictions": session.query(func.count(Prediction.id)).scalar(),
            "sentiment_records": session.query(func.count(SentimentTimeseries.id)).scalar()
        }

    # ---- User Operations ----

    def create_user(self, session, username, email, password_hash, is_admin=False):
        """Create a new user. Returns the new User or None if duplicate."""
        existing = session.query(User).filter(
            (User.username == username) | (User.email == email)
        ).first()
        if existing:
            return None
        user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            is_admin=is_admin
        )
        session.add(user)
        session.flush()  # Populate id before returning
        return user

    def get_user_by_username(self, session, username):
        """Get a user by username. Returns User or None."""
        return session.query(User).filter_by(username=username).first()

    def get_user_by_id(self, session, user_id):
        """Get a user by id. Returns User or None."""
        return session.query(User).filter_by(id=user_id).first()

    def get_all_users(self, session):
        """Return a list of all users."""
        return session.query(User).order_by(User.created_at.asc()).all()

    def update_user_last_login(self, session, user_id):
        """Set last_login to the current UTC time."""
        user = session.query(User).filter_by(id=user_id).first()
        if user:
            user.last_login = datetime.utcnow()

    def update_user(self, session, user_id, **kwargs):
        """Update user fields (email, is_admin, is_active). Returns the updated User or None."""
        user = session.query(User).filter_by(id=user_id).first()
        if not user:
            return None
        allowed_fields = {"email", "is_admin", "is_active"}
        for field, value in kwargs.items():
            if field in allowed_fields:
                setattr(user, field, value)
        return user

    def delete_user(self, session, user_id):
        """Delete a user by id. Returns True if deleted, False if not found."""
        user = session.query(User).filter_by(id=user_id).first()
        if not user:
            return False
        session.delete(user)
        return True

    def count_users(self, session):
        """Return the total user count."""
        return session.query(func.count(User.id)).scalar()

    def create_default_admin(self, session):
        """
        Create an admin/admin user if no users exist (first-time setup).
        The password hash should be a bcrypt hash of 'admin'.
        Returns the admin User if created, None if users already exist.
        """
        if self.count_users(session) > 0:
            return None
        # bcrypt hash of the string 'admin'
        # This is a pre-computed bcrypt hash so the app does not need bcrypt at import time.
        default_hash = "$2b$12$LJ3m4ys3Lk0TSwMBfmBc5u0C6XEIbsXCFjKQHargOvnBYMo4AhJSe"
        admin = self.create_user(
            session,
            username="admin",
            email="admin@stockpulse.local",
            password_hash=default_hash,
            is_admin=True
        )
        logger.info("Default admin user created (username: admin)")
        return admin


# Global instance
db = DatabaseManager()
