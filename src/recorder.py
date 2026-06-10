import time

import board
import adafruit_dht

from src.models import save_reading, maybe_update_rollup_for_time

dht = adafruit_dht.DHT11(board.D4)

def sensor_loop():
    while True:
        try:
            temp = dht.temperature
            hum = dht.humidity

            if temp is not None and hum is not None:
                ts = save_reading(temp, hum)
                maybe_update_rollup_for_time(ts)
                print(f"Saved: {temp}°C {hum}%")

        except Exception as e:
            print("Sensor error:", e)

        time.sleep(60)
