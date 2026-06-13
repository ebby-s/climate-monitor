import time

from src.sensors import SensorReader
from src.models import save_reading, maybe_update_rollup


def sensor_loop():
    reader = SensorReader()

    while True:
        try:
            data = reader.read_all()
            ts = save_reading(data)
            maybe_update_rollup(ts)

            parts = []
            if data["temperature"] is not None:
                parts.append(f"{data['temperature']}C")
            if data["humidity"] is not None:
                parts.append(f"{data['humidity']}%")
            if data["voc_index"] is not None:
                parts.append(f"VOC:{data['voc_index']:.0f}")
            if data["nox_index"] is not None:
                parts.append(f"NOx:{data['nox_index']:.0f}")
            if data["ambient_light"] is not None:
                parts.append(f"{data['ambient_light']:.0f}lx")
            print(f"Saved: {' '.join(parts)}")

        except Exception as e:
            print(f"Recorder error: {e}")

        time.sleep(60)
