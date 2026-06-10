import os

from flask import Flask, render_template_string, jsonify

from src.models import get_recent_readings, get_rollups, get_trends, get_total_count
from src.config import RECENT_LIMIT

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sensor Dashboard</title>
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
        }

        * { box-sizing: border-box; }

        body {
            margin: 0;
            font-family: Arial, sans-serif;
            background: linear-gradient(180deg, #020617 0%, #0f172a 100%);
            color: var(--text);
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 24px;
        }

        h1 {
            margin: 0 0 8px 0;
            font-size: 32px;
        }

        .subtitle {
            color: var(--muted);
            margin-bottom: 24px;
        }

        .cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }

        .card {
            background: rgba(17, 24, 39, 0.95);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 18px;
        }

        .card h3 {
            margin: 0 0 10px 0;
            font-size: 14px;
            color: var(--muted);
        }

        .value {
            font-size: 28px;
            font-weight: 700;
        }

        .chart-box {
            background: rgba(17, 24, 39, 0.95);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 20px;
            margin-bottom: 20px;
        }

        .chart-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
            gap: 12px;
            flex-wrap: wrap;
        }

        .chart-header h2 {
            margin: 0;
            font-size: 20px;
        }

        .chart-subtitle {
            color: var(--muted);
            font-size: 13px;
        }

        .plot {
            width: 100%;
            height: 420px;
        }

        .actions {
            margin-top: 20px;
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
        }

        button {
            padding: 11px 16px;
            border: 1px solid var(--border);
            background: var(--panel2);
            color: var(--text);
            border-radius: 10px;
            cursor: pointer;
            font-size: 14px;
        }

        button:hover {
            filter: brightness(1.08);
        }

        .shutdown-btn {
            background: #7f1d1d;
            border-color: #991b1b;
        }

        .note {
            margin-top: 12px;
            color: var(--muted);
            font-size: 14px;
        }

        .status-dot {
            display: inline-block;
            width: 10px;
            height: 10px;
            background: var(--green);
            border-radius: 50%;
            margin-right: 8px;
            box-shadow: 0 0 8px var(--green);
        }
    </style>
</head>
<body>
<div class="container">
    <h1>Sensor Dashboard</h1>
    <div class="subtitle">
        <span class="status-dot"></span>
        Power-friendly dashboard: recent raw data, 30-minute averages, and low-frequency trend plots precomputed on-device.
    </div>

    <div class="cards">
        <div class="card">
            <h3>Latest Temperature</h3>
            <div class="value" id="latestTemp">-- °C</div>
        </div>
        <div class="card">
            <h3>Latest Humidity</h3>
            <div class="value" id="latestHum">-- %</div>
        </div>
        <div class="card">
            <h3>Latest Reading Time</h3>
            <div class="value" id="latestTime" style="font-size:18px;">--</div>
        </div>
        <div class="card">
            <h3>Total Raw Points</h3>
            <div class="value" id="pointCount">0</div>
        </div>
    </div>

    <div class="chart-box">
        <div class="chart-header">
            <div>
                <h2>Temperature</h2>
                <div class="chart-subtitle">Latest 240 raw readings</div>
            </div>
        </div>
        <div id="tempPlot" class="plot"></div>
    </div>

    <div class="chart-box">
        <div class="chart-header">
            <div>
                <h2>Humidity</h2>
                <div class="chart-subtitle">Latest 240 raw readings</div>
            </div>
        </div>
        <div id="humPlot" class="plot"></div>
    </div>

    <div class="chart-box">
        <div class="chart-header">
            <div>
                <h2>Temperature 30-Minute Average</h2>
                <div class="chart-subtitle">24-hour view, midnight to midnight, one line per day. Brighter lines are more recent.</div>
            </div>
        </div>
        <div id="tempAvgPlot" class="plot"></div>
    </div>

    <div class="chart-box">
        <div class="chart-header">
            <div>
                <h2>Humidity 30-Minute Average</h2>
                <div class="chart-subtitle">24-hour view, midnight to midnight, one line per day. Brighter lines are more recent.</div>
            </div>
        </div>
        <div id="humAvgPlot" class="plot"></div>
    </div>

    <div class="chart-box">
        <div class="chart-header">
            <div>
                <h2>Temperature Slow Trend</h2>
                <div class="chart-subtitle">6-hour rolling average sampled every 30 minutes to suppress rapid window-opening changes</div>
            </div>
        </div>
        <div id="tempTrendPlot" class="plot"></div>
    </div>

    <div class="chart-box">
        <div class="chart-header">
            <div>
                <h2>Humidity Slow Trend</h2>
                <div class="chart-subtitle">6-hour rolling average sampled every 30 minutes to suppress rapid window-opening changes</div>
            </div>
        </div>
        <div id="humTrendPlot" class="plot"></div>
    </div>

    <div class="actions">
        <button onclick="resetAxes()">Reset Zoom</button>
        <button class="shutdown-btn" onclick="shutdownPi()">Shutdown Raspberry Pi</button>
    </div>

    <div class="note">
        The bottom two trend plots are precomputed from a 6-hour rolling average on 30-minute boundaries for low CPU and low power operation.
    </div>
