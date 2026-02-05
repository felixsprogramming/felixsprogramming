/* ========================================
   BBF-Trading - Prediction Engine
   News-based stock prediction logic
   ======================================== */

const PredictionEngine = {

    // Sentiment weights by news category
    categoryWeights: {
        policy: 1.2,       // Central bank / government policy
        tech: 1.3,         // Technology news
        earnings: 1.4,     // Earnings reports
        geopolitics: 1.1,  // Geopolitical events
        economy: 1.2,      // Economic data
        product: 1.0,      // Product launches
        market: 0.9,       // General market news
        pandemic: 1.5,     // Health crises
        finance: 1.1,      // Financial sector news
        commodities: 0.9,  // Commodity prices
        management: 0.8,   // Management changes
        acquisition: 1.0,  // M&A activity
        business: 0.9      // General business
    },

    // Historical correlation strength per stock
    stockSensitivity: {
        dax: 0.85,
        dowjones: 0.82,
        sp500: 0.80,
        nasdaq: 0.90,
        apple: 0.88,
        microsoft: 0.86,
        tesla: 0.95,      // Very news-sensitive
        siemens: 0.75,
        sap: 0.78
    },

    // Calculate aggregate sentiment for a stock based on current news
    calculateStockSentiment(stockKey) {
        const relevantNews = CurrentNews.filter(n => n.affectedStocks.includes(stockKey));
        if (relevantNews.length === 0) return { score: 0, confidence: 0, newsCount: 0 };

        let totalScore = 0;
        let totalWeight = 0;

        relevantNews.forEach(news => {
            const catWeight = this.categoryWeights[news.category] || 1.0;
            const weight = catWeight * Math.abs(news.score);
            totalScore += news.score * catWeight;
            totalWeight += weight;
        });

        const avgScore = totalWeight > 0 ? totalScore / relevantNews.length : 0;
        const sensitivity = this.stockSensitivity[stockKey] || 0.8;
        const adjustedScore = avgScore * sensitivity;

        // Confidence based on number of signals and their agreement
        const agreement = Math.abs(totalScore) / (relevantNews.length * 1.0);
        const confidence = Math.min(0.95, Math.max(0.2, agreement * 0.7 + (relevantNews.length / 12) * 0.3));

        return {
            score: adjustedScore,
            confidence: confidence,
            newsCount: relevantNews.length
        };
    },

    // Generate prediction for a specific stock
    generatePrediction(stockKey) {
        const stock = StockData[stockKey];
        if (!stock) return null;

        const sentiment = this.calculateStockSentiment(stockKey);
        const recentData = stock.data.slice(-30);

        // Technical momentum (simple moving average trend)
        const sma5 = recentData.slice(-5).reduce((s, d) => s + d.value, 0) / 5;
        const sma20 = recentData.slice(-20).reduce((s, d) => s + d.value, 0) / 20;
        const technicalSignal = (sma5 - sma20) / sma20;

        // Combined score: 60% news sentiment, 40% technical
        const combinedScore = sentiment.score * 0.6 + technicalSignal * 100 * 0.4;

        // Determine direction
        let direction, directionLabel, predictedChange;
        if (combinedScore > 0.15) {
            direction = 'up';
            directionLabel = 'Steigend';
            predictedChange = '+' + (Math.abs(combinedScore) * 2.5).toFixed(1) + '%';
        } else if (combinedScore < -0.15) {
            direction = 'down';
            directionLabel = 'Fallend';
            predictedChange = '-' + (Math.abs(combinedScore) * 2.5).toFixed(1) + '%';
        } else {
            direction = 'sideways';
            directionLabel = 'Seitwaerts';
            predictedChange = '+/-' + (Math.abs(combinedScore) * 1.5).toFixed(1) + '%';
        }

        // Generate reasoning
        const reason = this.generateReason(stockKey, sentiment, direction);

        // Confidence level
        let confidenceLevel;
        if (sentiment.confidence > 0.7) confidenceLevel = 'high';
        else if (sentiment.confidence > 0.4) confidenceLevel = 'medium';
        else confidenceLevel = 'low';

        // Get top news sources with URLs for clickable links
        const relevantNews = CurrentNews.filter(n => n.affectedStocks.includes(stockKey));
        const topNewsSources = relevantNews
            .sort((a, b) => Math.abs(b.score) - Math.abs(a.score))
            .slice(0, 3)
            .map(n => ({
                title: n.title,
                url: n.url || '',
                sentiment: n.sentiment
            }));

        return {
            stockKey: stockKey,
            stockName: stock.name + (stock.ticker ? ' (' + stock.ticker + ')' : ''),
            direction: direction,
            directionLabel: directionLabel,
            predictedChange: predictedChange,
            confidence: Math.round(sentiment.confidence * 100),
            confidenceLevel: confidenceLevel,
            reason: reason,
            newsCount: sentiment.newsCount,
            timeframe: '7 Tage',
            topNewsSources: topNewsSources
        };
    },

    // Generate human-readable reasoning for prediction
    generateReason(stockKey, sentiment, direction) {
        const relevantNews = CurrentNews.filter(n => n.affectedStocks.includes(stockKey));
        const positiveNews = relevantNews.filter(n => n.sentiment === 'positive');
        const negativeNews = relevantNews.filter(n => n.sentiment === 'negative');

        let reason = '';

        if (direction === 'up') {
            if (positiveNews.length > 0) {
                reason = 'Positive Nachrichtenlage (' + positiveNews.length + ' bullische Signale). ';
                reason += 'Besonders relevant: "' + positiveNews[0].title + '". ';
            }
            if (negativeNews.length > 0) {
                reason += 'Trotz ' + negativeNews.length + ' negativer Meldung(en) ueberwiegt das positive Sentiment.';
            } else {
                reason += 'Kein nennenswerter negativer Gegenwind erkennbar.';
            }
        } else if (direction === 'down') {
            if (negativeNews.length > 0) {
                reason = 'Belastende Nachrichtenlage (' + negativeNews.length + ' bearische Signale). ';
                reason += 'Hauptfaktor: "' + negativeNews[0].title + '". ';
            }
            if (positiveNews.length > 0) {
                reason += 'Positive Gegensignale (' + positiveNews.length + ') reichen nicht fuer eine Trendwende.';
            } else {
                reason += 'Keine positiven Impulse in Sicht.';
            }
        } else {
            reason = 'Gemischte Signale: ' + positiveNews.length + ' positive und ' + negativeNews.length + ' negative Nachrichten. ';
            reason += 'Der Markt wartet auf klare Impulse fuer eine Richtungsentscheidung.';
        }

        return reason;
    },

    // Generate predictions for all tracked stocks
    // Returns AI predictions if available, otherwise uses frontend engine
    generateAllPredictions() {
        if (typeof AIPredictions !== 'undefined' && AIPredictions.length > 0) {
            return AIPredictions.map(pred => ({
                stockKey: pred.stock_key || '',
                stockName: pred.stockName || pred.stock_key || '',
                direction: pred.direction || 'sideways',
                directionLabel: pred.direction === 'up' ? 'Steigend' : pred.direction === 'down' ? 'Fallend' : 'Seitwaerts',
                predictedChange: pred.predicted_change_pct
                    ? (pred.predicted_change_pct >= 0 ? '+' : '') + pred.predicted_change_pct.toFixed(1) + '%'
                    : '+/-0.0%',
                confidence: Math.round((pred.confidence || 0.5) * 100),
                confidenceLevel: (pred.confidence || 0.5) > 0.7 ? 'high' : (pred.confidence || 0.5) > 0.4 ? 'medium' : 'low',
                reason: pred.reason || pred.news_summary || 'KI-Analyse basierend auf technischen und News-Daten',
                newsCount: pred.news_count || 0,
                timeframe: pred.timeframe || '7 Tage',
                isAI: true
            }));
        }
        const stocks = ['dax', 'dowjones', 'apple', 'microsoft', 'tesla', 'siemens', 'sap'];
        return stocks.map(key => this.generatePrediction(key)).filter(p => p !== null);
    },

    // Calculate overall market sentiment
    getMarketSentiment(category) {
        let stocks;
        switch (category) {
            case 'dax':
                stocks = ['dax', 'siemens', 'sap'];
                break;
            case 'dow':
                stocks = ['dowjones'];
                break;
            case 'tech':
                stocks = ['apple', 'microsoft', 'tesla', 'nasdaq'];
                break;
            default:
                stocks = Object.keys(StockData);
        }

        let totalScore = 0;
        let count = 0;

        stocks.forEach(key => {
            const sentiment = this.calculateStockSentiment(key);
            if (sentiment.newsCount > 0) {
                totalScore += sentiment.score;
                count++;
            }
        });

        // Return value between -100 and +100
        const avg = count > 0 ? totalScore / count : 0;
        return Math.round(Math.max(-100, Math.min(100, avg * 120)));
    }
};
