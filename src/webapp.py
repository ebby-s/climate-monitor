from flask import Flask, render_template_string, jsonify

from src.models import get_recent_readings, get_rollups, get_trends, get_total_count, get_prev3day_profile, get_daily_stats
from src.config import RECENT_LIMIT

app = Flask(__name__)

HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Climate Monitor</title>
    <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
    <style>
        :root {
            --bg: #020617;
            --panel: #111827;
            --panel2: #1f2937;
            --border: #334155;
            --text: #e5e7eb;
            --muted: #94a3b8;
            --red: #ef4444;
            --blue: #3b82f6;
            --orange: #f59e0b;
            --cyan: #06b6d4;
            --green: #22c55e;
            --pink: #ec4899;
            --teal: #14b8a6;
            --teal: #14b8a6;
            --purple: #a855f7;
            --yellow: #eab308;
        }
        * { box-sizing: border-box; }
        body {
            margin: 0;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(180deg, #020617 0%, #0f172a 100%);
            color: var(--text);
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 24px;
        }
        h1 {
            margin: 0 0 6px 0;
            font-size: 28px;
        }
        .subtitle {
            color: var(--muted);
            margin-bottom: 20px;
            font-size: 14px;
        }
        .status-dot {
            display: inline-block;
            width: 10px; height: 10px;
            background: var(--green);
            border-radius: 50%;
            margin-right: 8px;
            box-shadow: 0 0 8px var(--green);
        }

        .cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
            gap: 12px;
            margin-bottom: 24px;
        }
        .card {
            background: rgba(17, 24, 39, 0.95);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 16px;
        }
        .card h3 {
            margin: 0 0 8px 0;
            font-size: 12px;
            color: var(--muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .value {
            font-size: 24px;
            font-weight: 700;
        }

        .tabs {
            display: flex;
            gap: 4px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        .tab-btn {
            padding: 10px 20px;
            border: 1px solid var(--border);
            background: var(--panel2);
            color: var(--text);
            border-radius: 10px 10px 0 0;
            cursor: pointer;
            font-size: 14px;
            border-bottom: none;
            transition: background 0.2s;
        }
        .tab-btn.active {
            background: var(--panel);
            border-color: var(--border);
            font-weight: 600;
        }
        .tab-btn:hover {
            filter: brightness(1.1);
        }
        .tab-content {
            display: none;
        }
        .tab-content.active {
            display: block;
        }

        .chart-box {
            background: rgba(17, 24, 39, 0.95);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 18px;
            margin-bottom: 16px;
        }
        .chart-header {
            margin-bottom: 8px;
        }
        .chart-header h2 {
            margin: 0;
            font-size: 16px;
        }
        .chart-subtitle {
            color: var(--muted);
            font-size: 12px;
        }
        .plot {
            width: 100%;
            height: 360px;
        }

        .actions {
            margin-top: 20px;
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
        }
        button {
            padding: 10px 16px;
            border: 1px solid var(--border);
            background: var(--panel2);
            color: var(--text);
            border-radius: 10px;
            cursor: pointer;
            font-size: 13px;
        }
        button:hover { filter: brightness(1.1); }
        .note {
            margin-top: 12px;
            color: var(--muted);
            font-size: 13px;
        }
    </style>
</head>
<body>
<div class="container">
    <h1>Climate Monitor</h1>
    <div class="subtitle">
        <span class="status-dot"></span>
        SHT-41 &middot; SGP41 &middot; VEML 7700 &middot; Recording every minute
    </div>

    <div class="cards">
        <div class="card">
            <h3>Temperature</h3>
            <div class="value" id="latestTemp">--</div>
        </div>
        <div class="card">
            <h3>Humidity</h3>
            <div class="value" id="latestHum">--</div>
        </div>
        <div class="card">
            <h3>VOC Index</h3>
            <div class="value" id="latestVoc">--</div>
        </div>
        <div class="card">
            <h3>NOx Index</h3>
            <div class="value" id="latestNox">--</div>
        </div>
        <div class="card">
            <h3>Light</h3>
            <div class="value" id="latestLight">--</div>
        </div>
        <div class="card">
            <h3>Total Points</h3>
            <div class="value" id="pointCount">0</div>
        </div>
    </div>

    <div class="tabs">
        <button class="tab-btn active" onclick="switchTab('tab-th')">Temp &amp; Humidity</button>
        <button class="tab-btn" onclick="switchTab('tab-aq')">Air Quality</button>
        <button class="tab-btn" onclick="switchTab('tab-light')">Ambient Light</button>
    </div>

    <div id="tab-th" class="tab-content active">
        <div class="chart-box">
            <div class="chart-header">
                <h2>Temperature &mdash; Last 24 Hours</h2>
                <div class="chart-subtitle">All 1-minute readings with 3-day average overlay</div>
            </div>
            <div id="tempRawPlot" class="plot"></div>
        </div>
        <div class="chart-box">
            <div class="chart-header">
                <h2>Temperature &mdash; 30-Minute Averages by Day</h2>
                <div class="chart-subtitle">One line per calendar day</div>
            </div>
            <div id="tempAvgPlot" class="plot"></div>
        </div>
        <div class="chart-box">
            <div class="chart-header">
                <h2>Temperature &mdash; Daily Distribution</h2>
                <div class="chart-subtitle">Per-day min, quartiles, max, and mean</div>
            </div>
            <div id="tempDailyPlot" class="plot"></div>
        </div>
        <div class="chart-box">
            <div class="chart-header">
                <h2>Humidity &mdash; Last 24 Hours</h2>
                <div class="chart-subtitle">All 1-minute readings with 3-day average overlay</div>
            </div>
            <div id="humRawPlot" class="plot"></div>
        </div>
        <div class="chart-box">
            <div class="chart-header">
                <h2>Humidity &mdash; 30-Minute Averages by Day</h2>
                <div class="chart-subtitle">One line per calendar day</div>
            </div>
            <div id="humAvgPlot" class="plot"></div>
        </div>
        <div class="chart-box">
            <div class="chart-header">
                <h2>Humidity &mdash; Daily Distribution</h2>
                <div class="chart-subtitle">Per-day min, quartiles, max, and mean</div>
            </div>
            <div id="humDailyPlot" class="plot"></div>
        </div>
        <div class="chart-box">
            <div class="chart-header">
                <h2>Wet Bulb Temperature &mdash; Last 24 Hours</h2>
                <div class="chart-subtitle">All 1-minute readings with 3-day average overlay</div>
            </div>
            <div id="wbRawPlot" class="plot"></div>
        </div>
        <div class="chart-box">
            <div class="chart-header">
                <h2>Wet Bulb Temperature &mdash; 30-Minute Averages by Day</h2>
                <div class="chart-subtitle">One line per calendar day</div>
            </div>
            <div id="wbAvgPlot" class="plot"></div>
        </div>
        <div class="chart-box">
            <div class="chart-header">
                <h2>Wet Bulb Temperature &mdash; Daily Distribution</h2>
                <div class="chart-subtitle">Per-day min, quartiles, max, and mean</div>
            </div>
            <div id="wbDailyPlot" class="plot"></div>
        </div>
    </div>

    <div id="tab-aq" class="tab-content">
        <div class="chart-box">
            <div class="chart-header">
                <h2>VOC Index &mdash; Last 24 Hours</h2>
                <div class="chart-subtitle">Volatile Organic Compounds (0-500); all 1-minute readings with 3-day average overlay</div>
            </div>
            <div id="vocRawPlot" class="plot"></div>
        </div>
        <div class="chart-box">
            <div class="chart-header">
                <h2>VOC Index &mdash; 30-Minute Averages by Day</h2>
                <div class="chart-subtitle">One line per calendar day</div>
            </div>
            <div id="vocAvgPlot" class="plot"></div>
        </div>
        <div class="chart-box">
            <div class="chart-header">
                <h2>VOC Index &mdash; Daily Distribution</h2>
                <div class="chart-subtitle">Per-day min, quartiles, max, and mean</div>
            </div>
            <div id="vocDailyPlot" class="plot"></div>
        </div>
        <div class="chart-box">
            <div class="chart-header">
                <h2>NOx Index &mdash; Last 24 Hours</h2>
                <div class="chart-subtitle">Nitrogen Oxides (0-500); all 1-minute readings with 3-day average overlay</div>
            </div>
            <div id="noxRawPlot" class="plot"></div>
        </div>
        <div class="chart-box">
            <div class="chart-header">
                <h2>NOx Index &mdash; 30-Minute Averages by Day</h2>
                <div class="chart-subtitle">One line per calendar day</div>
            </div>
            <div id="noxAvgPlot" class="plot"></div>
        </div>
        <div class="chart-box">
            <div class="chart-header">
                <h2>NOx Index &mdash; Daily Distribution</h2>
                <div class="chart-subtitle">Per-day min, quartiles, max, and mean</div>
            </div>
            <div id="noxDailyPlot" class="plot"></div>
        </div>
    </div>

    <div id="tab-light" class="tab-content">
        <div class="chart-box">
            <div class="chart-header">
                <h2>Ambient Light &mdash; Last 24 Hours</h2>
                <div class="chart-subtitle">All 1-minute readings in lux with 3-day average overlay</div>
            </div>
            <div id="lightRawPlot" class="plot"></div>
        </div>
        <div class="chart-box">
            <div class="chart-header">
                <h2>Ambient Light &mdash; 30-Minute Averages by Day</h2>
                <div class="chart-subtitle">One line per calendar day</div>
            </div>
            <div id="lightAvgPlot" class="plot"></div>
        </div>
        <div class="chart-box">
            <div class="chart-header">
                <h2>Ambient Light &mdash; Daily Distribution</h2>
                <div class="chart-subtitle">Per-day min, quartiles, max, and mean</div>
            </div>
            <div id="lightDailyPlot" class="plot"></div>
        </div>
    </div>

    <div class="actions">
        <button onclick="resetAxes()">Reset All Zoom</button>
    </div>
    <div class="note">
        Charts auto-refresh every 60 seconds. Drag to zoom, double-click to reset individual axes.
    </div>
</div>

<script>
var _data = null;
var _currentTab = 'tab-th';

function switchTab(tabId) {
    _currentTab = tabId;
    document.querySelectorAll('.tab-btn').forEach(function(b) { b.classList.remove('active'); });
    document.querySelectorAll('.tab-content').forEach(function(c) { c.classList.remove('active'); });
    document.getElementById(tabId).classList.add('active');
    var buttons = document.querySelectorAll('.tab-btn');
    if (tabId === 'tab-th') buttons[0].classList.add('active');
    else if (tabId === 'tab-aq') buttons[1].classList.add('active');
    else buttons[2].classList.add('active');
    setTimeout(function() {
        Plotly.Plots.resize(document.querySelector('.tab-content.active .plot'));
        if (_data) renderPlots(_data);
    }, 50);
}

function getBounds(values, fallbackMin, fallbackMax) {
    if (!values.length) return { min: fallbackMin, max: fallbackMax };
    var min = Math.min.apply(null, values);
    var max = Math.max.apply(null, values);
    var pad = Math.max((max - min) * 0.1, 0.5);
    return { min: min - pad, max: max + pad };
}

function baseLayout(yTitle, yBounds) {
    return {
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: '#111827',
        font: { color: '#e5e7eb' },
        margin: { l: 60, r: 20, t: 10, b: 50 },
        xaxis: {
            type: 'date',
            gridcolor: 'rgba(148,163,184,0.12)',
            zerolinecolor: 'rgba(148,163,184,0.12)',
            color: '#94a3b8'
        },
        yaxis: {
            title: yTitle,
            range: [yBounds.min, yBounds.max],
            gridcolor: 'rgba(148,163,184,0.12)',
            zerolinecolor: 'rgba(148,163,184,0.12)',
            color: '#94a3b8'
        },
        hovermode: 'closest',
        legend: { orientation: 'h', y: 1.08, x: 0 }
    };
}

function baseDayLayout(yTitle, yBounds) {
    return {
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: '#111827',
        font: { color: '#e5e7eb' },
        margin: { l: 60, r: 20, t: 10, b: 50 },
        xaxis: {
            title: 'Time of Day',
            type: 'date',
            range: ['2000-01-01T00:00:00', '2000-01-02T00:00:00'],
            tickformat: '%H:%M',
            dtick: 3600000,
            gridcolor: 'rgba(148,163,184,0.12)',
            zerolinecolor: 'rgba(148,163,184,0.12)',
            color: '#94a3b8'
        },
        yaxis: {
            title: yTitle,
            range: [yBounds.min, yBounds.max],
            gridcolor: 'rgba(148,163,184,0.12)',
            zerolinecolor: 'rgba(148,163,184,0.12)',
            color: '#94a3b8'
        },
        hovermode: 'closest'
    };
}

var CONFIG = { responsive: true, displayModeBar: true, scrollZoom: true };

function dailyLayout(yTitle, yBounds) {
    return {
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: '#111827',
        font: { color: '#e5e7eb' },
        margin: { l: 60, r: 20, t: 10, b: 70 },
        xaxis: {
            title: 'Day',
            type: 'category',
            tickangle: -45,
            gridcolor: 'rgba(148,163,184,0.12)',
            zerolinecolor: 'rgba(148,163,184,0.12)',
            color: '#94a3b8'
        },
        yaxis: {
            title: yTitle,
            range: [yBounds.min, yBounds.max],
            gridcolor: 'rgba(148,163,184,0.12)',
            zerolinecolor: 'rgba(148,163,184,0.12)',
            color: '#94a3b8'
        },
        hovermode: 'closest'
    };
}

var CIVIDIS_STOPS = [
    [0.0, [0,32,76]],
    [0.1, [0,52,107]],
    [0.2, [23,77,131]],
    [0.3, [55,101,133]],
    [0.4, [90,124,117]],
    [0.5, [124,146,90]],
    [0.6, [162,164,62]],
    [0.7, [200,179,43]],
    [0.8, [231,194,30]],
    [0.9, [253,219,35]],
    [1.0, [253,231,37]]
];

function cividisColor(t) {
    t = Math.max(0, Math.min(1, t));
    var i;
    for (i = 0; i < CIVIDIS_STOPS.length - 2 && CIVIDIS_STOPS[i + 1][0] <= t; i++);
    var lo = CIVIDIS_STOPS[i], hi = CIVIDIS_STOPS[i + 1];
    var frac = (t - lo[0]) / (hi[0] - lo[0]);
    var r = Math.round(lo[1][0] + frac * (hi[1][0] - lo[1][0]));
    var g = Math.round(lo[1][1] + frac * (hi[1][1] - lo[1][1]));
    var b = Math.round(lo[1][2] + frac * (hi[1][2] - lo[1][2]));
    return 'rgb(' + r + ',' + g + ',' + b + ')';
}

function hexToRgba(hex, a) {
    var h = hex.replace('#', '');
    return 'rgba(' + parseInt(h.substring(0,2), 16) + ',' + parseInt(h.substring(2,4), 16) + ',' + parseInt(h.substring(4,6), 16) + ',' + a + ')';
}

function timeOfDayAnchor(isoString) {
    var d = new Date(isoString);
    var hh = String(d.getHours()).padStart(2, '0');
    var mm = String(d.getMinutes()).padStart(2, '0');
    var ss = String(d.getSeconds()).padStart(2, '0');
    return '2000-01-01T' + hh + ':' + mm + ':' + ss;
}

function groupRollupsByDay(rollups, metricKey) {
    var grouped = {};
    for (var i = 0; i < rollups.length; i++) {
        var r = rollups[i];
        var d = new Date(r.timestamp);
        var dayKey = d.getFullYear() + '-' +
            String(d.getMonth() + 1).padStart(2, '0') + '-' +
            String(d.getDate()).padStart(2, '0');
        if (!grouped[dayKey]) grouped[dayKey] = [];
        grouped[dayKey].push({
            original_timestamp: r.timestamp,
            tod_timestamp: timeOfDayAnchor(r.timestamp),
            value: r[metricKey]
        });
    }
    var sortedDays = Object.keys(grouped).sort();
    for (var j = 0; j < sortedDays.length; j++) {
        grouped[sortedDays[j]].sort(function(a, b) {
            return new Date(a.original_timestamp) - new Date(b.original_timestamp);
        });
    }
    return sortedDays.map(function(day) { return { day: day, points: grouped[day] }; });
}

function buildDailyTraces(dayGroups, baseHex, valueLabel) {
    var total = dayGroups.length;
    return dayGroups.map(function(group, index) {
        var ratio = total <= 1 ? 1.0 : index / (total - 1);
        var isLatest = index === total - 1;
        return {
            x: group.points.map(function(p) { return p.tod_timestamp; }),
            y: group.points.map(function(p) { return p.value; }),
            type: 'scatter',
            mode: 'lines',
            name: group.day,
            showlegend: false,
            line: { color: cividisColor(ratio), width: isLatest ? 3 : 2 },
            hovertemplate: 'Day: ' + group.day + '<br>Time: %{x|%H:%M}<br>' + valueLabel + ': %{y:.2f}<extra></extra>'
        };
    });
}

function makeRawTrace(x, y, color, name, unit) {
    return [{
        x: x, y: y,
        type: 'scatter', mode: 'lines+markers',
        name: name,
        line: { color: color, width: 2 },
        marker: { color: color, size: 5 },
        hovertemplate: '%{x}<br>' + name + ': %{y:.2f} ' + unit + '<extra></extra>'
    }];
}

var RAW_PLOTS = [
    { id: 'tempRawPlot', metric: 'temperature', color: '#ef4444', name: 'Temperature', unit: 'C', fallback: [0, 50] },
    { id: 'humRawPlot',  metric: 'humidity',    color: '#3b82f6', name: 'Humidity',    unit: '%', fallback: [0, 100] },
    { id: 'wbRawPlot',   metric: 'wet_bulb_temperature', color: '#14b8a6', name: 'Wet Bulb', unit: 'C', fallback: [-10, 40] },
    { id: 'vocRawPlot',  metric: 'voc_index',   color: '#f59e0b', name: 'VOC Index',  unit: '',  fallback: [0, 500] },
    { id: 'noxRawPlot',  metric: 'nox_index',   color: '#a855f7', name: 'NOx Index',  unit: '',  fallback: [0, 500] },
    { id: 'lightRawPlot',metric: 'ambient_light',color: '#eab308', name: 'Light',      unit: 'lx', fallback: [0, 1000] },
];

var AVG_PLOTS = [
    { id: 'tempAvgPlot',  rollupKey: 'temperature_avg', color: '#f59e0b', label: '30m Avg Temp (C)', fallback: [0, 50] },
    { id: 'humAvgPlot',   rollupKey: 'humidity_avg',    color: '#06b6d4', label: '30m Avg Humidity (%)', fallback: [0, 100] },
    { id: 'wbAvgPlot',    rollupKey: 'wet_bulb_temp_avg', color: '#14b8a6', label: '30m Avg Wet Bulb (C)', fallback: [-10, 40] },
    { id: 'vocAvgPlot',   rollupKey: 'voc_avg',          color: '#f59e0b', label: '30m Avg VOC Index', fallback: [0, 500] },
    { id: 'noxAvgPlot',   rollupKey: 'nox_avg',          color: '#a855f7', label: '30m Avg NOx Index', fallback: [0, 500] },
    { id: 'lightAvgPlot', rollupKey: 'light_avg',         color: '#eab308', label: '30m Avg Light (lx)', fallback: [0, 1000] },
];

var DAILY_PLOTS = [
    { id: 'tempDailyPlot',  metric: 'temperature', color: '#ef4444', name: 'Temperature', unit: 'C', fallback: [0, 50] },
    { id: 'humDailyPlot',   metric: 'humidity',    color: '#3b82f6', name: 'Humidity',    unit: '%', fallback: [0, 100] },
    { id: 'wbDailyPlot',    metric: 'wet_bulb_temperature', color: '#14b8a6', name: 'Wet Bulb', unit: 'C', fallback: [-10, 40] },
    { id: 'vocDailyPlot',   metric: 'voc_index',   color: '#f59e0b', name: 'VOC Index',  unit: '',  fallback: [0, 500] },
    { id: 'noxDailyPlot',   metric: 'nox_index',   color: '#a855f7', name: 'NOx Index',  unit: '',  fallback: [0, 500] },
    { id: 'lightDailyPlot', metric: 'ambient_light',color: '#eab308', name: 'Light',      unit: 'lx', fallback: [0, 1000] },
];

var ALL_PLOT_IDS = [];
RAW_PLOTS.forEach(function(p) { ALL_PLOT_IDS.push(p.id); });
AVG_PLOTS.forEach(function(p) { ALL_PLOT_IDS.push(p.id); });
DAILY_PLOTS.forEach(function(p) { ALL_PLOT_IDS.push(p.id); });

function resetAxes() {
    ALL_PLOT_IDS.forEach(function(id) {
        var el = document.getElementById(id);
        if (!el) return;
        if (id.indexOf('AvgPlot') !== -1) {
            Plotly.relayout(id, { 'xaxis.range': ['2000-01-01T00:00:00', '2000-01-02T00:00:00'], 'yaxis.autorange': true });
        } else {
            Plotly.relayout(id, { 'xaxis.autorange': true, 'yaxis.autorange': true });
        }
    });
}

function renderPlots(data) {
    _data = data;
    var readings = data.recent_readings;
    var rollups = data.rollups;
    var trends = data.trends;

    var rawTimestamps = readings.map(function(r) { return r.timestamp; });

    document.getElementById('pointCount').textContent = data.total_count;

    if (readings.length > 0) {
        var latest = readings[readings.length - 1];
        document.getElementById('latestTemp').textContent =
            latest.temperature != null ? latest.temperature.toFixed(1) + ' C' : '--';
        document.getElementById('latestHum').textContent =
            latest.humidity != null ? latest.humidity.toFixed(1) + ' %' : '--';
        document.getElementById('latestVoc').textContent =
            latest.voc_index != null ? latest.voc_index.toFixed(0) : '--';
        document.getElementById('latestNox').textContent =
            latest.nox_index != null ? latest.nox_index.toFixed(0) : '--';
        document.getElementById('latestLight').textContent =
            latest.ambient_light != null ? latest.ambient_light.toFixed(1) + ' lx' : '--';
    }

    for (var i = 0; i < RAW_PLOTS.length; i++) {
        var p = RAW_PLOTS[i];
        var el = document.getElementById(p.id);
        if (!el || !el.offsetParent) continue;
        var pairs = readings.map(function(r) { return {x: r.timestamp, y: r[p.metric]}; })
                           .filter(function(pt) { return pt.y != null; });
        if (pairs.length === 0) continue;
        var xvals = pairs.map(function(pt) { return pt.x; });
        var yvals = pairs.map(function(pt) { return pt.y; });

        var traces = makeRawTrace(xvals, yvals, p.color, p.name, p.unit);

        var profile = data.prev3day_profile;
        if (profile && profile.length > 0 && xvals.length > 0) {
            var profileMap = {};
            for (var pi = 0; pi < profile.length; pi++) {
                if (profile[pi][p.metric] != null) {
                    profileMap[profile[pi].time_of_day] = profile[pi][p.metric];
                }
            }
            var profileX = [];
            var profileY = [];
            for (var ri = 0; ri < xvals.length; ri++) {
                var tod = xvals[ri].substring(11, 16);
                var pv = profileMap[tod];
                if (pv != null) {
                    profileX.push(xvals[ri]);
                    profileY.push(pv);
                    yvals.push(pv);
                }
            }
            if (profileX.length > 0) {
                traces.push({
                    x: profileX, y: profileY,
                    type: 'scatter', mode: 'lines',
                    name: '3-day avg',
                    line: { color: p.color, width: 1.5 },
                    opacity: 0.35,
                    hovertemplate: '3-day avg<br>Time: %{x}<br>' + p.name + ': %{y:.2f} ' + p.unit + '<extra></extra>'
                });
            }
        }

        var bounds = getBounds(yvals, p.fallback[0], p.fallback[1]);
        Plotly.react(p.id, traces,
            baseLayout(p.name + ' (' + p.unit + ')', bounds), CONFIG);
    }

    for (var j = 0; j < AVG_PLOTS.length; j++) {
        var ap = AVG_PLOTS[j];
        var ael = document.getElementById(ap.id);
        if (!ael || !ael.offsetParent) continue;
        var dayGroups = groupRollupsByDay(rollups, ap.rollupKey);
        if (dayGroups.length === 0) continue;
        var allVals = [];
        dayGroups.forEach(function(g) {
            g.points.forEach(function(pt) { allVals.push(pt.value); });
        });
        var avgBounds = getBounds(allVals, ap.fallback[0], ap.fallback[1]);
        Plotly.react(ap.id,
            buildDailyTraces(dayGroups, ap.color, ap.label),
            baseDayLayout(ap.label, avgBounds), CONFIG);
    }

    for (var k = 0; k < DAILY_PLOTS.length; k++) {
        var dp = DAILY_PLOTS[k];
        var del2 = document.getElementById(dp.id);
        if (!del2 || !del2.offsetParent) continue;
        var dailyStats = data.daily_stats;
        var allDays = Object.keys(dailyStats).sort();
        if (allDays.length === 0) continue;
        var plotDays = [], q1 = [], med = [], q3 = [], lof = [], hif = [], mn = [];
        var allVals = [];
        for (var d = 0; d < allDays.length; d++) {
            var s = dailyStats[allDays[d]][dp.metric];
            if (s) {
                plotDays.push(allDays[d]);
                q1.push(s.q1); med.push(s.median); q3.push(s.q3);
                lof.push(s.min); hif.push(s.max); mn.push(s.mean);
                allVals.push(s.min, s.q1, s.median, s.q3, s.max, s.mean);
            }
        }
        if (q1.length === 0) continue;
        var db = getBounds(allVals, dp.fallback[0], dp.fallback[1]);
        var boxTrace = {
            type: 'box',
            x: plotDays,
            q1: q1, median: med, q3: q3,
            lowerfence: lof, upperfence: hif,
            mean: mn,
            boxmean: true,
            name: dp.name,
            marker: { color: dp.color },
            fillcolor: hexToRgba(dp.color, 0.15),
            line: { color: dp.color },
            hovertemplate: '%{x}<br>Min: %{customdata[0]:.2f}  Q1: %{customdata[1]:.2f}  Med: %{customdata[2]:.2f}  Q3: %{customdata[3]:.2f}  Max: %{customdata[4]:.2f}  Mean: %{customdata[5]:.2f} ' + dp.unit + '<extra></extra>',
            customdata: plotDays.map(function(day, i) { return [lof[i], q1[i], med[i], q3[i], hif[i], mn[i]]; })
        };
        Plotly.react(dp.id, [boxTrace],
            dailyLayout(dp.name + ' (' + dp.unit + ')', db), CONFIG);
    }
}

function loadData() {
    fetch('/data')
        .then(function(r) { return r.json(); })
        .then(function(data) { renderPlots(data); })
        .catch(function(err) { console.error('Failed to load data:', err); });
}

loadData();
setInterval(loadData, 60000);
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/data")
def data():
    return jsonify({
        "total_count": get_total_count(),
        "recent_readings": get_recent_readings(RECENT_LIMIT),
        "rollups": get_rollups(),
        "trends": get_trends(),
        "prev3day_profile": get_prev3day_profile(),
        "daily_stats": get_daily_stats(),
    })



