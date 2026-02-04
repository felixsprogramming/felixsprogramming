/* ========================================
   StockPulse - Main Application
   Navigation, rendering, and UI logic
   ======================================== */

document.addEventListener('DOMContentLoaded', function() {

    // ---- Navigation ----
    const navLinks = document.querySelectorAll('.nav-link');
    const sections = document.querySelectorAll('.section');
    const hamburger = document.getElementById('hamburger');
    const navLinksContainer = document.getElementById('nav-links');

    // Track initialized sections
    const initialized = {
        dashboard: false,
        correlation: false,
        predictions: false,
        history: false
    };

    function navigateTo(sectionId) {
        sections.forEach(s => s.classList.remove('active'));
        navLinks.forEach(l => l.classList.remove('active'));

        const target = document.getElementById(sectionId);
        if (target) {
            target.classList.add('active');
        }

        navLinks.forEach(l => {
            if (l.dataset.section === sectionId) l.classList.add('active');
        });

        // Close mobile menu
        if (navLinksContainer) navLinksContainer.classList.remove('open');

        // Initialize section if not yet done
        initSection(sectionId);
    }

    navLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            navigateTo(this.dataset.section);
        });
    });

    if (hamburger) {
        hamburger.addEventListener('click', function() {
            navLinksContainer.classList.toggle('open');
        });
    }

    // ---- Section Initialization ----
    function initSection(sectionId) {
        if (initialized[sectionId]) return;
        initialized[sectionId] = true;

        switch (sectionId) {
            case 'dashboard': initDashboard(); break;
            case 'correlation': initCorrelation(); break;
            case 'predictions': initPredictions(); break;
            case 'history': initHistory(); break;
        }
    }

    // ---- Dashboard ----
    function initDashboard() {
        // Sparklines
        ChartModule.createSparkline('dax-sparkline', StockData.dax.data, StockData.dax.change > 0);
        ChartModule.createSparkline('dow-sparkline', StockData.dowjones.data, StockData.dowjones.change > 0);
        ChartModule.createSparkline('sp500-sparkline', StockData.sp500.data, StockData.sp500.change > 0);
        ChartModule.createSparkline('nasdaq-sparkline', StockData.nasdaq.data, StockData.nasdaq.change > 0);

        // Main chart
        ChartModule.createMainChart('main-chart', 'dax', '1M');

        // Stock selector
        document.getElementById('stock-selector').addEventListener('change', function() {
            const activeRange = document.querySelector('.time-btn.active');
            ChartModule.createMainChart('main-chart', this.value, activeRange ? activeRange.dataset.range : '1M');
        });

        // Time range buttons
        document.querySelectorAll('.time-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                document.querySelectorAll('.time-btn').forEach(b => b.classList.remove('active'));
                this.classList.add('active');
                const stockSel = document.getElementById('stock-selector');
                ChartModule.createMainChart('main-chart', stockSel.value, this.dataset.range);
            });
        });

        // Stock table
        renderStockTable();
    }

    function renderStockTable() {
        const list = document.getElementById('stock-list');
        if (!list) return;

        list.innerHTML = TopStocks.map(stock => {
            return '<div class="stock-row">' +
                '<div class="stock-info">' +
                    '<span class="name">' + stock.name + '</span>' +
                    '<span class="ticker">' + stock.ticker + '</span>' +
                '</div>' +
                '<span class="stock-price">' + stock.price + '</span>' +
                '<span class="stock-change ' + stock.changeType + '">' + stock.change + '</span>' +
                '<span class="sentiment-badge ' + stock.sentiment + '">' + stock.sentimentLabel + '</span>' +
            '</div>';
        }).join('');
    }

    // ---- Correlation ----
    function initCorrelation() {
        ChartModule.createCorrelationChart('correlation-chart', 'dax');
        renderNewsEvents('dax');

        document.getElementById('correlation-stock-selector').addEventListener('change', function() {
            ChartModule.createCorrelationChart('correlation-chart', this.value);
            renderNewsEvents(this.value);
            updateCorrelationStats(this.value);
        });
    }

    function renderNewsEvents(stockKey) {
        const list = document.getElementById('news-events-list');
        if (!list) return;

        const events = NewsEvents[stockKey] || [];

        list.innerHTML = events.map((event, index) => {
            const impactStr = event.impact > 0
                ? '+' + event.impact + '%'
                : event.impact + '%';
            const impactClass = event.impact > 0 ? 'positive' : 'negative';

            return '<div class="news-event-item ' + event.sentiment + '">' +
                '<div class="news-event-date">' + (index + 1) + '. ' + formatDate(event.date) + '</div>' +
                '<div class="news-event-title">' + event.title + '</div>' +
                '<div class="news-event-impact ' + impactClass + '">Kurseffekt: ' + impactStr + '</div>' +
            '</div>';
        }).join('');
    }

    function updateCorrelationStats(stockKey) {
        const events = NewsEvents[stockKey] || [];
        const positive = events.filter(e => e.sentiment === 'positive');
        const negative = events.filter(e => e.sentiment === 'negative');

        const avgPositive = positive.length > 0
            ? (positive.reduce((sum, e) => sum + e.impact, 0) / positive.length).toFixed(1)
            : '0';
        const avgNegative = negative.length > 0
            ? (negative.reduce((sum, e) => sum + e.impact, 0) / negative.length).toFixed(1)
            : '0';

        const el1 = document.getElementById('positive-news-impact');
        const el2 = document.getElementById('negative-news-impact');
        if (el1) el1.textContent = '+' + avgPositive + '%';
        if (el2) el2.textContent = avgNegative + '%';
    }

    // ---- Predictions ----
    function initPredictions() {
        renderNewsFeed('all');
        renderPredictions();
        renderSentimentGauges();

        // News filter buttons
        document.querySelectorAll('.filter-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                this.classList.add('active');
                renderNewsFeed(this.dataset.filter);
            });
        });
    }

    function renderNewsFeed(filter) {
        const feed = document.getElementById('current-news-feed');
        if (!feed) return;

        let news = CurrentNews;
        if (filter !== 'all') {
            news = news.filter(n => n.sentiment === filter);
        }

        feed.innerHTML = news.map(item => {
            return '<div class="news-item" data-sentiment="' + item.sentiment + '">' +
                '<div class="news-item-header">' +
                    '<span class="news-source">' + item.source + '</span>' +
                    '<span class="news-time">' + item.time + '</span>' +
                '</div>' +
                '<div class="news-title">' + item.title + '</div>' +
                '<span class="news-sentiment-tag ' + item.sentiment + '">' +
                    sentimentLabel(item.sentiment) +
                '</span>' +
            '</div>';
        }).join('');
    }

    function renderPredictions() {
        const list = document.getElementById('predictions-list');
        if (!list) return;

        const predictions = PredictionEngine.generateAllPredictions();

        list.innerHTML = predictions.map(pred => {
            const arrow = pred.direction === 'up' ? '&#9650;'
                : pred.direction === 'down' ? '&#9660;'
                : '&#9654;';

            return '<div class="prediction-card">' +
                '<div class="prediction-header">' +
                    '<span class="prediction-stock">' + pred.stockName + '</span>' +
                    '<span class="prediction-direction ' + pred.direction + '">' +
                        arrow + ' ' + pred.predictedChange +
                    '</span>' +
                '</div>' +
                '<div class="prediction-reason">' + pred.reason + '</div>' +
                '<div class="prediction-confidence">' +
                    '<span class="confidence-value">' + pred.confidence + '%</span>' +
                    '<div class="confidence-bar">' +
                        '<div class="confidence-fill ' + pred.confidenceLevel + '" style="width: ' + pred.confidence + '%;"></div>' +
                    '</div>' +
                    '<span class="confidence-value">' + pred.timeframe + '</span>' +
                '</div>' +
            '</div>';
        }).join('');
    }

    function renderSentimentGauges() {
        const daxSentiment = PredictionEngine.getMarketSentiment('dax');
        const dowSentiment = PredictionEngine.getMarketSentiment('dow');
        const techSentiment = PredictionEngine.getMarketSentiment('tech');

        ChartModule.createSentimentGauge('sentiment-gauge-dax', daxSentiment);
        ChartModule.createSentimentGauge('sentiment-gauge-dow', dowSentiment);
        ChartModule.createSentimentGauge('sentiment-gauge-tech', techSentiment);
    }

    // ---- Historical Analysis ----
    function initHistory() {
        renderTimeline();
        initComparisonChart();
    }

    function renderTimeline() {
        const timeline = document.getElementById('historical-timeline');
        if (!timeline) return;

        timeline.innerHTML = HistoricalEvents.map(event => {
            return '<div class="timeline-item ' + event.type + '">' +
                '<div class="timeline-date">' + event.date + '</div>' +
                '<div class="timeline-title">' + event.title + '</div>' +
                '<div class="timeline-desc">' + event.description + '</div>' +
                '<span class="timeline-impact ' + event.type + '">' + event.impact + '</span>' +
            '</div>';
        }).join('');
    }

    function initComparisonChart() {
        updateComparisonChart();

        document.getElementById('compare-dax').addEventListener('change', updateComparisonChart);
        document.getElementById('compare-dow').addEventListener('change', updateComparisonChart);
        document.getElementById('compare-sp500').addEventListener('change', updateComparisonChart);
    }

    function updateComparisonChart() {
        const indices = [];
        if (document.getElementById('compare-dax').checked) indices.push('dax');
        if (document.getElementById('compare-dow').checked) indices.push('dowjones');
        if (document.getElementById('compare-sp500').checked) indices.push('sp500');

        if (indices.length > 0) {
            ChartModule.createComparisonChart('comparison-chart', indices);
        }
    }

    // ---- Utility Functions ----
    function formatDate(dateStr) {
        return new Date(dateStr).toLocaleDateString('de-DE', {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric'
        });
    }

    function sentimentLabel(sentiment) {
        switch (sentiment) {
            case 'positive': return 'Positiv';
            case 'negative': return 'Negativ';
            default: return 'Neutral';
        }
    }

    // ---- Index Card Click Handlers ----
    document.querySelectorAll('.index-card').forEach(card => {
        card.addEventListener('click', function() {
            const indexKey = this.dataset.index;
            const selector = document.getElementById('stock-selector');
            if (selector) {
                selector.value = indexKey;
                selector.dispatchEvent(new Event('change'));

                // Scroll to chart
                document.querySelector('.main-chart').scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        });
    });

    // ---- Initialize first section ----
    navigateTo('dashboard');

});
