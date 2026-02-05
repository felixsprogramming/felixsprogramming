/* ========================================
   BBF-Trading - Stock & News Data
   Loads live data from crawler JSON files,
   falls back to generated demo data if unavailable.
   ======================================== */

// ---- Live Data Loader ----
const LiveDataLoader = {
    liveData: null,
    isLive: false,

    async load() {
        try {
            const response = await fetch('data/live_data.json');
            if (!response.ok) throw new Error('No live data available');
            this.liveData = await response.json();
            this.isLive = true;
            console.log('[BBF-Trading] Live data loaded:', this.liveData.lastUpdate);
        } catch (e) {
            console.log('[BBF-Trading] No live data found, using demo data.', e.message);
            this.isLive = false;
            return false;
        }

        // Also try to load recommendations from separate file (fallback)
        try {
            var recRes = await fetch('data/recommendations.json');
            if (recRes.ok) {
                var recData = await recRes.json();
                var recList = null;
                if (Array.isArray(recData)) {
                    recList = recData;
                } else if (recData && recData.recommendations) {
                    recList = recData.recommendations;
                }
                if (recList && recList.length > 0) {
                    // Use separate file if live_data has no recommendations
                    if (!this.liveData.recommendations || this.liveData.recommendations.length === 0) {
                        this.liveData.recommendations = recList;
                        console.log('[BBF-Trading] Recommendations loaded from recommendations.json:', recList.length);
                    }
                }
            }
        } catch (e) {
            // recommendations.json not yet generated, that is fine
        }

        return true;
    },

    applyToStockData() {
        if (!this.liveData || !this.liveData.stocks) return;

        Object.keys(this.liveData.stocks).forEach(key => {
            const live = this.liveData.stocks[key];
            if (!live) return;

            // Update existing StockData entry or create new one
            if (StockData[key]) {
                StockData[key].currentValue = live.currentPrice;
                StockData[key].change = live.changePercent;
                StockData[key].name = live.name;
                StockData[key].currency = live.currency;

                // Replace history with real data
                if (live.history && live.history.length > 0) {
                    StockData[key].data = live.history.map(h => ({
                        date: h.date,
                        value: h.close
                    }));
                }
            } else {
                // New stock from crawler not in defaults
                StockData[key] = {
                    name: live.name,
                    ticker: live.ticker,
                    currency: live.currency,
                    currentValue: live.currentPrice,
                    change: live.changePercent,
                    data: (live.history || []).map(h => ({
                        date: h.date,
                        value: h.close
                    }))
                };
            }
        });

        // Update dashboard display values
        this.updateDashboardValues();
    },

    applyToNewsData() {
        if (!this.liveData || !this.liveData.news || !this.liveData.news.articles) return;

        // Replace CurrentNews with live crawled news
        CurrentNews.length = 0;
        this.liveData.news.articles.forEach(article => {
            CurrentNews.push({
                title: article.title,
                source: article.source,
                time: article.relativeTime || 'unbekannt',
                sentiment: article.sentiment || 'neutral',
                score: article.sentimentScore || 0,
                affectedStocks: article.affectedStocks || [],
                category: article.category || 'general',
                url: article.url || '',
                summary: article.summary || ''
            });
        });

        // Also update TopStocks table from live data
        this.updateTopStocks();
    },

    updateDashboardValues() {
        const updates = {
            'dax': { valueEl: 'dax-value', changeEl: 'dax-change' },
            'dowjones': { valueEl: 'dow-value', changeEl: 'dow-change' },
            'sp500': { valueEl: 'sp500-value', changeEl: 'sp500-change' },
            'nasdaq': { valueEl: 'nasdaq-value', changeEl: 'nasdaq-change' }
        };

        Object.keys(updates).forEach(key => {
            const stock = StockData[key];
            if (!stock) return;

            const valueEl = document.getElementById(updates[key].valueEl);
            const changeEl = document.getElementById(updates[key].changeEl);

            if (valueEl) {
                valueEl.textContent = stock.currentValue.toLocaleString('de-DE', {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2
                });
            }
            if (changeEl) {
                const prefix = stock.change >= 0 ? '+' : '';
                changeEl.textContent = prefix + stock.change.toFixed(2) + '%';
                changeEl.className = 'index-change ' + (stock.change >= 0 ? 'positive' : 'negative');
            }
        });
    },

    updateTopStocks() {
        const stockKeys = ['apple', 'microsoft', 'tesla', 'nvidia', 'sap', 'siemens', 'amazon', 'alphabet'];

        TopStocks.length = 0;
        stockKeys.forEach(key => {
            const stock = StockData[key];
            if (!stock) return;

            // Find sentiment from news
            const relevantNews = CurrentNews.filter(n => n.affectedStocks.includes(key));
            let avgSentiment = 0;
            if (relevantNews.length > 0) {
                avgSentiment = relevantNews.reduce((sum, n) => sum + n.score, 0) / relevantNews.length;
            }

            let sentimentType, sentimentLabel;
            if (avgSentiment > 0.3) { sentimentType = 'positive'; sentimentLabel = 'Bullish'; }
            else if (avgSentiment < -0.3) { sentimentType = 'negative'; sentimentLabel = 'Bearish'; }
            else { sentimentType = 'neutral'; sentimentLabel = 'Neutral'; }

            TopStocks.push({
                name: stock.name,
                ticker: stock.ticker || key.toUpperCase(),
                price: stock.currentValue.toLocaleString('de-DE', { minimumFractionDigits: 2 }),
                change: (stock.change >= 0 ? '+' : '') + stock.change.toFixed(2) + '%',
                changeType: stock.change >= 0 ? 'positive' : 'negative',
                sentiment: sentimentType,
                sentimentLabel: sentimentLabel
            });
        });
    },

    // Apply AI predictions from crawler
    applyAIPredictions() {
        if (!this.liveData || !this.liveData.aiPredictions) return;

        AIPredictions.length = 0;
        this.liveData.aiPredictions.forEach(pred => {
            AIPredictions.push(pred);
        });

        // Store model info
        if (this.liveData.modelInfo) {
            AIModelInfo.accuracy = this.liveData.modelInfo.accuracy || 0;
            AIModelInfo.mae = this.liveData.modelInfo.mae || 0;
            AIModelInfo.samples = this.liveData.modelInfo.samples || 0;
            AIModelInfo.trainedAt = this.liveData.modelInfo.name || '';
            AIModelInfo.topFeatures = this.liveData.modelInfo.topFeatures || [];
        }
        if (this.liveData.dbStats) {
            AIModelInfo.dbStats = this.liveData.dbStats;
        }
        if (this.liveData.predictionAccuracy) {
            AIModelInfo.predictionAccuracy = this.liveData.predictionAccuracy;
        }
    },

    // Apply reverse correlation data from crawler
    applyCorrelations() {
        if (!this.liveData || !this.liveData.correlations) return;
        var corrData = this.liveData.correlations;
        ReverseCorrelations.length = 0;
        if (corrData.correlations) {
            corrData.correlations.forEach(function(c) { ReverseCorrelations.push(c); });
        }
        CorrelationStats.total_movements = corrData.total_movements || 0;
        CorrelationStats.explained_count = corrData.explained_count || 0;
        CorrelationStats.overall_strength = corrData.overall_correlation_strength || 0;
    },

    // Apply AI recommendations from crawler
    applyRecommendations() {
        if (!this.liveData || !this.liveData.recommendations) return;

        Recommendations.length = 0;
        this.liveData.recommendations.forEach(rec => {
            Recommendations.push({
                stock_key: rec.stock_key || '',
                stock_name: rec.stock_name || '',
                ticker: rec.ticker || '',
                direction: rec.direction || 'sideways',
                predicted_change_pct: rec.predicted_change_pct || 0,
                confidence: rec.confidence || 0,
                reasoning: rec.reasoning || '',
                sources: rec.sources || [],
                timestamp: rec.timestamp || ''
            });
        });
    }
};

