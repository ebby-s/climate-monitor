import time
import threading

import board
import adafruit_sht4x
import adafruit_veml7700
from sensirion_i2c_driver import LinuxI2cTransceiver, I2cConnection
from sensirion_i2c_sgp4x import Sgp41I2cDevice
from sensirion_gas_index_algorithm.voc_algorithm import VocAlgorithm
from sensirion_gas_index_algorithm.nox_algorithm import NoxAlgorithm

from src.config import I2C_BUS


class SensorReader:
    def __init__(self):
        self._sht_ok = False
        self._veml_ok = False
        self._sgp41_ok = False

        self._voc_index = None
        self._nox_index = None
        self._lock = threading.Lock()
        self._running = False

        self._init_sht41()
        self._init_veml7700()
        self._init_sgp41()

    def _init_sht41(self):
        try:
            i2c = board.I2C()
            self._sht = adafruit_sht4x.SHT4x(i2c)
            self._sht.mode = adafruit_sht4x.Mode.NOHEAT_HIGHPRECISION
            self._sht_ok = True
            print("SHT-41 initialized")
        except Exception as e:
            print(f"SHT-41 init failed: {e}")
            self._sht = None

    def _init_veml7700(self):
        try:
            i2c = board.I2C()
            self._veml = adafruit_veml7700.VEML7700(i2c)
            self._veml_ok = True
            print("VEML 7700 initialized")
        except Exception as e:
            print(f"VEML 7700 init failed: {e}")
            self._veml = None

    def _init_sgp41(self):
        try:
            self._sgp_transceiver = LinuxI2cTransceiver(I2C_BUS)
            self._sgp41 = Sgp41I2cDevice(I2cConnection(self._sgp_transceiver))
            serial = self._sgp41.get_serial_number()
            print(f"SGP41 initialized, serial: {serial}")

            print("SGP41 conditioning (10s)...")
            for _ in range(10):
                self._sgp41.conditioning()
                time.sleep(1)
            print("SGP41 conditioning complete")

            self._voc_algo = VocAlgorithm()
            self._nox_algo = NoxAlgorithm()
            self._sgp41_ok = True

            self._running = True
            self._thread = threading.Thread(target=self._sgp41_loop, daemon=True)
            self._thread.start()
        except Exception as e:
            print(f"SGP41 init failed: {e}")
            self._sgp41 = None

    def _sgp41_loop(self):
        while self._running:
            try:
                sraw_voc, sraw_nox = self._sgp41.measure_raw()
                voc = self._voc_algo.process(sraw_voc.ticks)
                nox = self._nox_algo.process(sraw_nox.ticks)
                with self._lock:
                    self._voc_index = voc
                    self._nox_index = nox
            except Exception as e:
                print(f"SGP41 read error: {e}")
            time.sleep(1)

    def read_all(self):
        result = {
            "temperature": None,
            "humidity": None,
            "voc_index": None,
            "nox_index": None,
            "ambient_light": None,
        }

        if self._sht_ok:
            try:
                temp, hum = self._sht.measurements
                result["temperature"] = round(temp, 2)
                result["humidity"] = round(hum, 2)
            except Exception as e:
                print(f"SHT-41 read error: {e}")

        if self._veml_ok:
            try:
                result["ambient_light"] = round(self._veml.light, 2)
            except Exception as e:
                print(f"VEML 7700 read error: {e}")

        if self._sgp41_ok:
            with self._lock:
                if self._voc_index is not None:
                    result["voc_index"] = round(self._voc_index, 2)
                if self._nox_index is not None:
                    result["nox_index"] = round(self._nox_index, 2)

        return result
