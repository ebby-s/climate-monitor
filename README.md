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

Verify sensors are detected (SGP41 may not appear):
```bash
sudo i2cdetect -y 1
```

**Armbian / non-Raspberry Pi:** Use `armbian-config` → System → Hardware → enable i2c0. The I2C bus may be `/dev/i2c-0`. Set the environment variable if needed:
```bash
export CLIMATE_I2C_BUS=/dev/i2c-0
```

## Software Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Running

Three modes of operation:

| Script | Runs | Use case |
|--------|------|----------|
| `python run_recorder.py` | Recorder only | Sensor Pi |
| `python run_webserver.py` | Webserver only | Dashboard machine |
| `python sensor_app.py` | Both (threaded) | Single-machine setup |

## Auto-start on Boot

Install the systemd service with the install script:

```bash
bash scripts/install_services.sh
```

The script auto-detects your project path, user, and virtual environment, then asks which mode to install:

| Choice | Installs | For |
|--------|----------|-----|
| `recorder` | `climate-monitor-recorder.service` + sync timer | Sensor Pi |
| `webserver` | `climate-monitor-webserver.service` | Dashboard machine |
| `combined` | `climate-monitor.service` | Single machine |

After install:

```bash
# Check status
systemctl status climate-monitor-recorder

# View logs
journalctl -u climate-monitor-recorder -f
```

## Split Deployment Over Tailscale

Run the recorder on the Pi (with sensors) and the webserver on a separate machine (laptop, desktop, or second Pi). The database is synced every 60 seconds over a Tailscale network.

### Setup

1. **Install Tailscale on both machines** and join the same tailnet ([tailscale.com/download](https://tailscale.com/download)).

2. **Set up both machines** with the project:
   ```bash
   git clone ... ~/climate-monitor
   cd ~/climate-monitor
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **On the recorder Pi**, install the recorder service + sync timer:
   ```bash
   bash scripts/install_services.sh   # choose 1 (recorder)
   ```

4. **On the webserver machine**, install the webserver service:
   ```bash
   bash scripts/install_services.sh   # choose 2 (webserver)
   ```

5. **On the recorder Pi**, edit `scripts/sync_db.sh` and set your webserver's Tailscale hostname:
   ```bash
   TARGET="my-webserver"  # or "my-webserver.tailnet-name.ts.net"
   ```

6. **On the recorder Pi**, copy your SSH key to the webserver:
   ```bash
   ssh-copy-id my-webserver
   ```

7. **On the webserver**, create the data directory:
   ```bash
   mkdir -p ~/climate-monitor/data
   ```

8. Start syncing (the timer is already enabled, but trigger the first sync now):
   ```bash
   sudo systemctl start climate-monitor-sync
   ```

The dashboard is then accessible at `http://<webserver-hostname>:5000`.

### How the sync works

The sync timer fires every 60 seconds. It runs `scripts/sync_db.sh` which:

1. Creates a transactionally-consistent snapshot via `sqlite3 .backup` (safe while the recorder is writing)
2. Uses `rsync` over Tailscale to copy the snapshot to the webserver
3. `rsync` atomically replaces the DB file on the webserver — open connections keep reading the old inode until they close; the next request picks up the new data

The database uses **WAL journal mode** so the recorder can write and the webserver can read concurrently without locking conflicts.

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
├── run_recorder.py          # Entry: recorder only
├── run_webserver.py         # Entry: webserver only
├── sensor_app.py            # Entry: combined recorder + webserver
├── scripts/
│   ├── install_services.sh  # One-command systemd setup
│   └── sync_db.sh           # DB snapshot + rsync to webserver
├── services/
│   ├── climate-monitor-recorder.service
│   ├── climate-monitor-webserver.service
│   ├── climate-monitor.service
│   ├── climate-monitor-sync.service
│   └── climate-monitor-sync.timer
├── data/                    # SQLite database (gitignored)
└── src/
    ├── __init__.py
    ├── config.py            # Constants, I2C addresses
    ├── database.py          # SQLite schema and utilities
    ├── models.py            # Data access and aggregation
    ├── sensors.py           # Sensor drivers and SGP41 algorithm
    ├── recorder.py          # Recording loop
    └── webapp.py            # Flask server and Plotly dashboard
```
