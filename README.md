# Climate Monitor

Continuous environmental monitoring on Raspberry Pi using three I2C sensors:
**SHT-41** (temperature + humidity), **SGP41** (VOC + NOx gas indices), and **VEML 7700** (ambient light).

Data is recorded every minute to a SQLite database and served through a Plotly.js dashboard with interactive charts.

## Metrics Measured

| Sensor | Metric | Unit | Range |
|--------|--------|------|-------|
| SHT-41 | Temperature | °C | -40 to 125 |
| SHT-41 | Relative Humidity | % | 0 to 100 |
| SGP41 | VOC Index | — | 0 to 500 |
| SGP41 | NOx Index | — | 0 to 500 |
| VEML 7700 | Ambient Light | lux | 0 to ~120k |

## Hardware Setup

Connect all three sensors to the Raspberry Pi I2C bus (pins 3/5). All sensors share the same SDA/SCL lines and are addressed individually.

```
         Raspberry Pi
        ┌────────────┐
  3.3V ─┤ Pin 1      │
   SDA ─┤ Pin 3      │
   SCL ─┤ Pin 5      │
   GND ─┤ Pin 6      │
        └────────────┘
```

| Sensor | VCC | GND | SDA | SCL | I2C Address |
|--------|-----|-----|-----|-----|-------------|
| SHT-41 | Pin 1 (3.3V) | Pin 6 | Pin 3 | Pin 5 | 0x44 |
| SGP41 | Pin 1 (3.3V) | Pin 6 | Pin 3 | Pin 5 | 0x59 |
| VEML 7700 | Pin 1 (3.3V) | Pin 6 | Pin 3 | Pin 5 | 0x10 |

Before running, enable I2C on the Pi:
```bash
sudo raspi-config nonint do_i2c 0
```

Verify sensors are detected:
```bash
sudo i2cdetect -y 1
```

## Software Setup

```bash
# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Running

Three modes of operation are available:

### Combined (single device)
Runs recorder and webserver on the same Pi:
```bash
python sensor_app.py
```

### Recorder only
Writes sensor data to the database file without serving the dashboard:
```bash
python run_recorder.py
```

### Webserver only
Reads from an existing database file and serves the dashboard:
```bash
python run_webserver.py
```

### Split across two devices
Run the recorder on the Pi with the sensors, and the webserver on another device (e.g. a desktop, laptop, or second Pi). Both must access the same `data/` directory — use NFS, Samba, or `rsync` to share the `sensor_data.db` file.

**Recorder device (with sensors):**
```bash
python run_recorder.py
```

**Webserver device (no sensors needed):**
```bash
python run_webserver.py
```

The dashboard is accessible at `http://<device-ip>:5000`.

## Dashboard

Three tabbed sections organize 15 interactive Plotly.js charts:

### Temperature & Humidity (SHT-41) — 6 charts
- Last 12 hours — all 1-minute readings
- 30-minute averages — one line per calendar day
- 6-hour rolling trend — smoothed long-term trend over all recorded data

### Air Quality (SGP41) — 6 charts
- VOC Index and NOx Index, each with the same three chart types above

### Ambient Light (VEML 7700) — 3 charts
- Same three chart types for lux readings

All charts auto-refresh every 60 seconds. Drag to zoom; double-click to reset; use the "Reset All Zoom" button to reset all axes.

## SGP41 Notes

The SGP41 requires a **10-second conditioning cycle** on startup to heat the NOx sensing element. This runs automatically. The VOC and NOx Index values are produced by Sensirion's Gas Index Algorithm, which runs continuously in a background thread at 1 Hz to maintain adaptive baselines. Meaningful values typically appear after 1–2 hours of continuous operation as the algorithm learns the environment.

## File Structure

```
climate-monitor/
├── README.md
├── requirements.txt
├── .gitignore
├── run_recorder.py       # Entry: recorder only
├── run_webserver.py      # Entry: webserver only
├── sensor_app.py         # Entry: combined recorder + webserver
├── data/                 # SQLite database (gitignored)
└── src/
    ├── __init__.py
    ├── config.py         # Constants, I2C addresses
    ├── database.py       # SQLite schema and utilities
    ├── models.py         # Data access and aggregation
    ├── sensors.py        # Sensor drivers and SGP41 algorithm
    ├── recorder.py       # Recording loop
    └── webapp.py         # Flask server and Plotly dashboard
```
