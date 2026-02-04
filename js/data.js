/* ========================================
   StockPulse - Stock & News Data
   Historical data and news events
   ======================================== */

// Helper: Generate realistic stock data from a start value
function generateStockData(startDate, endDate, startValue, volatility, trend) {
    const data = [];
    const start = new Date(startDate);
    const end = new Date(endDate);
    let value = startValue;

    for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
        if (d.getDay() === 0 || d.getDay() === 6) continue; // Skip weekends
        const change = (Math.random() - 0.48 + trend) * volatility * value / 100;
        value = Math.max(value + change, value * 0.7);
        data.push({
            date: new Date(d).toISOString().split('T')[0],
            value: Math.round(value * 100) / 100
        });
    }
    return data;
}

// Historical stock data (simulated realistic data)
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
        name: 'Apple',
        ticker: 'AAPL',
        currency: 'USD',
        currentValue: 213.45,
        change: 2.15,
        data: generateStockData('2019-01-01', '2026-01-31', 38, 2.5, 0.025)
    },
    microsoft: {
        name: 'Microsoft',
        ticker: 'MSFT',
        currency: 'USD',
        currentValue: 425.80,
        change: 1.43,
        data: generateStockData('2019-01-01', '2026-01-31', 100, 2.0, 0.022)
    },
    tesla: {
        name: 'Tesla',
        ticker: 'TSLA',
        currency: 'USD',
        currentValue: 248.67,
        change: -2.34,
        data: generateStockData('2019-01-01', '2026-01-31', 22, 4.5, 0.03)
    },
    siemens: {
        name: 'Siemens',
        ticker: 'SIE',
        currency: 'EUR',
        currentValue: 188.42,
        change: 0.78,
        data: generateStockData('2019-01-01', '2026-01-31', 95, 1.8, 0.012)
    },
    sap: {
        name: 'SAP',
        ticker: 'SAP',
        currency: 'EUR',
        currentValue: 196.35,
        change: 1.89,
        data: generateStockData('2019-01-01', '2026-01-31', 90, 2.0, 0.015)
    }
};

