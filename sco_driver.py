"""
SCO_1_500K Oscilloscope Hardware Driver & Telemetry Streamer
Author: Antigravity Engineering
------------------------------------------------------------
Provides robust, thread-safe asynchronous telemetry polling from the
SCO_1_500K digital oscilloscope over UART at 9600 Baud.
Features:
- Background acquisition worker (5-10 Hz)
- Accurate unit conversions (uV -> V, centi-Hz -> Hz, 10ns -> us)
- Remote AUTO calibration command (0x01 0x01)
- Rolling buffer of history metrics for real-time trend plotting
- Thread-safe state access
"""

import time
import struct
import threading
from typing import Dict, Any, Optional, List
from collections import deque
import serial
import serial.tools.list_ports

HEADER = bytes([0xAB, 0xCD, 0xEF])

class SCODriver:
    def __init__(self, port: str = "COM3", baudrate: int = 9600, history_len: int = 120):
        self.port = port
        self.baudrate = baudrate
        self.ser: Optional[serial.Serial] = None
        self.lock = threading.Lock()
        
        self.running = False
        self.worker_thread: Optional[threading.Thread] = None
        
        # State
        self.connected = False
        self.last_error = ""
        self.last_update_ts = 0.0
        self.latest_metrics: Dict[str, Any] = self._empty_metrics()
        self.history: deque = deque(maxlen=history_len)
        self.is_frozen = False
        self.last_frozen_metrics: Optional[Dict[str, Any]] = None

    def _empty_metrics(self) -> Dict[str, Any]:
        return {
            "v_max": 0.0,
            "v_min": 0.0,
            "v_ave": 0.0,
            "v_pp": 0.0,
            "v_peak": 0.0,
            "v_rms": 0.0,
            "period_us": 0.0,
            "frequency_hz": 0.0,
            "duty_pos_pct": 0.0,
            "duty_neg_pct": 0.0,
            "pw_pos_us": 0.0,
            "pw_neg_us": 0.0,
            "timestamp": time.time(),
            "formatted_time": time.strftime("%H:%M:%S")
        }

    def open_port(self) -> bool:
        with self.lock:
            if self.ser and self.ser.is_open:
                return True
            try:
                self.ser = serial.Serial(
                    port=self.port,
                    baudrate=self.baudrate,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    timeout=0.6
                )
                self.ser.reset_input_buffer()
                self.ser.reset_output_buffer()
                self.connected = True
                self.last_error = ""
                return True
            except Exception as e:
                self.connected = False
                self.last_error = str(e)
                return False

    def close_port(self):
        with self.lock:
            if self.ser and self.ser.is_open:
                try:
                    self.ser.close()
                except Exception:
                    pass
            self.ser = None
            self.connected = False

    def trigger_auto(self) -> bool:
        """Sends the remote AUTO calibration command (0x01 0x01) to the oscilloscope."""
        with self.lock:
            if not self.ser or not self.ser.is_open:
                return False
            try:
                self.ser.reset_input_buffer()
                self.ser.write(bytes([0x01, 0x01]))
                time.sleep(0.4)
                return True
            except Exception as e:
                self.last_error = str(e)
                return False

    def toggle_freeze(self) -> bool:
        """Freezes or unfreezes live telemetry updates."""
        self.is_frozen = not self.is_frozen
        if self.is_frozen:
            self.last_frozen_metrics = dict(self.latest_metrics)
        else:
            self.last_frozen_metrics = None
        return self.is_frozen

    def _query_device(self) -> Optional[Dict[str, Any]]:
        """Sends 0x02 0x02 and parses the 55-byte response packet."""
        if not self.ser or not self.ser.is_open:
            return None

        try:
            self.ser.reset_input_buffer()
            self.ser.write(bytes([0x02, 0x02]))
            
            # Read 55 bytes
            data = self.ser.read(55)
            if len(data) != 55:
                # retry reading remainder if chunked
                if len(data) > 0 and len(data) < 55:
                    remainder = self.ser.read(55 - len(data))
                    data += remainder

            if len(data) != 55 or data[:3] != HEADER:
                return None

            payload = data[3:51]
            signs = data[51:55]
            raw = struct.unpack('<12I', payload)

            def parse_v(val: int, sign: int) -> float:
                v = -val if sign == 1 else val
                return round(v / 1_000_000.0, 4)

            vmax = parse_v(raw[0], signs[0])
            vmin = parse_v(raw[1], signs[1])
            vave = parse_v(raw[2], signs[2])
            vpp  = round(raw[3] / 1_000_000.0, 4)
            vp   = parse_v(raw[4], signs[3])
            vrms = round(raw[5] / 1_000_000.0, 4)

            # Period in 10ns ticks -> microseconds
            period_us = round((raw[6] * 10.0) / 1000.0, 3)
            # Frequency in 0.01 Hz -> Hz
            freq_hz   = round(raw[7] / 100.0, 2)
            # Duty cycles in 0.1 %
            duty_pos  = round(raw[8] * 0.1, 1)
            duty_neg  = round(raw[9] * 0.1, 1)
            # Pulse widths in 10ns ticks -> microseconds
            pw_pos_us = round((raw[10] * 10.0) / 1000.0, 3)
            pw_neg_us = round((raw[11] * 10.0) / 1000.0, 3)

            now = time.time()
            return {
                "v_max": vmax,
                "v_min": vmin,
                "v_ave": vave,
                "v_pp": vpp,
                "v_peak": vp,
                "v_rms": vrms,
                "period_us": period_us,
                "frequency_hz": freq_hz,
                "duty_pos_pct": duty_pos,
                "duty_neg_pct": duty_neg,
                "pw_pos_us": pw_pos_us,
                "pw_neg_us": pw_neg_us,
                "timestamp": now,
                "formatted_time": time.strftime("%H:%M:%S", time.localtime(now))
            }
        except Exception as e:
            self.last_error = str(e)
            return None

    def _worker_loop(self):
        """Background thread worker for streaming telemetry."""
        consecutive_failures = 0
        while self.running:
            if not self.connected:
                if not self.open_port():
                    time.sleep(1.0)
                    continue

            with self.lock:
                metrics = self._query_device()

            if metrics:
                consecutive_failures = 0
                self.connected = True
                self.last_update_ts = time.time()
                if not self.is_frozen:
                    self.latest_metrics = metrics
                    self.history.append({
                        "t": metrics["formatted_time"],
                        "ts": metrics["timestamp"],
                        "v_max": metrics["v_max"],
                        "v_ave": metrics["v_ave"],
                        "v_pp": metrics["v_pp"],
                        "freq": metrics["frequency_hz"]
                    })
            else:
                consecutive_failures += 1
                if consecutive_failures > 5:
                    self.connected = False
                    self.close_port()
                    time.sleep(0.5)

            # Polling rate ~6-8 Hz
            time.sleep(0.12)

    def start(self):
        if self.running:
            return
        self.running = True
        self.open_port()
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()

    def stop(self):
        self.running = False
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=1.0)
        self.close_port()

    def get_current_metrics(self) -> Dict[str, Any]:
        with self.lock:
            if self.is_frozen and self.last_frozen_metrics:
                m = dict(self.last_frozen_metrics)
            else:
                m = dict(self.latest_metrics)
            m["connected"] = self.connected
            m["is_frozen"] = self.is_frozen
            m["port"] = self.port
            return m

    def get_history(self) -> List[Dict[str, Any]]:
        with self.lock:
            return list(self.history)