// ---- AI Predictions (filled by live data or empty) ----
const AIPredictions = [];
const AIModelInfo = {
    accuracy: 0, mae: 0, samples: 0, trainedAt: '',
    topFeatures: [], dbStats: {}, predictionAccuracy: {}
};

// ---- AI Recommendations (filled by live data or empty) ----
const Recommendations = [];

// ---- Reverse Correlations (filled by live data or empty) ----
var ReverseCorrelations = [];
var CorrelationStats = { total_movements: 0, explained_count: 0, overall_strength: 0 };

// ---- Demo Data Generation (Fallback) ----

function generateStockData(startDate, endDate, startValue, volatility, trend) {
    const data = [];
    const start = new Date(startDate);
    const end = new Date(endDate);
    let value = startValue;

    for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
        if (d.getDay() === 0 || d.getDay() === 6) continue;
        const change = (Math.random() - 0.48 + trend) * volatility * value / 100;
        value = Math.max(value + change, value * 0.7);
        data.push({
            date: new Date(d).toISOString().split('T')[0],
            value: Math.round(value * 100) / 100
        });
    }
    return data;
}

// Default stock data (used when crawler data is not available)
const StockData = {
    dax: {
        name: 'DAX',
        currency: 'EUR',
        currentValue: 18456.23,
        change: 1.24,
        data: generateStockData('2019-01-01', '2026-01-31', 10800, 1.8, 0.015)
    },
    dowjones: {
        name: 'Dow Jones',
        currency: 'USD',
        currentValue: 38912.45,
        change: 0.87,
        data: generateStockData('2019-01-01', '2026-01-31', 23500, 1.5, 0.018)
    },
    sp500: {
        name: 'S&P 500',
        currency: 'USD',
        currentValue: 5234.18,
        change: -0.32,
        data: generateStockData('2019-01-01', '2026-01-31', 2500, 1.6, 0.02)
    },
    nasdaq: {
        name: 'NASDAQ',
        currency: 'USD',
        currentValue: 16789.56,
        change: 1.56,
        data: generateStockData('2019-01-01', '2026-01-31', 6700, 2.2, 0.022)
    },
    apple: {
        name: 'Apple', ticker: 'AAPL', currency: 'USD', currentValue: 213.45, change: 2.15,
        data: generateStockData('2019-01-01', '2026-01-31', 38, 2.5, 0.025)
    },
    microsoft: {
        name: 'Microsoft', ticker: 'MSFT', currency: 'USD', currentValue: 425.80, change: 1.43,
        data: generateStockData('2019-01-01', '2026-01-31', 100, 2.0, 0.022)
    },
    tesla: {
        name: 'Tesla', ticker: 'TSLA', currency: 'USD', currentValue: 248.67, change: -2.34,
        data: generateStockData('2019-01-01', '2026-01-31', 22, 4.5, 0.03)
    },
    siemens: {
        name: 'Siemens', ticker: 'SIE', currency: 'EUR', currentValue: 188.42, change: 0.78,
        data: generateStockData('2019-01-01', '2026-01-31', 95, 1.8, 0.012)
    },
    sap: {
        name: 'SAP', ticker: 'SAP', currency: 'EUR', currentValue: 196.35, change: 1.89,
        data: generateStockData('2019-01-01', '2026-01-31', 90, 2.0, 0.015)
    }
};

