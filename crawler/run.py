#!/usr/bin/env python3
"""
StockPulse Crawler - Main Runner
Runs the full pipeline: crawl stocks, crawl news, train AI, generate predictions.

Usage:
    python -m crawler.run                  # Run full pipeline once
    python -m crawler.run --daemon         # Run continuously every hour
    python -m crawler.run --stocks         # Only crawl stocks
    python -m crawler.run --news           # Only crawl news
    python -m crawler.run --train          # Only train AI model
    python -m crawler.run --predict        # Only generate predictions
    python -m crawler.run --recommend      # Only generate recommendations (no crawl)
    python -m crawler.run --stats          # Show database statistics
    python -m crawler.run --initial        # First run: fetch max history
"""

import argparse
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawler.stock_crawler import run_stock_crawler, save_stock_json
from crawler.news_crawler import run_news_crawler
from crawler.database import db
from crawler.ai_model import predictor, RecommendationEngine
from crawler.config import CRAWL_INTERVAL, DATA_DIR, STOCKS

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

# Graceful shutdown
running = True


def signal_handler(signum, frame):
    global running
    logger.info("Shutdown signal received. Finishing current cycle...")
    running = False


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def generate_frontend_data(predictions=None):
    """Combine all data into a single JSON file for the frontend."""
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

    # Format AI predictions for frontend
    ai_predictions = []
    if predictions:
        for pred in predictions:
            direction_arrow = "up" if pred["direction"] == "up" else "down" if pred["direction"] == "down" else "sideways"
            change_str = f"{pred['predicted_change_pct']:+.1f}%"
            if pred["direction"] == "sideways":
                change_str = f"+/-{abs(pred['predicted_change_pct']):.1f}%"

            conf_level = "high" if pred["confidence"] > 70 else "medium" if pred["confidence"] > 40 else "low"

            ai_predictions.append({
                "stockKey": pred["stock_key"],
                "stockName": pred["stock_name"],
                "direction": direction_arrow,
                "predictedChange": change_str,
                "confidence": pred["confidence"],
                "confidenceLevel": conf_level,
                "reason": pred["reason"],
                "model": pred["model_name"],
                "newsCount": pred["news_count"],
                "sentimentAvg": pred["news_sentiment_avg"],
                "timeframe": f"{pred['timeframe_days']} Tage",
                "directionProbabilities": pred.get("direction_probabilities", {}),
                "topNews": pred.get("top_news_titles", [])
            })

    # Load recommendations if available
    recommendations_file = os.path.join(DATA_DIR, "recommendations.json")
    recommendations_data = []
    if os.path.exists(recommendations_file):
        try:
            with open(recommendations_file, "r", encoding="utf-8") as f:
                rec_json = json.load(f)
                recommendations_data = rec_json if isinstance(rec_json, list) else rec_json.get("recommendations", [])
        except (json.JSONDecodeError, IOError) as e:
            logger.warning("Could not load recommendations.json: %s", e)

    # Load model performance history if available
    model_performance_file = os.path.join(DATA_DIR, "model_performance.json")
    model_performance_data = {}
    if os.path.exists(model_performance_file):
        try:
            with open(model_performance_file, "r", encoding="utf-8") as f:
                model_performance_data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning("Could not load model_performance.json: %s", e)

    # Get DB stats
    session = db.get_session()
    stats = db.get_db_stats(session)
    accuracy = db.get_prediction_accuracy(session)
    session.close()

    combined = {
        "lastUpdate": datetime.now().isoformat(),
        "stocks": stocks_data.get("stocks", {}),
        "news": {
            "articles": news_data.get("articles", []),
            "sentimentBreakdown": news_data.get("sentimentBreakdown", {}),
            "totalArticles": news_data.get("totalArticles", 0)
        },
        "aiPredictions": ai_predictions,
        "recommendations": recommendations_data,
        "modelInfo": {
            "name": predictor.training_stats.get("trained_at", "not trained"),
            "accuracy": predictor.training_stats.get("accuracy", 0),
            "mae": predictor.training_stats.get("mae", 0),
            "samples": predictor.training_stats.get("samples", 0),
            "topFeatures": predictor.training_stats.get("top_features", [])
        },
        "modelPerformanceHistory": model_performance_data,
        "dbStats": stats,
        "predictionAccuracy": accuracy
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(combined, f, ensure_ascii=False, indent=2)

    logger.info("Frontend data written to %s", output_file)


def run_ai_pipeline():
    """Train model (if needed) and generate predictions."""
    logger.info("=== Running AI pipeline ===")

    session = db.get_session()

    # 1. Evaluate past predictions
    evaluated = predictor.evaluate_past_predictions(db, session)
    if evaluated > 0:
        logger.info("Evaluated %d past predictions", evaluated)

    # 1b. Self-evaluation and weight adjustment based on past performance
    try:
        adjust_result = predictor.evaluate_and_adjust()
        if adjust_result:
            logger.info("Self-evaluation complete: %s", adjust_result)
    except Exception as e:
        logger.warning("Self-evaluation failed (non-critical): %s", e)

    # 2. Train or retrain model
    price_count = db.get_price_count(session)
    news_count = db.get_news_count(session)
    logger.info("DB contains %d price records and %d news articles", price_count, news_count)

    should_train = False
    if not predictor.is_trained:
        predictor.load_model()
    if not predictor.is_trained:
        should_train = True
        logger.info("No trained model found, will train now")
    elif predictor.training_stats:
        # Retrain if model is older than 24 hours
        trained_at = predictor.training_stats.get("trained_at", "")
        if trained_at:
            try:
                trained_time = datetime.fromisoformat(trained_at)
                hours_old = (datetime.now() - trained_time).total_seconds() / 3600
                if hours_old > 24:
                    should_train = True
                    logger.info("Model is %.0f hours old, retraining", hours_old)
            except ValueError:
                should_train = True

    if should_train:
        try:
            success = predictor.train(db, session)
            if success:
                logger.info("Model trained successfully: accuracy=%.1f%%",
                          predictor.training_stats.get("accuracy", 0))
        except ImportError:
            logger.warning("scikit-learn not installed. Using fallback predictions.")
        except Exception as e:
            logger.error("Training failed: %s", e)

    # 3. Generate predictions for all stocks
    logger.info("Generating predictions for %d stocks...", len(STOCKS))
    predictions = predictor.predict_all(db, session)

    # 4. Save predictions to database
    for pred in predictions:
        db.save_prediction(session, {
            "stock_key": pred["stock_key"],
            "prediction_date": (datetime.now() + __import__("datetime").timedelta(
                days=pred["timeframe_days"])).strftime("%Y-%m-%d"),
            "timeframe_days": pred["timeframe_days"],
            "direction": pred["direction"],
            "predicted_change_pct": pred["predicted_change_pct"],
            "confidence": pred["confidence"] / 100.0,
            "model_name": pred["model_name"],
            "news_sentiment_avg": pred["news_sentiment_avg"],
            "news_count": pred["news_count"],
            "technical_signal": pred.get("technical_signal", 0),
            "volatility_30d": pred.get("volatility_30d", 0),
            "reason": pred["reason"],
            "top_news_titles": json.dumps(pred.get("top_news_titles", []))
        })

    session.commit()

    # 5. Generate recommendations from predictions
    try:
        engine = RecommendationEngine(db, session, predictor)
        recommendations = engine.generate_recommendations(max_count=20)
        engine.save_recommendations_json()
        logger.info("Generated %d recommendations", len(recommendations))
    except Exception as e:
        logger.warning("Recommendation generation failed (non-critical): %s", e)

    session.close()

    logger.info("=== AI pipeline complete: %d predictions generated ===", len(predictions))
    return predictions


def run_full_crawl(initial=False):
    """Execute a full crawl cycle: stocks + news + AI + frontend."""
    start_time = time.time()
    logger.info("=" * 60)
    logger.info("CRAWL CYCLE STARTED at %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("=" * 60)

    errors = []
    predictions = None

    # 1. Crawl stock prices
    try:
        stock_data = run_stock_crawler(initial=initial)
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

    # 3. Run AI pipeline
    try:
        predictions = run_ai_pipeline()
        logger.info("Predictions: %d generated", len(predictions) if predictions else 0)
    except Exception as e:
        logger.error("AI pipeline failed: %s", str(e))
        errors.append(f"AI pipeline: {e}")

    # 4. Generate frontend data
    try:
        generate_frontend_data(predictions)
    except Exception as e:
        logger.error("Frontend data generation failed: %s", str(e))
        errors.append(f"Frontend data: {e}")

    elapsed = time.time() - start_time

    # Print DB stats
    try:
        session = db.get_session()
        stats = db.get_db_stats(session)
        session.close()
        logger.info("DB Stats: %d stocks, %d prices, %d news, %d predictions",
                    stats["stocks"], stats["price_records"],
                    stats["news_articles"], stats["predictions"])
    except Exception:
        pass

    logger.info("-" * 60)
    if errors:
        logger.warning("Crawl completed with %d error(s) in %.1fs", len(errors), elapsed)
    else:
        logger.info("Crawl completed successfully in %.1fs", elapsed)
    logger.info("=" * 60)


def run_daemon():
    """Run the crawler in daemon mode (every CRAWL_INTERVAL seconds)."""
    interval = CRAWL_INTERVAL
    logger.info("StockPulse Crawler starting in DAEMON mode")
    logger.info("Crawl interval: %d seconds (%d minutes)", interval, interval // 60)
    logger.info("Tracked stocks: %d", len(STOCKS))

    first_run = True
    while running:
        run_full_crawl(initial=first_run)
        first_run = False

        if not running:
            break

        logger.info("Next crawl in %d minutes. Waiting...", interval // 60)
        sleep_end = time.time() + interval
        while running and time.time() < sleep_end:
            time.sleep(5)

    logger.info("StockPulse Crawler stopped.")


def show_stats():
    """Show database statistics."""
    session = db.get_session()
    stats = db.get_db_stats(session)
    accuracy = db.get_prediction_accuracy(session)
    session.close()

    print("\n=== StockPulse Database Statistics ===")
    print(f"  Tracked Stocks:    {stats['stocks']}")
    print(f"  Price Records:     {stats['price_records']:,}")
    print(f"  News Articles:     {stats['news_articles']:,}")
    print(f"  Predictions:       {stats['predictions']:,}")
    print(f"  Sentiment Records: {stats['sentiment_records']:,}")
    print(f"\n  Prediction Accuracy (90d):")
    print(f"    Total evaluated: {accuracy['total']}")
    print(f"    Correct:         {accuracy['correct']}")
    print(f"    Accuracy:        {accuracy['accuracy']}%")

    if predictor.load_model():
        print(f"\n  Model Info:")
        print(f"    Trained at:      {predictor.training_stats.get('trained_at', 'N/A')}")
        print(f"    Accuracy:        {predictor.training_stats.get('accuracy', 'N/A')}%")
        print(f"    MAE:             {predictor.training_stats.get('mae', 'N/A')}%")
        print(f"    Training samples:{predictor.training_stats.get('samples', 'N/A')}")

    # Recommendation stats
    recommendations_file = os.path.join(DATA_DIR, "recommendations.json")
    if os.path.exists(recommendations_file):
        try:
            with open(recommendations_file, "r", encoding="utf-8") as f:
                rec_json = json.load(f)
                rec_list = rec_json if isinstance(rec_json, list) else rec_json.get("recommendations", [])
                rec_count = len(rec_list)

                # Find last recommendation time
                last_rec_time = "N/A"
                if isinstance(rec_json, dict) and "generated_at" in rec_json:
                    last_rec_time = rec_json["generated_at"]
                elif rec_list:
                    # Try to find timestamp from individual recommendations
                    timestamps = [r.get("generated_at", r.get("timestamp", "")) for r in rec_list if isinstance(r, dict)]
                    timestamps = [t for t in timestamps if t]
                    if timestamps:
                        last_rec_time = max(timestamps)

                print(f"\n  Recommendations:")
                print(f"    Active count:    {rec_count}")
                print(f"    Last generated:  {last_rec_time}")
        except (json.JSONDecodeError, IOError) as e:
            print(f"\n  Recommendations: (error loading: {e})")
    else:
        print(f"\n  Recommendations:   None generated yet")

    # Model performance history
    perf_file = os.path.join(DATA_DIR, "model_performance.json")
    if os.path.exists(perf_file):
        try:
            with open(perf_file, "r", encoding="utf-8") as f:
                perf_data = json.load(f)
                entries = perf_data if isinstance(perf_data, list) else perf_data.get("history", [])
                if entries:
                    latest = entries[-1] if isinstance(entries, list) else {}
                    print(f"\n  Performance History:")
                    print(f"    Entries tracked: {len(entries)}")
                    if isinstance(latest, dict) and "accuracy" in latest:
                        print(f"    Latest accuracy: {latest['accuracy']}%")
        except (json.JSONDecodeError, IOError):
            pass

    print()


def main():
    parser = argparse.ArgumentParser(
        description="StockPulse Web Crawler - Stocks, News & AI Predictions"
    )
    parser.add_argument("--daemon", action="store_true", help="Run continuously every hour")
    parser.add_argument("--stocks", action="store_true", help="Only crawl stock prices")
    parser.add_argument("--news", action="store_true", help="Only crawl news")
    parser.add_argument("--train", action="store_true", help="Only train AI model")
    parser.add_argument("--predict", action="store_true", help="Only generate predictions")
    parser.add_argument("--stats", action="store_true", help="Show database statistics")
    parser.add_argument("--initial", action="store_true", help="First run: fetch max history")
    parser.add_argument("--recommend", action="store_true", help="Only generate recommendations (no crawl)")
    parser.add_argument("--interval", type=int, default=None, help="Custom interval in seconds")

    args = parser.parse_args()

    # Initialize database
    os.makedirs(DATA_DIR, exist_ok=True)
    db.init_db()

    if args.interval:
        global CRAWL_INTERVAL
        CRAWL_INTERVAL = args.interval

    if args.stats:
        show_stats()
    elif args.recommend:
        logger.info("=== Generating recommendations only ===")
        session = db.get_session()
        if not predictor.is_trained:
            predictor.load_model()
        engine = RecommendationEngine(db, session, predictor)
        recommendations = engine.generate_recommendations(max_count=20)
        engine.save_recommendations_json()
        session.close()
        logger.info("Generated %d recommendations", len(recommendations))
        generate_frontend_data()
    elif args.stocks:
        run_stock_crawler(initial=args.initial)
        generate_frontend_data()
    elif args.news:
        run_news_crawler()
        generate_frontend_data()
    elif args.train:
        session = db.get_session()
        predictor.train(db, session)
        session.close()
    elif args.predict:
        predictions = run_ai_pipeline()
        generate_frontend_data(predictions)
    elif args.daemon:
        run_daemon()
    else:
        run_full_crawl(initial=args.initial)


if __name__ == "__main__":
    main()