</div>

<script>
function shutdownPi() {
    if (confirm("Are you sure you want to shut down the Raspberry Pi?")) {
        fetch('/shutdown', { method: 'POST' })
            .then(() => alert("Shutting down..."));
    }
}

function formatDateTime(isoString) {
    return new Date(isoString).toLocaleString();
}

function getBounds(values, fallbackMin, fallbackMax) {
    if (!values.length) {
        return { min: fallbackMin, max: fallbackMax };
    }

    const min = Math.min(...values);
    const max = Math.max(...values);
    let padding = (max - min) * 0.1;

    if (padding < 0.5) {
        padding = 0.5;
    }

    return {
        min: min - padding,
        max: max + padding
    };
}

function baseLayout(title, yTitle, yBounds) {
    return {
        title: {
            text: title,
            font: { color: '#e5e7eb', size: 20 }
        },
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: '#111827',
        font: { color: '#e5e7eb' },
        margin: { l: 60, r: 20, t: 50, b: 60 },
        xaxis: {
            title: 'Time',
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
        hovermode: 'closest'
    };
}

function baseDayLayout(title, yTitle, yBounds) {
    return {
        title: {
            text: title,
            font: { color: '#e5e7eb', size: 20 }
        },
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: '#111827',
        font: { color: '#e5e7eb' },
        margin: { l: 60, r: 20, t: 50, b: 60 },
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
        hovermode: 'closest',
        legend: {
            orientation: 'h',
            y: 1.12,
            x: 0
        }
    };
}

const config = {
    responsive: true,
    displayModeBar: true,
    scrollZoom: true
};

function resetAxes() {
    ['tempPlot', 'humPlot', 'tempTrendPlot', 'humTrendPlot'].forEach(id => {
        Plotly.relayout(id, {
            'xaxis.autorange': true,
            'yaxis.autorange': true
        });
    });

    ['tempAvgPlot', 'humAvgPlot'].forEach(id => {
        Plotly.relayout(id, {
            'xaxis.range': ['2000-01-01T00:00:00', '2000-01-02T00:00:00'],
            'yaxis.autorange': true
        });
    });
}

function rgba(hex, alpha) {
    const h = hex.replace('#', '');
    const bigint = parseInt(h, 16);
    const r = (bigint >> 16) & 255;
    const g = (bigint >> 8) & 255;
    const b = bigint & 255;
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function timeOfDayAnchor(isoString) {
    const d = new Date(isoString);
    const hh = String(d.getHours()).padStart(2, '0');
    const mm = String(d.getMinutes()).padStart(2, '0');
    const ss = String(d.getSeconds()).padStart(2, '0');
    return `2000-01-01T${hh}:${mm}:${ss}`;
}

function groupRollupsByDay(rollups) {
    const grouped = {};

    for (const r of rollups) {
        const d = new Date(r.timestamp);
        const year = d.getFullYear();
        const month = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        const dayKey = `${year}-${month}-${day}`;

        if (!grouped[dayKey]) {
            grouped[dayKey] = [];
        }

        grouped[dayKey].push({
            original_timestamp: r.timestamp,
            tod_timestamp: timeOfDayAnchor(r.timestamp),
            temperature_avg: r.temperature_avg,
            humidity_avg: r.humidity_avg
        });
    }

    const sortedDays = Object.keys(grouped).sort();

    for (const day of sortedDays) {
        grouped[day].sort((a, b) => new Date(a.original_timestamp) - new Date(b.original_timestamp));
    }

    return sortedDays.map(day => ({
        day,
        points: grouped[day]
    }));
}

function buildDailyTraces(dayGroups, valueKey, baseHex, valueLabel) {
    const total = dayGroups.length;

    return dayGroups.map((group, index) => {
        const alpha = total <= 1 ? 1.0 : 0.2 + (0.8 * index / (total - 1));
        const isLatest = index === total - 1;

        return {
            x: group.points.map(p => p.tod_timestamp),
            y: group.points.map(p => p[valueKey]),
            type: 'scatter',
            mode: 'lines',
            name: group.day,
            line: {
                color: rgba(baseHex, alpha),
                width: isLatest ? 3 : 2
            },
            hovertemplate:
                `Day: ${group.day}<br>Time: %{x|%H:%M}<br>${valueLabel}: %{y:.2f}<extra></extra>`
        };
    });
}

function renderPlots(data) {
    const rawTimestamps = data.recent_readings.map(r => r.timestamp);
    const temps = data.recent_readings.map(r => r.temperature);
    const humids = data.recent_readings.map(r => r.humidity);

    const allTempAvgs = data.rollups.map(r => r.temperature_avg);
    const allHumAvgs = data.rollups.map(r => r.humidity_avg);

    const trendTimestamps = data.trends.map(r => r.timestamp);
    const tempTrends = data.trends.map(r => r.temperature_trend);
    const humTrends = data.trends.map(r => r.humidity_trend);

    document.getElementById('pointCount').textContent = data.total_count;

    if (data.recent_readings.length > 0) {
        const latest = data.recent_readings[data.recent_readings.length - 1];
        document.getElementById('latestTemp').textContent = `${latest.temperature} °C`;
        document.getElementById('latestHum').textContent = `${latest.humidity} %`;
        document.getElementById('latestTime').textContent = formatDateTime(latest.timestamp);
    }

    const tempBounds = getBounds(temps, 0, 50);
    const humBounds = getBounds(humids, 0, 100);
    const tempAvgBounds = getBounds(allTempAvgs, 0, 50);
    const humAvgBounds = getBounds(allHumAvgs, 0, 100);
    const tempTrendBounds = getBounds(tempTrends, 0, 50);
    const humTrendBounds = getBounds(humTrends, 0, 100);

    Plotly.react(
        'tempPlot',
        [{
            x: rawTimestamps,
            y: temps,
            type: 'scatter',
            mode: 'lines+markers',
            name: 'Temperature',
            line: { color: '#ef4444', width: 2 },
            marker: { color: '#ef4444', size: 6 },
            hovertemplate: 'Time: %{x}<br>Temperature: %{y:.2f} °C<extra></extra>'
        }],
        baseLayout('Temperature', 'Temperature (°C)', tempBounds),
        config
    );

    Plotly.react(
        'humPlot',
        [{
            x: rawTimestamps,
            y: humids,
            type: 'scatter',
            mode: 'lines+markers',
            name: 'Humidity',
            line: { color: '#3b82f6', width: 2 },
            marker: { color: '#3b82f6', size: 6 },
            hovertemplate: 'Time: %{x}<br>Humidity: %{y:.2f} %<extra></extra>'
        }],
        baseLayout('Humidity', 'Humidity (%)', humBounds),
        config
    );

    const dayGroups = groupRollupsByDay(data.rollups);

    Plotly.react(
        'tempAvgPlot',
        buildDailyTraces(dayGroups, 'temperature_avg', '#f59e0b', '30m Avg Temp (°C)'),
        baseDayLayout('Temperature 30-Minute Average', 'Temperature (°C)', tempAvgBounds),
        config
    );

    Plotly.react(
        'humAvgPlot',
        buildDailyTraces(dayGroups, 'humidity_avg', '#06b6d4', '30m Avg Humidity (%)'),
        baseDayLayout('Humidity 30-Minute Average', 'Humidity (%)', humAvgBounds),
        config
    );

    Plotly.react(
        'tempTrendPlot',
        [{
            x: trendTimestamps,
            y: tempTrends,
            type: 'scatter',
            mode: 'lines',
            name: 'Temperature Slow Trend',
            line: { color: '#ec4899', width: 3 },
            hovertemplate: 'Time: %{x}<br>Temperature Trend: %{y:.2f} °C<extra></extra>'
        }],
        baseLayout('Temperature Slow Trend', 'Temperature (°C)', tempTrendBounds),
        config
    );

    Plotly.react(
        'humTrendPlot',
        [{
            x: trendTimestamps,
            y: humTrends,
            type: 'scatter',
            mode: 'lines',
            name: 'Humidity Slow Trend',
            line: { color: '#14b8a6', width: 3 },
            hovertemplate: 'Time: %{x}<br>Humidity Trend: %{y:.2f} %<extra></extra>'
        }],
        baseLayout('Humidity Slow Trend', 'Humidity (%)', humTrendBounds),
        config
    );
}

function loadData() {
    fetch('/data')
        .then(r => r.json())
        .then(data => renderPlots(data))
        .catch(err => console.error('Failed to load data:', err));
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
        "trends": get_trends()
    })

@app.route("/shutdown", methods=["POST"])
def shutdown():
    os.system("sudo shutdown now")
    return "Shutting down...", 200