// Apply COVID crash pattern
function applyCrashPattern(data, crashStartDate, crashEndDate, dropPercent, recoveryMonths) {
    const crashStart = new Date(crashStartDate);
    const crashEnd = new Date(crashEndDate);
    const recoveryEnd = new Date(crashEnd);
    recoveryEnd.setMonth(recoveryEnd.getMonth() + recoveryMonths);
    let preCrashValue = null;

    data.forEach((point, index) => {
        const d = new Date(point.date);
        if (d >= crashStart && d <= crashEnd) {
            if (!preCrashValue && index > 0) preCrashValue = data[index - 1].value;
            const progress = (d - crashStart) / (crashEnd - crashStart);
            const drop = preCrashValue * dropPercent * Math.sin(progress * Math.PI / 2);
            point.value = Math.round((preCrashValue - drop) * 100) / 100;
        } else if (d > crashEnd && d <= recoveryEnd && preCrashValue) {
            const bottomValue = preCrashValue * (1 - dropPercent);
            const recoveryProgress = (d - crashEnd) / (recoveryEnd - crashEnd);
            const recovered = bottomValue + (preCrashValue - bottomValue) * Math.pow(recoveryProgress, 0.7);
            point.value = Math.round(recovered * 100) / 100;
        }
    });
}

Object.keys(StockData).forEach(key => {
    applyCrashPattern(StockData[key].data, '2020-02-20', '2020-03-23', 0.35, 10);
});

