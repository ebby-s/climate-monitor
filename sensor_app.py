from threading import Thread

from src.database import init_db
from src.models import backfill_rollups, backfill_trends
from src.recorder import sensor_loop
from src.webapp import app

if __name__ == "__main__":
    init_db()
    backfill_rollups()
    backfill_trends()
    Thread(target=sensor_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=5000)
