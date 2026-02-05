/* ========================================
   BBF-Trading - Main Application
   Navigation, rendering, and UI logic
   ======================================== */

document.addEventListener('DOMContentLoaded', async function() {

    // ---- Load Live Data from Crawler ----
    const hasLiveData = await LiveDataLoader.load();
    if (hasLiveData) {
        LiveDataLoader.applyToStockData();
        LiveDataLoader.applyToNewsData();
        LiveDataLoader.applyAIPredictions();
        LiveDataLoader.applyCorrelations();
        LiveDataLoader.applyRecommendations();
        console.log('[BBF-Trading] Live crawler data applied successfully');

        // Show live indicator
        const brand = document.querySelector('.nav-brand');
        if (brand) {
            const badge = document.createElement('span');
            badge.className = 'live-badge';
            badge.textContent = 'LIVE';
            badge.style.cssText = 'background:#10b981;color:#fff;font-size:0.6rem;padding:2px 6px;border-radius:8px;margin-left:8px;font-weight:700;';
            brand.appendChild(badge);
        }
    }

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
        recommendations: false,
        history: false,
        crawler: false
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
            case 'recommendations': initRecommendations(); break;
            case 'history': initHistory(); break;
            case 'crawler': initCrawler(); break;
            case 'etf': initETF(); break;
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

        // Helper to refresh the main chart with current settings
        function refreshMainChart() {
            var stockSel = document.getElementById('stock-selector');
            var dateFrom = document.getElementById('main-date-from');
            var dateTo = document.getElementById('main-date-to');
            var activeRange = document.querySelector('.time-btn.active');
            var fromVal = dateFrom ? dateFrom.value : null;
            var toVal = dateTo ? dateTo.value : null;

            // If custom dates are set, use date range; otherwise use preset range
            if (fromVal || toVal) {
                ChartModule.createMainChart('main-chart', stockSel.value, null, fromVal, toVal);
            } else {
                ChartModule.createMainChart('main-chart', stockSel.value, activeRange ? activeRange.dataset.range : '1M');
            }
        }

        // Stock selector
        document.getElementById('stock-selector').addEventListener('change', refreshMainChart);

        // Time range buttons
        document.querySelectorAll('.time-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                document.querySelectorAll('.time-btn').forEach(b => b.classList.remove('active'));
                this.classList.add('active');
                // Clear custom date inputs when using preset range
                var dateFrom = document.getElementById('main-date-from');
                var dateTo = document.getElementById('main-date-to');
                if (dateFrom) dateFrom.value = '';
                if (dateTo) dateTo.value = '';
                refreshMainChart();
            });
        });

        // Date range inputs
        var mainDateFrom = document.getElementById('main-date-from');
        var mainDateTo = document.getElementById('main-date-to');
        if (mainDateFrom) {
            mainDateFrom.addEventListener('change', function() {
                // Clear active preset button when using custom date range
                document.querySelectorAll('.time-btn').forEach(b => b.classList.remove('active'));
                refreshMainChart();
            });
        }
        if (mainDateTo) {
            mainDateTo.addEventListener('change', function() {
                // Clear active preset button when using custom date range
                document.querySelectorAll('.time-btn').forEach(b => b.classList.remove('active'));
                refreshMainChart();
            });
        }

        // Stock table
        renderStockTable();
    }

    function renderStockTable() {
        const list = document.getElementById('stock-list');
        if (!list) return;

        list.innerHTML = TopStocks.map(stock => {
            return '<div class="stock-row stock-row-clickable" data-stock="' + stock.name + '" data-ticker="' + stock.ticker + '">' +
                '<div class="stock-info">' +
                    '<span class="name">' + stock.name + '</span>' +
                    '<span class="ticker">' + stock.ticker + '</span>' +
                '</div>' +
                '<span class="stock-price">' + stock.price + '</span>' +
                '<span class="stock-change ' + stock.changeType + '">' + stock.change + '</span>' +
                '<span class="sentiment-badge ' + stock.sentiment + '">' + stock.sentimentLabel + '</span>' +
            '</div>';
        }).join('');

        // Add click listeners to stock rows
        list.querySelectorAll('.stock-row-clickable').forEach(row => {
            row.addEventListener('click', function() {
                const stockName = this.dataset.stock;

                // Highlight the clicked row
                list.querySelectorAll('.stock-row-clickable').forEach(r => r.classList.remove('active'));
                this.classList.add('active');

                // Navigate to predictions section
                navigateTo('predictions');
            });
        });
    }

    // ---- Correlation ----
    function initCorrelation() {
        ChartModule.createCorrelationChart('correlation-chart', 'dax');
        renderNewsEvents('dax');
        updateCorrelationStats('dax');

        // Helper to refresh correlation chart with current settings
        function refreshCorrelationChart() {
            var stockSel = document.getElementById('correlation-stock-selector');
            var dateFrom = document.getElementById('correlation-date-from');
            var dateTo = document.getElementById('correlation-date-to');
            var fromVal = dateFrom ? dateFrom.value : null;
            var toVal = dateTo ? dateTo.value : null;
            ChartModule.createCorrelationChart('correlation-chart', stockSel.value, fromVal, toVal);
            renderNewsEvents(stockSel.value);
            updateCorrelationStats(stockSel.value);
        }

        document.getElementById('correlation-stock-selector').addEventListener('change', refreshCorrelationChart);

        // Date range inputs for correlation chart
        var corrDateFrom = document.getElementById('correlation-date-from');
        var corrDateTo = document.getElementById('correlation-date-to');
        if (corrDateFrom) {
            corrDateFrom.addEventListener('change', refreshCorrelationChart);
        }
        if (corrDateTo) {
            corrDateTo.addEventListener('change', refreshCorrelationChart);
        }

        // Render reverse correlation findings
        renderReverseCorrelations();
    }

    function renderNewsEvents(stockKey) {
        const list = document.getElementById('news-events-list');
        if (!list) return;

        var events = (NewsEvents[stockKey] || []).slice(); // Clone array

        // Sort events by date
        events.sort(function(a, b) {
            var dateA = new Date(a.date);
            var dateB = new Date(b.date);
            return newsEventsSortOrder === 'newest' ? dateB - dateA : dateA - dateB;
        });

        // Build sort bar HTML
        var sortBarHTML = '<div class="news-sort-bar">' +
            '<button class="sort-btn' + (newsEventsSortOrder === 'newest' ? ' active' : '') + '" data-sort="newest" data-target="news-events">Neueste zuerst</button>' +
            '<button class="sort-btn' + (newsEventsSortOrder === 'oldest' ? ' active' : '') + '" data-sort="oldest" data-target="news-events">Aelteste zuerst</button>' +
        '</div>';

        list.innerHTML = sortBarHTML + events.map((event, index) => {
            const impactStr = event.impact > 0
                ? '+' + event.impact + '%'
                : event.impact + '%';
            const impactClass = event.impact > 0 ? 'positive' : 'negative';

            return '<div class="news-event-item ' + event.sentiment + '">' +
                '<div class="news-event-date">' + (index + 1) + '. ' + formatDate(event.date) + '</div>' +
                '<div class="news-event-title">' + (event.url && event.url !== '#' && event.url !== '/' ? '<a href="' + event.url + '" target="_blank" rel="noopener">' + event.title + '</a>' : event.title) + '</div>' +
                '<div class="news-event-impact ' + impactClass + '">Kurseffekt: ' + impactStr + '</div>' +
            '</div>';
        }).join('');

        // Attach sort button handlers
        list.querySelectorAll('.sort-btn[data-target="news-events"]').forEach(function(btn) {
            btn.addEventListener('click', function() {
                newsEventsSortOrder = this.dataset.sort;
                var selector = document.getElementById('correlation-stock-selector');
                renderNewsEvents(selector ? selector.value : stockKey);
            });
        });
    }

    function updateCorrelationStats(stockKey) {
        var events = NewsEvents[stockKey] || [];
        if (events.length === 0) return;

        var positiveImpacts = [];
        var negativeImpacts = [];

        events.forEach(function(e) {
            if (e.impact) {
                var val = parseFloat(e.impact);
                if (!isNaN(val)) {
                    if (val > 0) positiveImpacts.push(val);
                    else negativeImpacts.push(val);
                }
            }
        });

        var avgPositive = positiveImpacts.length > 0
            ? (positiveImpacts.reduce(function(a, b) { return a + b; }, 0) / positiveImpacts.length) : 0;
        var avgNegative = negativeImpacts.length > 0
            ? (negativeImpacts.reduce(function(a, b) { return a + b; }, 0) / negativeImpacts.length) : 0;

        var el1 = document.getElementById('positive-news-impact');
        var el2 = document.getElementById('negative-news-impact');
        if (el1) el1.textContent = '+' + avgPositive.toFixed(1) + '%';
        if (el2) el2.textContent = avgNegative.toFixed(1) + '%';

        // Correlation score: % of events that have matching impact data
        var explained = events.filter(function(e) { return e.impact; }).length;
        var corrScore = Math.round((explained / events.length) * 100);
        var el3 = document.getElementById('correlation-score');
        if (el3) el3.textContent = corrScore + '%';

        // Reaction time based on event density
        var el4 = document.getElementById('reaction-time');
        if (el4) el4.textContent = events.length > 8 ? '1-3 Tage' : events.length > 4 ? '2-5 Tage' : '3-7 Tage';
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

    // Track sort state for news feeds
    var newsFeedSortOrder = 'newest';
    var newsEventsSortOrder = 'newest';

    function renderNewsFeed(filter) {
        const feed = document.getElementById('current-news-feed');
        if (!feed) return;

        let news = CurrentNews.slice(); // Clone array
        if (filter !== 'all') {
            news = news.filter(n => n.sentiment === filter);
        }

        // Sort by published date if available, otherwise by time string
        news.sort(function(a, b) {
            var dateA = a.published ? new Date(a.published) : parseTimeString(a.time);
            var dateB = b.published ? new Date(b.published) : parseTimeString(b.time);
            return newsFeedSortOrder === 'newest' ? dateB - dateA : dateA - dateB;
        });

        // Build sort bar HTML
        var sortBarHTML = '<div class="news-sort-bar">' +
            '<button class="sort-btn' + (newsFeedSortOrder === 'newest' ? ' active' : '') + '" data-sort="newest" data-target="news-feed">Neueste zuerst</button>' +
            '<button class="sort-btn' + (newsFeedSortOrder === 'oldest' ? ' active' : '') + '" data-sort="oldest" data-target="news-feed">Aelteste zuerst</button>' +
        '</div>';

        feed.innerHTML = sortBarHTML + news.map(item => {
            return '<div class="news-item" data-sentiment="' + item.sentiment + '">' +
                '<div class="news-item-header">' +
                    '<span class="news-source">' + item.source + '</span>' +
                    '<span class="news-time">' + item.time + '</span>' +
                '</div>' +
                '<div class="news-title">' + (item.url && item.url !== '#' && item.url !== '/' ? '<a href="' + item.url + '" target="_blank" rel="noopener">' + item.title + '</a>' : item.title) + '</div>' +
                '<span class="news-sentiment-tag ' + item.sentiment + '">' +
                    sentimentLabel(item.sentiment) +
                '</span>' +
            '</div>';
        }).join('');

        // Attach sort button handlers
        feed.querySelectorAll('.sort-btn[data-target="news-feed"]').forEach(function(btn) {
            btn.addEventListener('click', function() {
                newsFeedSortOrder = this.dataset.sort;
                var activeFilter = document.querySelector('.filter-btn.active');
                renderNewsFeed(activeFilter ? activeFilter.dataset.filter : 'all');
            });
        });
    }

    // Parse time strings like "vor 2 Stunden" to approximate dates
    function parseTimeString(timeStr) {
        var now = new Date();
        if (!timeStr) return now;
        var match = timeStr.match(/(\d+)/);
        var num = match ? parseInt(match[1], 10) : 0;
        if (timeStr.includes('Stunde')) {
            return new Date(now.getTime() - num * 60 * 60 * 1000);
        } else if (timeStr.includes('Minute')) {
            return new Date(now.getTime() - num * 60 * 1000);
        } else if (timeStr.includes('Tag')) {
            return new Date(now.getTime() - num * 24 * 60 * 60 * 1000);
        }
        return now;
    }

    function renderPredictions() {
        const list = document.getElementById('predictions-list');
        if (!list) return;

        // Use AI predictions if available, otherwise fall back to frontend engine
        let predictions;
        let isAI = false;

        if (AIPredictions.length > 0) {
            predictions = AIPredictions.map(pred => ({
                stockName: pred.stockName || pred.stock_key,
                direction: pred.direction || 'sideways',
                predictedChange: pred.predicted_change_pct
                    ? (pred.predicted_change_pct >= 0 ? '+' : '') + pred.predicted_change_pct.toFixed(1) + '%'
                    : '+/-0.0%',
                confidence: Math.round((pred.confidence || 0.5) * 100),
                confidenceLevel: (pred.confidence || 0.5) > 0.7 ? 'high' : (pred.confidence || 0.5) > 0.4 ? 'medium' : 'low',
                reason: pred.reason || pred.news_summary || 'KI-Analyse basierend auf technischen und News-Daten',
                timeframe: pred.timeframe || '7 Tage',
                topNewsSources: pred.topNewsSources || [],
                isAI: true
            }));
            isAI = true;
        } else {
            predictions = PredictionEngine.generateAllPredictions();
        }

        // Model info header
        let headerHTML = '';
        if (isAI && AIModelInfo.accuracy > 0) {
            headerHTML = '<div class="ai-model-info">' +
                '<span class="ai-badge">KI-Modell</span>' +
                '<span class="ai-accuracy">Genauigkeit: ' + (AIModelInfo.accuracy * 100).toFixed(1) + '%</span>' +
                '<span class="ai-samples">' + AIModelInfo.samples + ' Trainingsdaten</span>';
            if (AIModelInfo.dbStats && AIModelInfo.dbStats.total_prices) {
                headerHTML += '<span class="ai-db">DB: ' +
                    AIModelInfo.dbStats.total_prices.toLocaleString('de-DE') + ' Kursdaten, ' +
                    AIModelInfo.dbStats.total_articles.toLocaleString('de-DE') + ' Artikel</span>';
            }
            headerHTML += '</div>';
        }

        list.innerHTML = headerHTML + predictions.map(pred => {
            const arrow = pred.direction === 'up' ? '&#9650;'
                : pred.direction === 'down' ? '&#9660;'
                : '&#9654;';

            const aiTag = pred.isAI ? '<span class="ai-tag">KI</span>' : '';

            // Build news sources HTML with clickable links
            let sourcesHTML = '';
            if (pred.topNewsSources && pred.topNewsSources.length > 0) {
                sourcesHTML = '<div class="prediction-sources"><strong>Relevante Nachrichten:</strong><ul>';
                pred.topNewsSources.forEach(function(src) {
                    var sentimentClass = src.sentiment === 'positive' ? 'positive' :
                                        src.sentiment === 'negative' ? 'negative' : 'neutral';
                    var titleHTML = src.url && src.url !== '' && src.url !== '#'
                        ? '<a href="' + src.url + '" target="_blank" rel="noopener">' + src.title + '</a>'
                        : '<span>' + src.title + '</span>';
                    sourcesHTML += '<li class="' + sentimentClass + '">' + titleHTML + '</li>';
                });
                sourcesHTML += '</ul></div>';
            }

            return '<div class="prediction-card">' +
                '<div class="prediction-header">' +
                    '<span class="prediction-stock">' + pred.stockName + ' ' + aiTag + '</span>' +
                    '<span class="prediction-direction ' + pred.direction + '">' +
                        arrow + ' ' + pred.predictedChange +
                    '</span>' +
                '</div>' +
                '<div class="prediction-reason">' + pred.reason + '</div>' +
                sourcesHTML +
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
        var filter = document.getElementById('history-filter');
        if (filter) {
            filter.addEventListener('change', function() {
                renderTimeline(this.value);
            });
        }

        renderTimeline('all');
        initComparisonChart();
    }

    function renderTimeline(filterValue) {
        const timeline = document.getElementById('historical-timeline');
        if (!timeline) return;

        var events = HistoricalEvents;

        if (filterValue && filterValue !== 'all') {
            events = events.filter(function(e) {
                return e.affected && e.affected.some(function(a) {
                    return a.toLowerCase().includes(filterValue.toLowerCase());
                });
            });
        }

        if (events.length === 0) {
            timeline.innerHTML = '<div class="timeline-empty"><p>Keine Ereignisse fuer diesen Filter gefunden.</p></div>';
            return;
        }

        timeline.innerHTML = events.map(event => {
            // Format impact value
            const impactNum = typeof event.impact === 'number' ? event.impact : parseFloat(event.impact);
            const impactPrefix = impactNum >= 0 ? '+' : '';
            const impactStr = impactPrefix + impactNum.toLocaleString('de-DE', { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + '%';
            const impactClass = impactNum >= 0 ? 'positive' : 'negative';

            // Affected badges
            let affectedHTML = '';
            if (event.affected && event.affected.length > 0) {
                affectedHTML = '<div class="timeline-affected">' +
                    event.affected.map(function(a) {
                        return '<span class="badge">' + a + '</span>';
                    }).join('') +
                '</div>';
            }

            // Sources links
            let sourcesHTML = '';
            if (event.sources && event.sources.length > 0) {
                sourcesHTML = '<div class="timeline-sources">' +
                    '<span style="font-size:0.75rem;color:var(--text-muted)">Quellen:</span> ' +
                    event.sources.map(function(src) {
                        return '<a href="' + src.url + '" target="_blank" rel="noopener">' + src.title + '</a>';
                    }).join(' ') +
                '</div>';
            }

            return '<div class="timeline-item ' + event.type + '">' +
                '<div class="timeline-date">' + event.date + '</div>' +
                '<div class="timeline-content">' +
                    '<h4>' + event.title + '</h4>' +
                    '<p>' + event.description + '</p>' +
                    affectedHTML +
                    '<div class="timeline-impact ' + impactClass + '">' + impactStr + '</div>' +
                    sourcesHTML +
                '</div>' +
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

    // ---- Recommendations ----
    function initRecommendations() {
        const container = document.getElementById('recommendations-list');
        if (!container) return;

        // Render model info header
        const modelInfoEl = document.getElementById('rec-model-info');
        if (modelInfoEl && AIModelInfo.accuracy > 0) {
            let modelHTML = '<div class="ai-model-info">' +
                '<span class="ai-badge">KI-Modell</span>' +
                '<span class="ai-accuracy">Genauigkeit: ' + (AIModelInfo.accuracy * 100).toFixed(1) + '%</span>' +
                '<span class="ai-samples">' + AIModelInfo.samples + ' Trainingsdaten</span>';
            if (AIModelInfo.dbStats && AIModelInfo.dbStats.total_prices) {
                modelHTML += '<span class="ai-db">DB: ' +
                    AIModelInfo.dbStats.total_prices.toLocaleString('de-DE') + ' Kursdaten, ' +
                    AIModelInfo.dbStats.total_articles.toLocaleString('de-DE') + ' Artikel</span>';
            }
            modelHTML += '</div>';
            modelInfoEl.innerHTML = modelHTML;
        }

        // Check if recommendations are available
        if (Recommendations.length === 0) {
            container.innerHTML = '<div class="empty-state">' +
                '<p>Noch keine Empfehlungen verf\u00fcgbar. Das KI-Modell generiert Empfehlungen nach dem ersten Crawling-Durchlauf.</p>' +
                '</div>';
            return;
        }

        // Render recommendation cards (up to 20)
        const maxCards = Math.min(Recommendations.length, 20);
        let html = '';

        for (let i = 0; i < maxCards; i++) {
            const rec = Recommendations[i];

            // Direction arrow and color class
            const isUp = rec.direction === 'up';
            const isDown = rec.direction === 'down';
            const arrow = isUp ? '&#9650;' : isDown ? '&#9660;' : '&#9654;';
            const changeClass = isUp ? 'positive' : isDown ? 'negative' : 'neutral';
            const changePrefix = rec.predicted_change_pct >= 0 ? '+' : '';
            const changePct = changePrefix + rec.predicted_change_pct.toFixed(1) + '%';

            // Confidence bar
            const confidencePct = Math.round((rec.confidence || 0) * 100);
            const confidenceLevel = confidencePct > 70 ? 'high' : confidencePct > 40 ? 'medium' : 'low';

            // Sources list
            let sourcesHTML = '';
            if (rec.sources && rec.sources.length > 0) {
                sourcesHTML = '<div class="rec-sources"><strong>Quellen:</strong><ul>';
                rec.sources.forEach(function(src) {
                    const sentimentDot = src.sentiment === 'positive' ? 'green'
                        : src.sentiment === 'negative' ? 'red'
                        : 'gray';
                    const titleHTML = src.url
                        ? '<a href="' + src.url + '" target="_blank" rel="noopener">' + (src.title || 'Quelle') + '</a>'
                        : '<span>' + (src.title || 'Quelle') + '</span>';
                    const dateHTML = src.date ? ' <span class="rec-source-date">(' + src.date + ')</span>' : '';
                    sourcesHTML += '<li>' +
                        '<span class="sentiment-dot" style="background:' + sentimentDot + ';display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px;"></span>' +
                        titleHTML + dateHTML +
                        '</li>';
                });
                sourcesHTML += '</ul></div>';
            }

            // Timestamp
            const timestampHTML = rec.timestamp
                ? '<div class="rec-timestamp">' + rec.timestamp + '</div>'
                : '';

            html += '<div class="recommendation-card">' +
                '<div class="rec-header">' +
                    '<div class="rec-stock-info">' +
                        '<span class="rec-stock-name">' + rec.stock_name + '</span>' +
                        '<span class="rec-ticker">' + rec.ticker + '</span>' +
                        '<span class="ai-tag">KI</span>' +
                    '</div>' +
                    '<span class="rec-change ' + changeClass + '">' + arrow + ' ' + changePct + '</span>' +
                '</div>' +
                '<div class="rec-confidence">' +
                    '<span class="confidence-label">Konfidenz: ' + confidencePct + '%</span>' +
                    '<div class="confidence-bar">' +
                        '<div class="confidence-fill ' + confidenceLevel + '" style="width:' + confidencePct + '%;"></div>' +
                    '</div>' +
                '</div>' +
                '<div class="rec-reasoning">' + (rec.reasoning || '') + '</div>' +
                sourcesHTML +
                timestampHTML +
            '</div>';
        }

        container.innerHTML = html;
    }

    // ---- Reverse Correlations ----
    function renderReverseCorrelations() {
        if (ReverseCorrelations.length === 0) return;

        var container = document.getElementById('news-events-list');
        if (!container) return;

        // Sort by absolute change (strongest movements first)
        var sorted = ReverseCorrelations.slice().sort(function(a, b) {
            return Math.abs(b.change_pct) - Math.abs(a.change_pct);
        }).slice(0, 20);

        var html = '<div class="reverse-corr-header">' +
            '<h4>KI-Reverse-Analyse: Signifikante Kursbewegungen</h4>' +
            '<span class="ai-tag">KI</span>' +
            '<span style="color:var(--text-muted);font-size:0.8rem;margin-left:8px;">' +
            CorrelationStats.explained_count + ' von ' + CorrelationStats.total_movements +
            ' Bewegungen erklaert (' + Math.round(CorrelationStats.overall_strength * 100) + '% Korrelation)</span>' +
        '</div>';

        sorted.forEach(function(corr) {
            var isNeg = corr.change_pct < 0;
            var changeClass = isNeg ? 'negative' : 'positive';
            var arrow = isNeg ? '&#9660;' : '&#9650;';
            var dateFormatted = corr.movement_date || '';

            html += '<div class="news-event-item reverse-corr-item">' +
                '<div class="news-event-date">' + dateFormatted + '</div>' +
                '<div class="news-event-content">' +
                    '<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">' +
                        '<strong>' + (corr.stock_key || '').toUpperCase() + '</strong>' +
                        '<span class="' + changeClass + '" style="font-weight:700;">' +
                        arrow + ' ' + (corr.change_pct > 0 ? '+' : '') + corr.change_pct.toFixed(2) + '%</span>' +
                        '<span class="badge-' + (corr.explained ? 'success' : 'danger') + '" style="font-size:0.7rem;padding:1px 6px;border-radius:4px;">' +
                        (corr.explained ? 'Erklaert' : 'Unerklaert') + '</span>' +
                    '</div>';

            if (corr.matched_news && corr.matched_news.length > 0) {
                html += '<ul style="list-style:none;padding:0;margin:4px 0 0 0;">';
                corr.matched_news.slice(0, 3).forEach(function(news) {
                    var sentClass = news.sentiment === 'positive' ? 'positive' :
                                   news.sentiment === 'negative' ? 'negative' : 'neutral';
                    var titleHTML = news.url
                        ? '<a href="' + news.url + '" target="_blank" rel="noopener">' + (news.title || 'Quelle') + '</a>'
                        : (news.title || 'Quelle');
                    html += '<li style="font-size:0.82rem;color:var(--text-secondary);margin-bottom:3px;">' +
                        '<span class="rec-source-sentiment ' + sentClass + '"></span> ' +
                        titleHTML +
                        ' <span style="color:var(--text-muted);">(' + (news.source || '') + ')</span>' +
                    '</li>';
                });
                html += '</ul>';
            }

            html += '</div></div>';
        });

        container.insertAdjacentHTML('beforeend', html);
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
                // Update active state on cards
                document.querySelectorAll('.index-card').forEach(c => c.classList.remove('active'));
                this.classList.add('active');

                selector.value = indexKey;
                selector.dispatchEvent(new Event('change'));

                // Scroll to chart
                document.querySelector('.main-chart').scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        });
    });

    // ---- Crawler Section ----
    function initCrawler() {
        loadSavedStocks();

        document.getElementById('crawler-start').addEventListener('click', async function() {
            var ticker = document.getElementById('crawler-ticker').value.trim();
            var name = document.getElementById('crawler-name').value.trim();
            var keywords = document.getElementById('crawler-keywords').value.trim();

            if (!ticker) {
                alert('Bitte Ticker-Symbol eingeben');
                return;
            }

            var statusEl = document.getElementById('crawler-status');
            var resultsEl = document.getElementById('crawler-results');
            statusEl.style.display = 'flex';
            resultsEl.style.display = 'none';

            try {
                var res = await fetch('/api/crawler/custom', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ticker: ticker, name: name, keywords: keywords})
                });
                var data = await res.json();

                statusEl.style.display = 'none';
                resultsEl.style.display = 'block';

                if (data.success) {
                    document.getElementById('crawler-result-content').innerHTML =
                        '<div class="crawler-success">' +
                        '<p><strong>' + data.name + ' (' + data.ticker + ')</strong> erfolgreich gecrawlt!</p>' +
                        '<ul>' +
                        '<li>Kursdaten: ' + data.price_records + ' Eintraege</li>' +
                        '<li>News gefunden: ' + data.news_found + '</li>' +
                        '<li>Korrelationen: ' + data.correlations + '</li>' +
                        '</ul></div>';
                    loadSavedStocks();
                } else {
                    document.getElementById('crawler-result-content').innerHTML =
                        '<div class="crawler-error">Fehler: ' + (data.error || 'Unbekannt') + '</div>';
                }
            } catch(e) {
                statusEl.style.display = 'none';
                resultsEl.style.display = 'block';
                document.getElementById('crawler-result-content').innerHTML =
                    '<div class="crawler-error">Netzwerkfehler: ' + e.message + '</div>';
            }
        });
    }

    async function loadSavedStocks() {
        try {
            var res = await fetch('/api/crawler/stocks');
            var data = await res.json();
            var container = document.getElementById('crawler-saved-stocks');

            if (!data.stocks || data.stocks.length === 0) {
                container.innerHTML = '<p class="empty-state">Keine Aktien gespeichert</p>';
                return;
            }

            container.innerHTML = data.stocks.map(function(s) {
                return '<div class="saved-stock-card">' +
                    '<div class="saved-stock-name">' + s.name + '</div>' +
                    '<div class="saved-stock-ticker">' + s.ticker + '</div>' +
                    '<div class="saved-stock-updated">Aktualisiert: ' + (s.last_updated || 'Nie') + '</div>' +
                '</div>';
            }).join('');
        } catch(e) {
            console.error('Failed to load stocks:', e);
        }
    }

    // ---- ETF & Fonds Analysis ----
    function initETF() {
        document.getElementById('etf-select').addEventListener('change', function() {
            var etfKey = this.value;
            if (!etfKey) {
                document.getElementById('etf-details').style.display = 'none';
                return;
            }
            loadETFData(etfKey);
        });
    }

    function loadETFData(etfKey) {
        var etf = ETFData[etfKey];
        if (!etf) return;

        document.getElementById('etf-details').style.display = 'block';
        document.getElementById('etf-name').textContent = etf.name + ' (' + etf.ticker + ')';
        document.getElementById('etf-holdings').textContent = etf.holdings.length;

        // Calculate weighted sentiment from holdings' news
        var weightedSentiment = calculateWeightedSentiment(etf.holdings);
        document.getElementById('etf-sentiment').textContent =
            (weightedSentiment > 0 ? '+' : '') + weightedSentiment.toFixed(1) + '%';
        document.getElementById('etf-sentiment').className =
            'etf-stat-value ' + (weightedSentiment > 0 ? 'positive' : weightedSentiment < 0 ? 'negative' : 'neutral');

        // Render holdings and news impact
        renderETFHoldings(etf.holdings);
        renderETFNewsImpact(etf.holdings);
    }

    function calculateWeightedSentiment(holdings) {
        var totalWeight = 0;
        var weightedSum = 0;

        holdings.forEach(function(h) {
            var sentiment = getStockSentiment(h.stock);
            weightedSum += sentiment * h.weight;
            totalWeight += h.weight;
        });

        return totalWeight > 0 ? weightedSum / totalWeight : 0;
    }

    function getStockSentiment(ticker) {
        // Check predictions first
        var pred = AIPredictions.find(function(p) {
            return p.ticker === ticker || p.stock === ticker || p.stock_key === ticker.toLowerCase();
        });
        if (pred && pred.news_sentiment_avg !== undefined) return pred.news_sentiment_avg * 100;

        // Fallback to news sentiment
        var news = CurrentNews.filter(function(n) {
            return n.affected && n.affected.some(function(a) {
                return a.toUpperCase() === ticker.toUpperCase();
            });
        });
        if (news.length === 0) return 0;

        var sum = news.reduce(function(acc, n) {
            return acc + (n.sentiment === 'positive' ? 1 : n.sentiment === 'negative' ? -1 : 0);
        }, 0);
        return (sum / news.length) * 30; // Scale to reasonable %
    }

    function renderETFHoldings(holdings) {
        var container = document.getElementById('etf-holdings-list');
        var newsCount = 0;

        var html = holdings.map(function(h) {
            var sentiment = getStockSentiment(h.stock);
            var sentClass = sentiment > 0 ? 'positive' : sentiment < 0 ? 'negative' : 'neutral';
            return '<div class="holding-item">' +
                '<div class="holding-info">' +
                    '<span class="holding-name">' + h.name + '</span>' +
                    '<span class="holding-ticker">' + h.stock + '</span>' +
                '</div>' +
                '<div class="holding-weight">' + h.weight.toFixed(1) + '%</div>' +
                '<div class="holding-sentiment ' + sentClass + '">' +
                    (sentiment > 0 ? '+' : '') + sentiment.toFixed(1) + '%' +
                '</div>' +
            '</div>';
        }).join('');

        container.innerHTML = html;
    }

    function renderETFNewsImpact(holdings) {
        var relevantNews = [];
        holdings.forEach(function(h) {
            CurrentNews.forEach(function(n) {
                var isRelevant = n.affected && n.affected.some(function(a) {
                    return a.toUpperCase() === h.stock.toUpperCase();
                });
                if (isRelevant) {
                    relevantNews.push({
                        news: n,
                        holding: h,
                        weightedImpact: (n.sentiment === 'positive' ? 1 : n.sentiment === 'negative' ? -1 : 0) * h.weight
                    });
                }
            });
        });

        var container = document.getElementById('etf-news-impact');
        document.getElementById('etf-news-count').textContent = relevantNews.length;

        if (relevantNews.length === 0) {
            container.innerHTML = '<p class="empty-state">Keine relevanten News fuer die Holdings gefunden</p>';
            return;
        }

        relevantNews.sort(function(a, b) { return Math.abs(b.weightedImpact) - Math.abs(a.weightedImpact); });

        container.innerHTML = relevantNews.slice(0, 10).map(function(item) {
            var sentClass = item.news.sentiment === 'positive' ? 'positive' :
                            item.news.sentiment === 'negative' ? 'negative' : 'neutral';
            var titleHTML = item.news.url && item.news.url !== '#'
                ? '<a href="' + item.news.url + '" target="_blank" rel="noopener">' + item.news.title + '</a>'
                : item.news.title;
            return '<div class="news-impact-item ' + sentClass + '">' +
                '<div class="news-impact-holding">' + item.holding.name + ' (' + item.holding.weight + '% Gewichtung)</div>' +
                '<div class="news-impact-title">' + titleHTML + '</div>' +
                '<div class="news-impact-value">' +
                    (item.weightedImpact > 0 ? '+' : '') + item.weightedImpact.toFixed(2) + '% ETF-Einfluss' +
                '</div>' +
            '</div>';
        }).join('');
    }

    // ---- Initialize first section ----
    navigateTo('dashboard');

});
