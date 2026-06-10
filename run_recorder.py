from src.database import init_db
from src.models import backfill_rollups, backfill_trends
from src.recorder import sensor_loop

if __name__ == "__main__":
    init_db()
    backfill_rollups()
    backfill_trends()
    sensor_loop()