// Apply COVID crash and recovery pattern to data
function applyCrashPattern(data, crashStartDate, crashEndDate, dropPercent, recoveryMonths) {
    const crashStart = new Date(crashStartDate);
    const crashEnd = new Date(crashEndDate);
    const recoveryEnd = new Date(crashEnd);
    recoveryEnd.setMonth(recoveryEnd.getMonth() + recoveryMonths);

    let preCrashValue = null;

    data.forEach((point, index) => {
        const d = new Date(point.date);
        if (d >= crashStart && d <= crashEnd) {
            if (!preCrashValue && index > 0) {
                preCrashValue = data[index - 1].value;
            }
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

// Apply crash patterns to all stocks
Object.keys(StockData).forEach(key => {
    // COVID-19 crash (Feb-Mar 2020)
    applyCrashPattern(StockData[key].data, '2020-02-20', '2020-03-23', 0.35, 10);
});

// News events with stock correlations
const NewsEvents = {
    dax: [
        { date: '2020-03-11', title: 'WHO erklaert COVID-19 zur Pandemie', sentiment: 'negative', impact: -12.2, category: 'pandemic' },
        { date: '2020-03-23', title: 'Deutschland geht in den ersten Lockdown', sentiment: 'negative', impact: -5.8, category: 'policy' },
        { date: '2020-11-09', title: 'BioNTech/Pfizer Impfstoff zeigt 95% Wirksamkeit', sentiment: 'positive', impact: +8.4, category: 'pharma' },
        { date: '2021-06-15', title: 'EZB haelt an lockerer Geldpolitik fest', sentiment: 'positive', impact: +2.1, category: 'policy' },
        { date: '2022-02-24', title: 'Russland beginnt Invasion der Ukraine', sentiment: 'negative', impact: -8.7, category: 'geopolitics' },
        { date: '2022-07-21', title: 'EZB erhoeht Zinsen erstmals seit 11 Jahren', sentiment: 'negative', impact: -3.2, category: 'policy' },
        { date: '2023-01-30', title: 'ChatGPT erreicht 100 Mio. Nutzer - KI-Boom beginnt', sentiment: 'positive', impact: +4.5, category: 'tech' },
        { date: '2023-10-07', title: 'Hamas-Angriff auf Israel - Nahost-Krise eskaliert', sentiment: 'negative', impact: -2.8, category: 'geopolitics' },
        { date: '2024-03-15', title: 'EZB signalisiert erste Zinssenkung', sentiment: 'positive', impact: +3.1, category: 'policy' },
        { date: '2024-11-05', title: 'US-Wahl: Unsicherheit belastet Maerkte', sentiment: 'negative', impact: -1.9, category: 'politics' },
        { date: '2025-01-20', title: 'Deutsche Wirtschaft zeigt Erholungszeichen', sentiment: 'positive', impact: +2.3, category: 'economy' },
        { date: '2025-06-15', title: 'Neues EU-Konjunkturpaket beschlossen', sentiment: 'positive', impact: +3.5, category: 'policy' },
        { date: '2025-09-10', title: 'DAX erreicht neues Allzeithoch', sentiment: 'positive', impact: +1.8, category: 'market' }
    ],
    dowjones: [
        { date: '2020-03-11', title: 'WHO declares COVID-19 global pandemic', sentiment: 'negative', impact: -10.5, category: 'pandemic' },
        { date: '2020-03-23', title: 'Fed announces unlimited QE program', sentiment: 'positive', impact: +11.4, category: 'policy' },
        { date: '2020-11-09', title: 'Biden wins US election, vaccine news', sentiment: 'positive', impact: +5.2, category: 'politics' },
        { date: '2021-01-27', title: 'GameStop Short Squeeze schockt Wall Street', sentiment: 'negative', impact: -2.1, category: 'market' },
        { date: '2022-01-26', title: 'Fed kuendigt aggressive Zinsplaene an', sentiment: 'negative', impact: -6.3, category: 'policy' },
        { date: '2022-06-13', title: 'US-Inflation erreicht 9.1% - 40-Jahres-Hoch', sentiment: 'negative', impact: -4.8, category: 'economy' },
        { date: '2023-03-10', title: 'Silicon Valley Bank Kollaps', sentiment: 'negative', impact: -3.5, category: 'finance' },
        { date: '2023-05-24', title: 'NVIDIA Q1 Zahlen uebertreffen alle Erwartungen', sentiment: 'positive', impact: +4.2, category: 'tech' },
        { date: '2024-01-15', title: 'KI-Investments treiben Maerkte auf Rekordhoehen', sentiment: 'positive', impact: +3.8, category: 'tech' },
        { date: '2024-08-05', title: 'Japan Carry-Trade Crash - globale Panik', sentiment: 'negative', impact: -5.1, category: 'market' },
        { date: '2025-03-20', title: 'Fed senkt Zinsen auf 3.5%', sentiment: 'positive', impact: +2.9, category: 'policy' },
        { date: '2025-07-22', title: 'Tech-Sektor Korrektur nach Gewinnwarnungen', sentiment: 'negative', impact: -3.2, category: 'tech' }
    ],
    apple: [
        { date: '2020-03-23', title: 'COVID-Crash: Apple Stores weltweit geschlossen', sentiment: 'negative', impact: -8.2, category: 'pandemic' },
        { date: '2020-07-30', title: 'Apple meldet Rekordquartal trotz Pandemie', sentiment: 'positive', impact: +10.5, category: 'earnings' },
        { date: '2021-01-27', title: 'iPhone 12 treibt Umsatz auf Allzeithoch', sentiment: 'positive', impact: +5.3, category: 'product' },
        { date: '2022-01-03', title: 'Apple erreicht $3 Billionen Marktkapitalisierung', sentiment: 'positive', impact: +3.1, category: 'market' },
        { date: '2023-06-05', title: 'Apple Vision Pro vorgestellt', sentiment: 'positive', impact: +7.8, category: 'product' },
        { date: '2024-01-11', title: 'Apple ueberholt Microsoft als wertvollstes Unternehmen', sentiment: 'positive', impact: +2.4, category: 'market' },
        { date: '2024-05-02', title: 'Apple Aktienrueckkauf: $110 Milliarden', sentiment: 'positive', impact: +6.2, category: 'finance' },
        { date: '2025-09-15', title: 'iPhone 17 Pro mit KI-Features - starke Nachfrage', sentiment: 'positive', impact: +4.1, category: 'product' }
    ],
    tesla: [
        { date: '2020-03-18', title: 'Tesla stoppt Produktion in Fremont', sentiment: 'negative', impact: -15.3, category: 'production' },
        { date: '2020-08-31', title: 'Tesla Aktiensplit 5:1 - Rally geht weiter', sentiment: 'positive', impact: +12.6, category: 'market' },
        { date: '2020-12-21', title: 'Tesla wird in S&P 500 aufgenommen', sentiment: 'positive', impact: +8.4, category: 'market' },
        { date: '2021-10-25', title: 'Hertz bestellt 100.000 Teslas', sentiment: 'positive', impact: +12.7, category: 'business' },
        { date: '2022-04-14', title: 'Musk bietet fuer Twitter - Tesla faellt', sentiment: 'negative', impact: -9.2, category: 'management' },
        { date: '2022-12-22', title: 'Musk verkauft weitere Tesla-Aktien', sentiment: 'negative', impact: -11.4, category: 'management' },
        { date: '2023-07-19', title: 'Tesla Gewinnmargen sinken durch Preiskampf', sentiment: 'negative', impact: -8.6, category: 'earnings' },
        { date: '2024-04-23', title: 'Tesla kuendigt guenstiges Modell fuer 2025 an', sentiment: 'positive', impact: +12.1, category: 'product' },
        { date: '2025-01-29', title: 'Tesla Robotaxi-Start in mehreren US-Staedten', sentiment: 'positive', impact: +15.3, category: 'product' }
    ],
    microsoft: [
        { date: '2020-03-23', title: 'COVID-Crash trifft auch Microsoft', sentiment: 'negative', impact: -6.5, category: 'pandemic' },
        { date: '2021-01-26', title: 'Microsoft Cloud-Umsatz waechst um 50%', sentiment: 'positive', impact: +5.8, category: 'earnings' },
        { date: '2022-01-18', title: 'Microsoft kauft Activision Blizzard fuer $69 Mrd.', sentiment: 'positive', impact: +4.2, category: 'acquisition' },
        { date: '2023-01-23', title: 'Microsoft investiert $10 Mrd. in OpenAI', sentiment: 'positive', impact: +8.9, category: 'tech' },
        { date: '2023-02-07', title: 'Bing AI mit ChatGPT Integration vorgestellt', sentiment: 'positive', impact: +4.3, category: 'product' },
        { date: '2024-01-12', title: 'Microsoft ueberholt Apple als wertvollstes Unternehmen', sentiment: 'positive', impact: +3.7, category: 'market' },
        { date: '2024-07-19', title: 'CrowdStrike-Ausfall trifft Windows-Systeme weltweit', sentiment: 'negative', impact: -3.8, category: 'tech' },
        { date: '2025-04-10', title: 'Copilot KI treibt Office-365 Umsatz auf Rekord', sentiment: 'positive', impact: +5.1, category: 'product' }
    ]
};

// Current news for predictions
const CurrentNews = [
    {
        title: 'EZB erwaegt weitere Zinssenkung im Maerz',
        source: 'Reuters',
        time: 'vor 2 Stunden',
        sentiment: 'positive',
        score: 0.72,
        affectedStocks: ['dax', 'siemens', 'sap'],
        category: 'policy'
    },
    {
        title: 'NVIDIA meldet Rekordumsatz - KI-Nachfrage ungebrochen',
        source: 'Bloomberg',
        time: 'vor 3 Stunden',
        sentiment: 'positive',
        score: 0.85,
        affectedStocks: ['nasdaq', 'microsoft', 'apple'],
        category: 'tech'
    },
    {
        title: 'US-Arbeitsmarktdaten schwaecher als erwartet',
        source: 'CNBC',
        time: 'vor 4 Stunden',
        sentiment: 'negative',
        score: -0.45,
        affectedStocks: ['dowjones', 'sp500'],
        category: 'economy'
    },
    {
        title: 'Tesla Robotaxi-Expansion nach Europa geplant',
        source: 'Handelsblatt',
        time: 'vor 5 Stunden',
        sentiment: 'positive',
        score: 0.68,
        affectedStocks: ['tesla', 'dax'],
        category: 'product'
    },
    {
        title: 'Apple verhandelt KI-Partnerschaft mit Google',
        source: 'Wall Street Journal',
        time: 'vor 6 Stunden',
        sentiment: 'positive',
        score: 0.61,
        affectedStocks: ['apple', 'nasdaq'],
        category: 'tech'
    },
    {
        title: 'Geopolitische Spannungen in Ostasien eskalieren',
        source: 'Financial Times',
        time: 'vor 7 Stunden',
        sentiment: 'negative',
        score: -0.58,
        affectedStocks: ['dax', 'dowjones', 'sp500'],
        category: 'geopolitics'
    },
    {
        title: 'SAP Cloud-Transformation uebertrifft Analystenerwartungen',
        source: 'Boerse Frankfurt',
        time: 'vor 8 Stunden',
        sentiment: 'positive',
        score: 0.74,
        affectedStocks: ['sap', 'dax'],
        category: 'earnings'
    },
    {
        title: 'Steigende Oelpreise belasten Industrieaktien',
        source: 'Reuters',
        time: 'vor 9 Stunden',
        sentiment: 'negative',
        score: -0.42,
        affectedStocks: ['dax', 'siemens', 'dowjones'],
        category: 'commodities'
    },
    {
        title: 'Microsoft Azure waechst 35% - Cloud-Boom haelt an',
        source: 'TechCrunch',
        time: 'vor 10 Stunden',
        sentiment: 'positive',
        score: 0.79,
        affectedStocks: ['microsoft', 'nasdaq', 'sp500'],
        category: 'tech'
    },
    {
        title: 'Siemens erhaelt Grossauftrag fuer Bahninfrastruktur',
        source: 'Manager Magazin',
        time: 'vor 11 Stunden',
        sentiment: 'positive',
        score: 0.55,
        affectedStocks: ['siemens', 'dax'],
        category: 'business'
    },
    {
        title: 'Fed-Protokoll deutet auf vorsichtigere Zinspolitik hin',
        source: 'Bloomberg',
        time: 'vor 12 Stunden',
        sentiment: 'neutral',
        score: 0.1,
        affectedStocks: ['dowjones', 'sp500', 'nasdaq'],
        category: 'policy'
    },
    {
        title: 'Chipindustrie: Neue Exportbeschraenkungen gegen China',
        source: 'Handelsblatt',
        time: 'vor 14 Stunden',
        sentiment: 'negative',
        score: -0.51,
        affectedStocks: ['nasdaq', 'apple', 'microsoft'],
        category: 'policy'
    }
];

// Historical events for timeline
const HistoricalEvents = [
    {
        date: 'Maerz 2020',
        title: 'COVID-19 Pandemie - Globaler Boersencrash',
        description: 'Die WHO erklaert COVID-19 zur Pandemie. Innerhalb von Wochen verlieren die globalen Boersen 30-40% ihres Wertes. Der DAX faellt von 13.800 auf 8.400 Punkte.',
        impact: '-38,8% (DAX in 30 Tagen)',
        type: 'negative'
    },
    {
        date: 'November 2020',
        title: 'BioNTech/Pfizer Impfstoff - Markterholung',
        description: 'Die Nachricht ueber den wirksamen Impfstoff loest eine massive Rally aus. Vor allem Reise-, Freizeit- und Bankaktien profitieren stark.',
        impact: '+15,4% (DAX in 30 Tagen)',
        type: 'positive'
    },
    {
        date: 'Januar 2021',
        title: 'GameStop Short Squeeze',
        description: 'Reddit-Kleinanleger treiben GameStop-Aktien um ueber 1.600% nach oben und zwingen Hedgefonds zu Milliardenverluste.',
        impact: '+1.600% (GME in 2 Wochen)',
        type: 'positive'
    },
    {
        date: 'Februar 2022',
        title: 'Russland-Ukraine Krieg',
        description: 'Der Einmarsch Russlands in die Ukraine fuehrt zu einem Energiepreisschock und einer Neuordnung der globalen Maerkte. Europaeische Aktien besonders betroffen.',
        impact: '-8,7% (DAX in 1 Woche)',
        type: 'negative'
    },
    {
        date: 'Januar 2023',
        title: 'ChatGPT und der KI-Boom',
        description: 'Der Erfolg von ChatGPT loest einen beispiellosen KI-Investitionsboom aus. Tech-Aktien steigen massiv, NVIDIA wird zum Star der Boerse.',
        impact: '+240% (NVIDIA in 12 Monaten)',
        type: 'positive'
    },
    {
        date: 'Maerz 2023',
        title: 'Silicon Valley Bank Kollaps',
        description: 'Die SVB kollabiert nach einem Bank-Run. Kurzfristige Panik erfasst den Bankensektor, wird aber durch schnelles Eingreifen der Regulierer eingedaemmt.',
        impact: '-3,5% (Dow Jones in 1 Woche)',
        type: 'negative'
    },
    {
        date: 'August 2024',
        title: 'Japan Carry-Trade Crash',
        description: 'Die ueberraschende Zinsanpassung der Bank of Japan fuehrt zu einer Aufloesung massiver Carry-Trades und einem globalen Flash-Crash.',
        impact: '-12,4% (Nikkei an 1 Tag)',
        type: 'negative'
    },
    {
        date: 'Januar 2025',
        title: 'KI-Integration im Mainstream',
        description: 'Grosse Unternehmen berichten ueber massive Produktivitaetssteigerungen durch KI-Tools. Der Tech-Sektor erreicht neue Hoechststaende.',
        impact: '+18% (NASDAQ in 3 Monaten)',
        type: 'positive'
    }
];

// Top stocks for the dashboard table
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