// ---- News Events (historical, always available) ----
const NewsEvents = {
    dax: [
        { date: '2020-03-11', title: 'WHO erklaert COVID-19 zur Pandemie', sentiment: 'negative', impact: -12.2, category: 'pandemic', url: '#' },
        { date: '2020-03-23', title: 'Deutschland geht in den ersten Lockdown', sentiment: 'negative', impact: -5.8, category: 'policy', url: '#' },
        { date: '2020-11-09', title: 'BioNTech/Pfizer Impfstoff zeigt 95% Wirksamkeit', sentiment: 'positive', impact: +8.4, category: 'pharma', url: '#' },
        { date: '2021-06-15', title: 'EZB haelt an lockerer Geldpolitik fest', sentiment: 'positive', impact: +2.1, category: 'policy', url: '#' },
        { date: '2022-02-24', title: 'Russland beginnt Invasion der Ukraine', sentiment: 'negative', impact: -8.7, category: 'geopolitics', url: '#' },
        { date: '2022-07-21', title: 'EZB erhoeht Zinsen erstmals seit 11 Jahren', sentiment: 'negative', impact: -3.2, category: 'policy', url: '#' },
        { date: '2023-01-30', title: 'ChatGPT erreicht 100 Mio. Nutzer - KI-Boom beginnt', sentiment: 'positive', impact: +4.5, category: 'tech', url: '#' },
        { date: '2023-10-07', title: 'Hamas-Angriff auf Israel - Nahost-Krise eskaliert', sentiment: 'negative', impact: -2.8, category: 'geopolitics', url: '#' },
        { date: '2024-03-15', title: 'EZB signalisiert erste Zinssenkung', sentiment: 'positive', impact: +3.1, category: 'policy', url: '#' },
        { date: '2024-11-05', title: 'US-Wahl: Unsicherheit belastet Maerkte', sentiment: 'negative', impact: -1.9, category: 'politics', url: '#' },
        { date: '2025-01-20', title: 'Deutsche Wirtschaft zeigt Erholungszeichen', sentiment: 'positive', impact: +2.3, category: 'economy', url: '#' },
        { date: '2025-06-15', title: 'Neues EU-Konjunkturpaket beschlossen', sentiment: 'positive', impact: +3.5, category: 'policy', url: '#' },
        { date: '2025-09-10', title: 'DAX erreicht neues Allzeithoch', sentiment: 'positive', impact: +1.8, category: 'market', url: '#' }
    ],
    dowjones: [
        { date: '2020-03-11', title: 'WHO declares COVID-19 global pandemic', sentiment: 'negative', impact: -10.5, category: 'pandemic', url: '#' },
        { date: '2020-03-23', title: 'Fed announces unlimited QE program', sentiment: 'positive', impact: +11.4, category: 'policy', url: '#' },
        { date: '2020-11-09', title: 'Biden wins US election, vaccine news', sentiment: 'positive', impact: +5.2, category: 'politics', url: '#' },
        { date: '2021-01-27', title: 'GameStop Short Squeeze schockt Wall Street', sentiment: 'negative', impact: -2.1, category: 'market', url: '#' },
        { date: '2022-01-26', title: 'Fed kuendigt aggressive Zinsplaene an', sentiment: 'negative', impact: -6.3, category: 'policy', url: '#' },
        { date: '2022-06-13', title: 'US-Inflation erreicht 9.1% - 40-Jahres-Hoch', sentiment: 'negative', impact: -4.8, category: 'economy', url: '#' },
        { date: '2023-03-10', title: 'Silicon Valley Bank Kollaps', sentiment: 'negative', impact: -3.5, category: 'finance', url: '#' },
        { date: '2023-05-24', title: 'NVIDIA Q1 Zahlen uebertreffen alle Erwartungen', sentiment: 'positive', impact: +4.2, category: 'tech', url: '#' },
        { date: '2024-01-15', title: 'KI-Investments treiben Maerkte auf Rekordhoehen', sentiment: 'positive', impact: +3.8, category: 'tech', url: '#' },
        { date: '2024-08-05', title: 'Japan Carry-Trade Crash - globale Panik', sentiment: 'negative', impact: -5.1, category: 'market', url: '#' },
        { date: '2025-03-20', title: 'Fed senkt Zinsen auf 3.5%', sentiment: 'positive', impact: +2.9, category: 'policy', url: '#' },
        { date: '2025-07-22', title: 'Tech-Sektor Korrektur nach Gewinnwarnungen', sentiment: 'negative', impact: -3.2, category: 'tech', url: '#' }
    ],
    apple: [
        { date: '2020-03-23', title: 'COVID-Crash: Apple Stores weltweit geschlossen', sentiment: 'negative', impact: -8.2, category: 'pandemic', url: '#' },
        { date: '2020-07-30', title: 'Apple meldet Rekordquartal trotz Pandemie', sentiment: 'positive', impact: +10.5, category: 'earnings', url: '#' },
        { date: '2021-01-27', title: 'iPhone 12 treibt Umsatz auf Allzeithoch', sentiment: 'positive', impact: +5.3, category: 'product', url: '#' },
        { date: '2023-06-05', title: 'Apple Vision Pro vorgestellt', sentiment: 'positive', impact: +7.8, category: 'product', url: '#' },
        { date: '2024-05-02', title: 'Apple Aktienrueckkauf: $110 Milliarden', sentiment: 'positive', impact: +6.2, category: 'finance', url: '#' },
        { date: '2025-09-15', title: 'iPhone 17 Pro mit KI-Features - starke Nachfrage', sentiment: 'positive', impact: +4.1, category: 'product', url: '#' }
    ],
    tesla: [
        { date: '2020-03-18', title: 'Tesla stoppt Produktion in Fremont', sentiment: 'negative', impact: -15.3, category: 'production', url: '#' },
        { date: '2020-08-31', title: 'Tesla Aktiensplit 5:1 - Rally geht weiter', sentiment: 'positive', impact: +12.6, category: 'market', url: '#' },
        { date: '2020-12-21', title: 'Tesla wird in S&P 500 aufgenommen', sentiment: 'positive', impact: +8.4, category: 'market', url: '#' },
        { date: '2022-04-14', title: 'Musk bietet fuer Twitter - Tesla faellt', sentiment: 'negative', impact: -9.2, category: 'management', url: '#' },
        { date: '2023-07-19', title: 'Tesla Gewinnmargen sinken durch Preiskampf', sentiment: 'negative', impact: -8.6, category: 'earnings', url: '#' },
        { date: '2024-04-23', title: 'Tesla kuendigt guenstiges Modell fuer 2025 an', sentiment: 'positive', impact: +12.1, category: 'product', url: '#' },
        { date: '2025-01-29', title: 'Tesla Robotaxi-Start in mehreren US-Staedten', sentiment: 'positive', impact: +15.3, category: 'product', url: '#' }
    ],
    microsoft: [
        { date: '2020-03-23', title: 'COVID-Crash trifft auch Microsoft', sentiment: 'negative', impact: -6.5, category: 'pandemic', url: '#' },
        { date: '2021-01-26', title: 'Microsoft Cloud-Umsatz waechst um 50%', sentiment: 'positive', impact: +5.8, category: 'earnings', url: '#' },
        { date: '2022-01-18', title: 'Microsoft kauft Activision Blizzard fuer $69 Mrd.', sentiment: 'positive', impact: +4.2, category: 'acquisition', url: '#' },
        { date: '2023-01-23', title: 'Microsoft investiert $10 Mrd. in OpenAI', sentiment: 'positive', impact: +8.9, category: 'tech', url: '#' },
        { date: '2024-07-19', title: 'CrowdStrike-Ausfall trifft Windows-Systeme weltweit', sentiment: 'negative', impact: -3.8, category: 'tech', url: '#' },
        { date: '2025-04-10', title: 'Copilot KI treibt Office-365 Umsatz auf Rekord', sentiment: 'positive', impact: +5.1, category: 'product', url: '#' }
    ]
};

