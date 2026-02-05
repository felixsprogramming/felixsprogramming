/* ========================================
   BBF-Trading - Chart Module
   Handles all chart rendering
   ======================================== */

const ChartModule = {
    instances: {},
    defaultColors: {
        primary: '#3b82f6',
        primaryLight: 'rgba(59, 130, 246, 0.1)',
        success: '#10b981',
        successLight: 'rgba(16, 185, 129, 0.1)',
        danger: '#ef4444',
        dangerLight: 'rgba(239, 68, 68, 0.1)',
        purple: '#8b5cf6',
        purpleLight: 'rgba(139, 92, 246, 0.1)',
        warning: '#f59e0b',
        gray: '#64748b'
    },

    // Destroy existing chart before creating new one
    destroyChart(id) {
        if (this.instances[id]) {
            this.instances[id].destroy();
            delete this.instances[id];
        }
    },

    // Create sparkline chart for index cards
    createSparkline(canvasId, data, isPositive) {
        this.destroyChart(canvasId);
        const ctx = document.getElementById(canvasId);
        if (!ctx) return;

        const last30 = data.slice(-30);
        const color = isPositive ? this.defaultColors.success : this.defaultColors.danger;
        const colorLight = isPositive ? this.defaultColors.successLight : this.defaultColors.dangerLight;

        this.instances[canvasId] = new Chart(ctx, {
            type: 'line',
            data: {
                labels: last30.map(d => d.date),
                datasets: [{
                    data: last30.map(d => d.value),
                    borderColor: color,
                    backgroundColor: colorLight,
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 0,
                    pointHoverRadius: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false }, tooltip: { enabled: false } },
                scales: {
                    x: { display: false },
                    y: { display: false }
                },
                interaction: { mode: 'none' }
            }
        });
    },

    // Create main stock chart
    createMainChart(canvasId, stockKey, range, dateFrom, dateTo) {
        this.destroyChart(canvasId);
        const ctx = document.getElementById(canvasId);
        if (!ctx) return;

        const stock = StockData[stockKey];
        if (!stock) return;

        let data;
        // If custom date range is provided, use that instead of preset range
        if (dateFrom || dateTo) {
            data = this.filterDataByDateRange(stock.data, dateFrom, dateTo);
        } else {
            data = this.filterDataByRange(stock.data, range);
        }
        const isPositive = data.length >= 2 && data[data.length - 1].value >= data[0].value;
        const color = isPositive ? this.defaultColors.success : this.defaultColors.danger;
        const colorLight = isPositive ? this.defaultColors.successLight : this.defaultColors.dangerLight;

        this.instances[canvasId] = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.map(d => d.date),
                datasets: [{
                    label: stock.name,
                    data: data.map(d => d.value),
                    borderColor: color,
                    backgroundColor: colorLight,
                    borderWidth: 2,
                    fill: true,
                    tension: 0.3,
                    pointRadius: 0,
                    pointHoverRadius: 5,
                    pointHoverBackgroundColor: color,
                    pointHoverBorderColor: '#fff',
                    pointHoverBorderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: 'rgba(15, 23, 42, 0.95)',
                        titleColor: '#f1f5f9',
                        bodyColor: '#94a3b8',
                        borderColor: '#334155',
                        borderWidth: 1,
                        padding: 12,
                        displayColors: false,
                        callbacks: {
                            title: function(items) {
                                return new Date(items[0].label).toLocaleDateString('de-DE', {
                                    day: '2-digit', month: 'long', year: 'numeric'
                                });
                            },
                            label: function(item) {
                                const currency = stock.currency === 'EUR' ? ' EUR' : ' USD';
                                return stock.name + ': ' + item.parsed.y.toLocaleString('de-DE', {
                                    minimumFractionDigits: 2
                                }) + currency;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        type: 'time',
                        time: {
                            unit: this.getTimeUnit(range),
                            displayFormats: {
                                day: 'dd.MM',
                                week: 'dd.MM',
                                month: 'MMM yy',
                                year: 'yyyy'
                            }
                        },
                        grid: { color: 'rgba(51, 65, 85, 0.3)', drawBorder: false },
                        ticks: { color: '#64748b', maxTicksLimit: 10 }
                    },
                    y: {
                        grid: { color: 'rgba(51, 65, 85, 0.3)', drawBorder: false },
                        ticks: {
                            color: '#64748b',
                            callback: function(value) {
                                return value.toLocaleString('de-DE');
                            }
                        }
                    }
                }
            }
        });
    },

    // Create or get the news tooltip element
    getNewsTooltip() {
        let tooltip = document.getElementById('news-annotation-tooltip');
        if (!tooltip) {
            tooltip = document.createElement('div');
            tooltip.id = 'news-annotation-tooltip';
            tooltip.style.cssText = 'position:fixed;z-index:9999;background:rgba(15,23,42,0.98);border:1px solid #334155;border-radius:8px;padding:12px 16px;pointer-events:none;display:none;max-width:320px;box-shadow:0 10px 25px rgba(0,0,0,0.4);';
            document.body.appendChild(tooltip);
        }
        return tooltip;
    },

    // Show news tooltip at position
    showNewsTooltip(event, x, y) {
        const tooltip = this.getNewsTooltip();
        const sentimentLabel = event.sentiment === 'positive' ? 'Positiv' : event.sentiment === 'negative' ? 'Negativ' : 'Neutral';
        const sentimentColor = event.sentiment === 'positive' ? '#10b981' : event.sentiment === 'negative' ? '#ef4444' : '#6b7280';
        const impactStr = event.impact > 0 ? '+' + event.impact + '%' : event.impact + '%';
        const impactColor = event.impact > 0 ? '#10b981' : '#ef4444';
        const dateStr = new Date(event.date).toLocaleDateString('de-DE', { day: '2-digit', month: 'long', year: 'numeric' });

        tooltip.innerHTML = '<div style="margin-bottom:8px;font-weight:700;color:#f1f5f9;font-size:0.95rem;line-height:1.4;">' + event.title + '</div>' +
            '<div style="display:flex;flex-wrap:wrap;gap:12px;font-size:0.8rem;">' +
                '<div><span style="color:#64748b;">Datum:</span> <span style="color:#94a3b8;">' + dateStr + '</span></div>' +
                '<div><span style="color:#64748b;">Sentiment:</span> <span style="color:' + sentimentColor + ';font-weight:600;">' + sentimentLabel + '</span></div>' +
                '<div><span style="color:#64748b;">Kurseffekt:</span> <span style="color:' + impactColor + ';font-weight:600;">' + impactStr + '</span></div>' +
            '</div>';

        tooltip.style.display = 'block';
        tooltip.style.left = Math.min(x + 15, window.innerWidth - tooltip.offsetWidth - 20) + 'px';
        tooltip.style.top = Math.min(y + 15, window.innerHeight - tooltip.offsetHeight - 20) + 'px';
    },

    // Hide news tooltip
    hideNewsTooltip() {
        const tooltip = this.getNewsTooltip();
        tooltip.style.display = 'none';
    },

    // Create correlation chart with news annotations
    createCorrelationChart(canvasId, stockKey, dateFrom, dateTo) {
        this.destroyChart(canvasId);
        const ctx = document.getElementById(canvasId);
        if (!ctx) return;

        const stock = StockData[stockKey];
        const events = NewsEvents[stockKey] || [];
        if (!stock) return;

        let data = stock.data.slice(-365); // Last year of data

        // Apply date range filter if provided
        if (dateFrom || dateTo) {
            data = data.filter(d => {
                const date = new Date(d.date);
                if (dateFrom && date < new Date(dateFrom)) return false;
                if (dateTo && date > new Date(dateTo)) return false;
                return true;
            });
        }

        const color = this.defaultColors.primary;
        const self = this;

        // Build annotations from news events
        const annotations = {};
        events.forEach((event, i) => {
            const eventDate = new Date(event.date);
            const dataPoint = data.find(d => d.date === event.date);
            if (!dataPoint) return;

            annotations['line' + i] = {
                type: 'line',
                xMin: event.date,
                xMax: event.date,
                borderColor: event.sentiment === 'positive'
                    ? 'rgba(16, 185, 129, 0.6)'
                    : 'rgba(239, 68, 68, 0.6)',
                borderWidth: 2,
                borderDash: [4, 4],
                label: {
                    display: true,
                    content: (i + 1).toString(),
                    position: 'start',
                    backgroundColor: event.sentiment === 'positive' ? '#10b981' : '#ef4444',
                    color: '#fff',
                    font: { size: 10, weight: 'bold' },
                    padding: 4,
                    borderRadius: 10
                },
                enter: function(context, e) {
                    self.showNewsTooltip(event, e.native.clientX, e.native.clientY);
                },
                leave: function() {
                    self.hideNewsTooltip();
                }
            };
        });

        this.instances[canvasId] = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.map(d => d.date),
                datasets: [{
                    label: stock.name,
                    data: data.map(d => d.value),
                    borderColor: color,
                    backgroundColor: 'rgba(59, 130, 246, 0.08)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.3,
                    pointRadius: 0,
                    pointHoverRadius: 5,
                    pointHoverBackgroundColor: color
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: { display: false },
                    annotation: { annotations: annotations },
                    tooltip: {
                        backgroundColor: 'rgba(15, 23, 42, 0.95)',
                        titleColor: '#f1f5f9',
                        bodyColor: '#94a3b8',
                        borderColor: '#334155',
                        borderWidth: 1,
                        padding: 12,
                        displayColors: false,
                        callbacks: {
                            title: function(items) {
                                return new Date(items[0].label).toLocaleDateString('de-DE', {
                                    day: '2-digit', month: 'long', year: 'numeric'
                                });
                            },
                            label: function(item) {
                                return stock.name + ': ' + item.parsed.y.toLocaleString('de-DE', {
                                    minimumFractionDigits: 2
                                });
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        type: 'time',
                        time: { unit: 'month', displayFormats: { month: 'MMM yy' } },
                        grid: { color: 'rgba(51, 65, 85, 0.3)', drawBorder: false },
                        ticks: { color: '#64748b' }
                    },
                    y: {
                        grid: { color: 'rgba(51, 65, 85, 0.3)', drawBorder: false },
                        ticks: {
                            color: '#64748b',
                            callback: function(value) {
                                return value.toLocaleString('de-DE');
                            }
                        }
                    }
                }
            }
        });
    },

    // Create comparison chart
    createComparisonChart(canvasId, indices) {
        this.destroyChart(canvasId);
        const ctx = document.getElementById(canvasId);
        if (!ctx) return;

        const colors = [this.defaultColors.primary, this.defaultColors.success, this.defaultColors.purple];
        const datasets = [];

        indices.forEach((key, i) => {
            const stock = StockData[key];
            if (!stock) return;

            // Normalize to percentage change from start
            const data = stock.data;
            const startVal = data[0].value;
            const normalizedData = data.map(d => ({
                date: d.date,
                value: ((d.value - startVal) / startVal * 100)
            }));

            datasets.push({
                label: stock.name,
                data: normalizedData.map(d => d.value),
                borderColor: colors[i],
                backgroundColor: 'transparent',
                borderWidth: 2,
                tension: 0.3,
                pointRadius: 0,
                pointHoverRadius: 4
            });
        });

        if (datasets.length === 0) return;

        const labels = StockData[indices[0]].data.map(d => d.date);

        this.instances[canvasId] = new Chart(ctx, {
            type: 'line',
            data: { labels: labels, datasets: datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: {
                        display: true,
                        labels: { color: '#94a3b8', usePointStyle: true, padding: 20 }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(15, 23, 42, 0.95)',
                        titleColor: '#f1f5f9',
                        bodyColor: '#94a3b8',
                        borderColor: '#334155',
                        borderWidth: 1,
                        padding: 12,
                        callbacks: {
                            title: function(items) {
                                return new Date(items[0].label).toLocaleDateString('de-DE', {
                                    day: '2-digit', month: 'long', year: 'numeric'
                                });
                            },
                            label: function(item) {
                                const sign = item.parsed.y >= 0 ? '+' : '';
                                return item.dataset.label + ': ' + sign + item.parsed.y.toFixed(1) + '%';
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        type: 'time',
                        time: { unit: 'quarter', displayFormats: { quarter: 'MMM yy' } },
                        grid: { color: 'rgba(51, 65, 85, 0.3)', drawBorder: false },
                        ticks: { color: '#64748b' }
                    },
                    y: {
                        grid: { color: 'rgba(51, 65, 85, 0.3)', drawBorder: false },
                        ticks: {
                            color: '#64748b',
                            callback: function(value) {
                                return (value >= 0 ? '+' : '') + value + '%';
                            }
                        }
                    }
                }
            }
        });
    },

    // Create sentiment gauge (half-doughnut)
    createSentimentGauge(canvasId, value, label) {
        this.destroyChart(canvasId);
        const ctx = document.getElementById(canvasId);
        if (!ctx) return;

        // value: -100 to +100 -> 0 to 100 on gauge
        const normalizedValue = (value + 100) / 2;
        const remaining = 100 - normalizedValue;

        let gaugeColor;
        if (value > 30) gaugeColor = '#10b981';
        else if (value > 0) gaugeColor = '#34d399';
        else if (value > -30) gaugeColor = '#f59e0b';
        else gaugeColor = '#ef4444';

        this.instances[canvasId] = new Chart(ctx, {
            type: 'doughnut',
            data: {
                datasets: [{
                    data: [normalizedValue, remaining, 100],
                    backgroundColor: [gaugeColor, 'rgba(51, 65, 85, 0.3)', 'transparent'],
                    borderWidth: 0,
                    circumference: 180,
                    rotation: 270
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '75%',
                plugins: {
                    legend: { display: false },
                    tooltip: { enabled: false }
                }
            },
            plugins: [{
                id: 'gaugeText',
                afterDraw: function(chart) {
                    const { ctx, chartArea } = chart;
                    const centerX = (chartArea.left + chartArea.right) / 2;
                    const centerY = chartArea.bottom - 10;

                    ctx.save();
                    ctx.fillStyle = '#f1f5f9';
                    ctx.font = 'bold 22px Inter, sans-serif';
                    ctx.textAlign = 'center';
                    ctx.textBaseline = 'middle';
                    ctx.fillText((value > 0 ? '+' : '') + value, centerX, centerY - 15);

                    ctx.fillStyle = '#64748b';
                    ctx.font = '12px Inter, sans-serif';
                    ctx.fillText(value > 20 ? 'Bullish' : value > -20 ? 'Neutral' : 'Bearish', centerX, centerY + 8);
                    ctx.restore();
                }
            }]
        });
    },

    // Filter data by time range
    filterDataByRange(data, range) {
        const now = new Date(data[data.length - 1].date);
        let cutoff;

        switch (range) {
            case '1M': cutoff = new Date(now); cutoff.setMonth(cutoff.getMonth() - 1); break;
            case '3M': cutoff = new Date(now); cutoff.setMonth(cutoff.getMonth() - 3); break;
            case '6M': cutoff = new Date(now); cutoff.setMonth(cutoff.getMonth() - 6); break;
            case '1Y': cutoff = new Date(now); cutoff.setFullYear(cutoff.getFullYear() - 1); break;
            case '5Y': cutoff = new Date(now); cutoff.setFullYear(cutoff.getFullYear() - 5); break;
            default: cutoff = new Date(now); cutoff.setMonth(cutoff.getMonth() - 1);
        }

        return data.filter(d => new Date(d.date) >= cutoff);
    },

    // Filter data by custom date range
    filterDataByDateRange(data, dateFrom, dateTo) {
        return data.filter(d => {
            const date = new Date(d.date);
            if (dateFrom && date < new Date(dateFrom)) return false;
            if (dateTo && date > new Date(dateTo)) return false;
            return true;
        });
    },

    // Get appropriate time unit for range
    getTimeUnit(range) {
        switch (range) {
            case '1M': return 'day';
            case '3M': return 'week';
            case '6M': return 'month';
            case '1Y': return 'month';
            case '5Y': return 'year';
            default: return 'day';
        }
    }
};
