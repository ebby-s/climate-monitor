from src.database import init_db
from src.models import backfill_rollups, backfill_trends, backfill_wet_bulb_readings, backfill_wet_bulb_rollups, backfill_wet_bulb_trends
from src.webapp import app

if __name__ == "__main__":
    init_db()
    backfill_wet_bulb_readings()
    backfill_wet_bulb_rollups()
    backfill_wet_bulb_trends()
    backfill_rollups()
    backfill_trends()
    app.run(host="0.0.0.0", port=5000)