// ---- Current News (overwritten by live data if available) ----
const CurrentNews = [
    { title: 'EZB erwaegt weitere Zinssenkung im Maerz', source: 'Reuters', time: 'vor 2 Stunden', sentiment: 'positive', score: 0.72, affectedStocks: ['dax', 'siemens', 'sap'], category: 'policy', url: '#' },
    { title: 'NVIDIA meldet Rekordumsatz - KI-Nachfrage ungebrochen', source: 'Bloomberg', time: 'vor 3 Stunden', sentiment: 'positive', score: 0.85, affectedStocks: ['nasdaq', 'microsoft', 'apple'], category: 'tech', url: '#' },
    { title: 'US-Arbeitsmarktdaten schwaecher als erwartet', source: 'CNBC', time: 'vor 4 Stunden', sentiment: 'negative', score: -0.45, affectedStocks: ['dowjones', 'sp500'], category: 'economy', url: '#' },
    { title: 'Tesla Robotaxi-Expansion nach Europa geplant', source: 'Handelsblatt', time: 'vor 5 Stunden', sentiment: 'positive', score: 0.68, affectedStocks: ['tesla', 'dax'], category: 'product', url: '#' },
    { title: 'Apple verhandelt KI-Partnerschaft mit Google', source: 'Wall Street Journal', time: 'vor 6 Stunden', sentiment: 'positive', score: 0.61, affectedStocks: ['apple', 'nasdaq'], category: 'tech', url: '#' },
    { title: 'Geopolitische Spannungen in Ostasien eskalieren', source: 'Financial Times', time: 'vor 7 Stunden', sentiment: 'negative', score: -0.58, affectedStocks: ['dax', 'dowjones', 'sp500'], category: 'geopolitics', url: '#' },
    { title: 'SAP Cloud-Transformation uebertrifft Analystenerwartungen', source: 'Boerse Frankfurt', time: 'vor 8 Stunden', sentiment: 'positive', score: 0.74, affectedStocks: ['sap', 'dax'], category: 'earnings', url: '#' },
    { title: 'Steigende Oelpreise belasten Industrieaktien', source: 'Reuters', time: 'vor 9 Stunden', sentiment: 'negative', score: -0.42, affectedStocks: ['dax', 'siemens', 'dowjones'], category: 'commodities', url: '#' },
    { title: 'Microsoft Azure waechst 35% - Cloud-Boom haelt an', source: 'TechCrunch', time: 'vor 10 Stunden', sentiment: 'positive', score: 0.79, affectedStocks: ['microsoft', 'nasdaq', 'sp500'], category: 'tech', url: '#' },
    { title: 'Siemens erhaelt Grossauftrag fuer Bahninfrastruktur', source: 'Manager Magazin', time: 'vor 11 Stunden', sentiment: 'positive', score: 0.55, affectedStocks: ['siemens', 'dax'], category: 'business', url: '#' },
    { title: 'Fed-Protokoll deutet auf vorsichtigere Zinspolitik hin', source: 'Bloomberg', time: 'vor 12 Stunden', sentiment: 'neutral', score: 0.1, affectedStocks: ['dowjones', 'sp500', 'nasdaq'], category: 'policy', url: '#' },
    { title: 'Chipindustrie: Neue Exportbeschraenkungen gegen China', source: 'Handelsblatt', time: 'vor 14 Stunden', sentiment: 'negative', score: -0.51, affectedStocks: ['nasdaq', 'apple', 'microsoft'], category: 'policy', url: '#' }
];

// ---- Historical Events (always static) ----
const HistoricalEvents = [
    {
        date: 'Maerz 2020',
        title: 'COVID-19 Pandemie - Globaler Boersencrash',
        description: 'Die WHO erklaert COVID-19 am 11. Maerz zur Pandemie. Lockdowns weltweit fuehren zu Panikverkaeufen. Der DAX verliert innerhalb von 30 Tagen fast 39%, der Dow Jones faellt um ueber 35%. Nachrichten ueber steigende Infektionszahlen und wirtschaftliche Stilllegungen treiben den Ausverkauf.',
        impact: -38.8,
        type: 'negative',
        affected: ['DAX', 'Dow Jones', 'S&P 500', 'NASDAQ'],
        sources: [
            { title: 'Reuters - Maerkte im freien Fall', url: 'https://www.reuters.com/markets/' },
            { title: 'Tagesschau - WHO erklaert Pandemie', url: 'https://www.tagesschau.de/wirtschaft/' },
            { title: 'Handelsblatt - Boersencrash 2020', url: 'https://www.handelsblatt.com/finanzen/' }
        ]
    },
    {
        date: 'November 2020',
        title: 'COVID-Erholung / Impfstoff-Rally',
        description: 'BioNTech und Pfizer melden am 9. November eine Impfstoff-Wirksamkeit von 95%. Die Nachricht loest eine der staerksten Rallys der Boersengeschichte aus. Reise-, Freizeit- und Bankaktien springen zweistellig nach oben, da Anleger auf ein Ende der Pandemie setzen.',
        impact: 15.4,
        type: 'positive',
        affected: ['DAX', 'Dow Jones', 'BioNTech', 'Lufthansa'],
        sources: [
            { title: 'Bloomberg - Vaccine Rally', url: 'https://www.bloomberg.com/markets/' },
            { title: 'FAZ - BioNTech Impfstoff-Durchbruch', url: 'https://www.faz.net/aktuell/finanzen/' },
            { title: 'Reuters - Markets surge on vaccine news', url: 'https://www.reuters.com/business/' }
        ]
    },
    {
        date: 'Januar 2021',
        title: 'GameStop Short Squeeze',
        description: 'Kleinanleger auf Reddit (r/WallStreetBets) koordinieren massive Kaeufe von GameStop-Aktien und treiben den Kurs um ueber 1.600% nach oben. Hedgefonds wie Melvin Capital erleiden Milliardenverluste. Die Ereignisse fuehren zu einer Debatte ueber Marktmanipulation und Trading-Apps wie Robinhood.',
        impact: 1600,
        type: 'positive',
        affected: ['GameStop', 'AMC', 'NASDAQ', 'Dow Jones'],
        sources: [
            { title: 'Wall Street Journal - GameStop Frenzy', url: 'https://www.wsj.com/finance/stocks/' },
            { title: 'Handelsblatt - Reddit vs. Wall Street', url: 'https://www.handelsblatt.com/finanzen/' },
            { title: 'CNBC - Robinhood halts GameStop trading', url: 'https://www.cnbc.com/markets/' }
        ]
    },
    {
        date: 'November 2021',
        title: 'Fed Zinswende Ankuendigung',
        description: 'Fed-Chef Jerome Powell signalisiert das Ende der ultralockeren Geldpolitik und kuendigt ein beschleunigtes Tapering der Anleihenkaeufe an. Die Maerkte reagieren nervoes, insbesondere hoch bewertete Wachstumsaktien geraten unter Druck. Der Beginn des Zinsanhebungszyklus zeichnet sich ab.',
        impact: -5.2,
        type: 'negative',
        affected: ['NASDAQ', 'S&P 500', 'Tech-Aktien'],
        sources: [
            { title: 'Reuters - Fed signals faster taper', url: 'https://www.reuters.com/business/finance/' },
            { title: 'Bloomberg - Powell pivots on inflation', url: 'https://www.bloomberg.com/markets/' },
            { title: 'FAZ - Fed leitet Zinswende ein', url: 'https://www.faz.net/aktuell/finanzen/' }
        ]
    },
    {
        date: 'Februar 2022',
        title: 'Ukraine Krieg Beginn',
        description: 'Am 24. Februar 2022 beginnt Russland die Invasion der Ukraine. Energiepreise explodieren, Gas- und Oelpreise erreichen Rekordstaende. Der DAX verliert ueber 8% in einer Woche, europaeische Maerkte sind besonders betroffen. Sanktionen gegen Russland verschaerfen die Energiekrise in Europa.',
        impact: -8.7,
        type: 'negative',
        affected: ['DAX', 'Euro Stoxx 50', 'Oelpreis', 'Gaspreis'],
        sources: [
            { title: 'Tagesschau - Russland greift Ukraine an', url: 'https://www.tagesschau.de/wirtschaft/' },
            { title: 'Handelsblatt - Energiekrise und Boersen', url: 'https://www.handelsblatt.com/finanzen/' },
            { title: 'Reuters - Markets plunge on Ukraine invasion', url: 'https://www.reuters.com/markets/' }
        ]
    },
    {
        date: '2022',
        title: 'Tech-Crash / NASDAQ Baerenmarkt',
        description: 'Steigende Zinsen, hohe Inflation und das Ende des Pandemie-Booms fuehren zum schlimmsten Tech-Ausverkauf seit der Dotcom-Blase. Der NASDAQ verliert ueber 33% im Jahresverlauf. Meta faellt um 65%, Netflix um 51%. Die Aera des billigen Geldes ist vorbei, Wachstumsaktien werden massiv abgestraft.',
        impact: -33.1,
        type: 'negative',
        affected: ['NASDAQ', 'Meta', 'Netflix', 'Tesla', 'Amazon'],
        sources: [
            { title: 'Bloomberg - Tech bear market deepens', url: 'https://www.bloomberg.com/technology/' },
            { title: 'CNBC - Worst year for tech since 2008', url: 'https://www.cnbc.com/technology/' },
            { title: 'Handelsblatt - Tech-Crash 2022', url: 'https://www.handelsblatt.com/technik/' }
        ]
    },
    {
        date: 'Maerz 2023',
        title: 'Credit Suisse Kollaps / Bankenkrise',
        description: 'Nach dem Zusammenbruch der Silicon Valley Bank (SVB) und der Signature Bank in den USA geraten auch europaeische Banken unter Druck. Die Credit Suisse, seit Jahren krisengeschuettelt, wird in einer Notfusion von der UBS uebernommen. Bankaktien weltweit stuerzen ab, Erinnerungen an 2008 werden wach.',
        impact: -6.8,
        type: 'negative',
        affected: ['Credit Suisse', 'UBS', 'DAX', 'Deutsche Bank', 'Dow Jones'],
        sources: [
            { title: 'Reuters - Credit Suisse rescued by UBS', url: 'https://www.reuters.com/business/finance/' },
            { title: 'FAZ - Bankenkrise 2023', url: 'https://www.faz.net/aktuell/finanzen/' },
            { title: 'Tagesschau - SVB-Kollaps erschuettert Maerkte', url: 'https://www.tagesschau.de/wirtschaft/' }
        ]
    },
    {
        date: '2023',
        title: 'KI-Rally / ChatGPT Hype',
        description: 'ChatGPT erreicht im Januar 100 Millionen Nutzer und loest einen beispiellosen KI-Investitionsboom aus. Microsoft investiert $10 Milliarden in OpenAI, Google stellt Bard vor. Tech-Aktien mit KI-Bezug steigen massiv. NVIDIA wird zum groessten Profiteur des KI-Booms.',
        impact: 240,
        type: 'positive',
        affected: ['NVIDIA', 'Microsoft', 'NASDAQ', 'Alphabet'],
        sources: [
            { title: 'Bloomberg - AI boom drives tech rally', url: 'https://www.bloomberg.com/technology/' },
            { title: 'Handelsblatt - KI-Revolution an der Boerse', url: 'https://www.handelsblatt.com/technik/' },
            { title: 'Reuters - Microsoft bets $10B on OpenAI', url: 'https://www.reuters.com/technology/' }
        ]
    },
    {
        date: 'Mai 2023',
        title: 'NVIDIA Rekord-Quartalszahlen',
        description: 'NVIDIA meldet fuer Q1 2024 einen Umsatzausblick von $11 Milliarden - 50% ueber den Analystenerwartungen. Die Aktie springt nachboerslich um 25% nach oben und treibt den gesamten Chipsektor mit. NVIDIA wird zum Symbol des KI-Booms und ueberschreitet spaeter die $1-Billionen-Marktkapitalisierung.',
        impact: 24.6,
        type: 'positive',
        affected: ['NVIDIA', 'NASDAQ', 'AMD', 'TSMC'],
        sources: [
            { title: 'CNBC - NVIDIA earnings shock Wall Street', url: 'https://www.cnbc.com/technology/' },
            { title: 'Bloomberg - NVIDIA joins $1 trillion club', url: 'https://www.bloomberg.com/markets/' },
            { title: 'Handelsblatt - NVIDIA und der KI-Goldrausch', url: 'https://www.handelsblatt.com/technik/' }
        ]
    },
    {
        date: 'Oktober 2023',
        title: 'Hamas-Israel Konflikt',
        description: 'Am 7. Oktober greift die Hamas Israel an, es folgt eine massive militaerische Eskalation. Oelpreise steigen auf Sorge vor einer Ausweitung des Konflikts auf den gesamten Nahen Osten. Ruestungsaktien steigen, waehrend Airline- und Touristikwerte fallen. Geopolitische Risikoaufschlaege belasten die Maerkte.',
        impact: -2.8,
        type: 'negative',
        affected: ['DAX', 'Oelpreis', 'Ruestungsaktien', 'Airlines'],
        sources: [
            { title: 'Tagesschau - Nahost-Krise eskaliert', url: 'https://www.tagesschau.de/wirtschaft/' },
            { title: 'Reuters - Oil surges on Middle East fears', url: 'https://www.reuters.com/markets/commodities/' },
            { title: 'FAZ - Boersen reagieren auf Nahost-Krieg', url: 'https://www.faz.net/aktuell/finanzen/' }
        ]
    },
    {
        date: 'Dezember 2023',
        title: 'Fed Zinspause Signal',
        description: 'Fed-Chef Powell signalisiert auf der Dezember-Sitzung das Ende des Zinsanhebungszyklus und stellt Zinssenkungen fuer 2024 in Aussicht. Die Maerkte reagieren euphorisch: S&P 500 und NASDAQ springen auf neue Allzeithochs. Anleihenrenditen fallen stark, was besonders Wachstumswerte befluegelten.',
        impact: 4.5,
        type: 'positive',
        affected: ['S&P 500', 'NASDAQ', 'Dow Jones', 'Anleihen'],
        sources: [
            { title: 'Bloomberg - Fed signals rate cuts ahead', url: 'https://www.bloomberg.com/markets/' },
            { title: 'Reuters - Wall Street surges on Fed pivot', url: 'https://www.reuters.com/markets/' },
            { title: 'Handelsblatt - Fed-Wende befluegelten Boersen', url: 'https://www.handelsblatt.com/finanzen/' }
        ]
    },
    {
        date: '2024',
        title: 'Magnificent 7 Rally',
        description: 'Die sieben groessten US-Tech-Aktien (Apple, Microsoft, Alphabet, Amazon, NVIDIA, Meta, Tesla) dominieren die Marktentwicklung. Allein diese sieben Werte treiben den S&P 500 auf neue Rekorde, waehrend der breite Markt zurueckbleibt. KI-Fantasie und starke Quartalszahlen sind die Haupttreiber.',
        impact: 35.2,
        type: 'positive',
        affected: ['Apple', 'Microsoft', 'NVIDIA', 'Meta', 'Amazon', 'S&P 500'],
        sources: [
            { title: 'Bloomberg - Magnificent Seven drive market', url: 'https://www.bloomberg.com/markets/' },
            { title: 'CNBC - Tech mega-caps hit new records', url: 'https://www.cnbc.com/technology/' },
            { title: 'FAZ - Die Macht der Magnificent Seven', url: 'https://www.faz.net/aktuell/finanzen/' }
        ]
    },
    {
        date: '2024',
        title: 'Geopolitische Spannungen / Taiwan',
        description: 'Wachsende Spannungen zwischen China und Taiwan sowie neue Militaermanoever im Suedchinesischen Meer verunsichern die Maerkte. Chipaktien wie TSMC und ASML reagieren besonders empfindlich, da Taiwan ueber 60% der weltweiten Halbleiterproduktion kontrolliert. Handelsrestriktionen gegen China verschaerfen die Lage.',
        impact: -4.3,
        type: 'negative',
        affected: ['TSMC', 'ASML', 'NASDAQ', 'DAX', 'Halbleiter-Sektor'],
        sources: [
            { title: 'Reuters - Taiwan tensions rattle chip stocks', url: 'https://www.reuters.com/technology/' },
            { title: 'Handelsblatt - Geopolitik belastet Chipbranche', url: 'https://www.handelsblatt.com/technik/' },
            { title: 'Bloomberg - China-Taiwan risk for markets', url: 'https://www.bloomberg.com/markets/' }
        ]
    },
    {
        date: 'Juni 2024',
        title: 'EZB erste Zinssenkung',
        description: 'Die Europaeische Zentralbank senkt erstmals seit 2019 den Leitzins um 25 Basispunkte auf 4,25%. Die Entscheidung kommt nach Monaten sinkender Inflation in der Eurozone. Europaeische Aktien reagieren positiv, besonders Immobilien- und Bankenwerte profitieren. Der DAX klettert auf ein neues Jahreshoch.',
        impact: 3.1,
        type: 'positive',
        affected: ['DAX', 'Euro Stoxx 50', 'Immobilienaktien', 'Bankenwerte'],
        sources: [
            { title: 'Tagesschau - EZB senkt Leitzins', url: 'https://www.tagesschau.de/wirtschaft/' },
            { title: 'Handelsblatt - Zinswende in Europa', url: 'https://www.handelsblatt.com/finanzen/' },
            { title: 'Reuters - ECB cuts rates for first time', url: 'https://www.reuters.com/business/finance/' }
        ]
    },
    {
        date: 'November 2024',
        title: 'Trump Wahlsieg - Markteffekte',
        description: 'Donald Trump gewinnt die US-Praesidentschaftswahl 2024. Die Maerkte reagieren gespalten: US-Aktien steigen auf Hoffnung auf Steuersenkungen und Deregulierung, waehrend europaeische und asiatische Maerkte auf moegliche Handelszölle und geopolitische Unsicherheit negativ reagieren. Der Dollar steigt stark an.',
        impact: 2.5,
        type: 'positive',
        affected: ['Dow Jones', 'S&P 500', 'Tesla', 'DAX', 'USD'],
        sources: [
            { title: 'Bloomberg - Trump win sparks market rally', url: 'https://www.bloomberg.com/markets/' },
            { title: 'Handelsblatt - Trump-Effekt an den Boersen', url: 'https://www.handelsblatt.com/finanzen/' },
            { title: 'Reuters - Wall Street surges after election', url: 'https://www.reuters.com/markets/' }
        ]
    }
];

// ---- Top Stocks (overwritten by live data if available) ----
const TopStocks = [
    { name: 'Apple', ticker: 'AAPL', price: '213,45', change: '+2,15%', changeType: 'positive', sentiment: 'positive', sentimentLabel: 'Bullish' },
    { name: 'Microsoft', ticker: 'MSFT', price: '425,80', change: '+1,43%', changeType: 'positive', sentiment: 'positive', sentimentLabel: 'Bullish' },
    { name: 'Tesla', ticker: 'TSLA', price: '248,67', change: '-2,34%', changeType: 'negative', sentiment: 'negative', sentimentLabel: 'Bearish' },
    { name: 'NVIDIA', ticker: 'NVDA', price: '892,30', change: '+3,87%', changeType: 'positive', sentiment: 'positive', sentimentLabel: 'Sehr Bullish' },
    { name: 'SAP', ticker: 'SAP', price: '196,35', change: '+1,89%', changeType: 'positive', sentiment: 'positive', sentimentLabel: 'Bullish' },
    { name: 'Siemens', ticker: 'SIE', price: '188,42', change: '+0,78%', changeType: 'positive', sentiment: 'neutral', sentimentLabel: 'Neutral' },
    { name: 'Amazon', ticker: 'AMZN', price: '198,12', change: '+1,12%', changeType: 'positive', sentiment: 'positive', sentimentLabel: 'Bullish' },
    { name: 'Alphabet', ticker: 'GOOGL', price: '175,88', change: '-0,56%', changeType: 'negative', sentiment: 'neutral', sentimentLabel: 'Neutral' }
];
