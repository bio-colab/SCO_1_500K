"""
SCO_1_500K Oscilloscope Hardware Driver & Telemetry Streamer
Author: Antigravity Engineering
------------------------------------------------------------
Features:
- Cross-platform port auto-discovery (Windows, Linux, macOS)
- Dual-lock architecture: non-blocking state access (0ms latency for web/event loop)
- Dedicated serial bus locking
- Accurate mathematical scaling (uV -> V, centi-Hz -> Hz, 10ns -> us)
- Remote AUTO calibration command (0x01 0x01)
- Rolling telemetry history buffer
"""

import os
import sys
import time
import struct
import threading
from typing import Dict, Any, Optional, List
from collections import deque
import serial
import serial.tools.list_ports

HEADER = bytes([0xAB, 0xCD, 0xEF])

# Known USB-to-TTL UART bridges (VID, PID)
KNOWN_UART_VID_PIDS = {
    (0x1A86, 0x7523): "WCH CH340",
    (0x1A86, 0x5523): "WCH CH341",
    (0x1A86, 0x55D4): "WCH CH9102",
    (0x1A86, 0x55D3): "WCH CH343",
    (0x10C4, 0xEA60): "Silicon Labs CP2102/CP2104",
    (0x0403, 0x6001): "FTDI FT232R",
    (0x067B, 0x2303): "Prolific PL2303"
}

def find_scope_port(preferred: Optional[str] = None) -> Optional[str]:
    """
    Intelligently discovers the SCO_1_500K serial port across Windows, Linux, and macOS.
    Order of precedence:
    1. Explicit parameter `preferred` (e.g. from --port CLI)
    2. SCO_PORT environment variable
    3. Auto-detection matching known USB-to-TTL UART bridges (CH340, CP2102, FT232)
    4. Auto-detection matching USB-Serial keywords in device description
    5. First available serial port
    """
    if preferred and preferred.strip():
        return preferred.strip()

    env_port = os.environ.get("SCO_PORT", "").strip()
    if env_port:
        return env_port

    available_ports = list(serial.tools.list_ports.comports())
    if not available_ports:
        return None

    # Priority A: Check exact VID/PID match
    for port_info in available_ports:
        if port_info.vid is not None and port_info.pid is not None:
            key = (port_info.vid, port_info.pid)
            if key in KNOWN_UART_VID_PIDS:
                return port_info.device

    # Priority B: Check description keywords
    keywords = ["CH340", "CH341", "CP210", "FT232", "USB-SERIAL", "PL2303", "UART", "USB to UART"]
    for port_info in available_ports:
        desc = (port_info.description or "").upper()
        mfg = (port_info.manufacturer or "").upper()
        for kw in keywords:
            if kw.upper() in desc or kw.upper() in mfg:
                return port_info.device

    # Priority C: OS-specific preferred names
    for port_info in available_ports:
        dev = port_info.device
        if dev.startswith("/dev/ttyUSB") or dev.startswith("/dev/ttyACM") or "usbserial" in dev.lower():
            return dev

    # Priority D: First available
    return available_ports[0].device


class SCODriver:
    def __init__(self, port: Optional[str] = None, baudrate: int = 9600, history_len: int = 120):
        self.port = find_scope_port(port) or (port if port else ("COM3" if sys.platform == "win32" else "/dev/ttyUSB0"))
        self.baudrate = baudrate
        self.ser: Optional[serial.Serial] = None
        
        # Dual-Lock Architecture:
        # 1. _state_lock: Protects in-memory state variables only (instantaneous acquire < 1us)
        # 2. _serial_lock: Protects serial bus hardware transactions (prevents bus contention)
        self._state_lock = threading.Lock()
        self._serial_lock = threading.Lock()
        
        self.running = False
        self.worker_thread: Optional[threading.Thread] = None
        
        # Internal State
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
            "overflow": [],
            "timestamp": time.time(),
            "formatted_time": time.strftime("%H:%M:%S")
        }

    def open_port(self) -> bool:
        with self._serial_lock:
            if self.ser and self.ser.is_open:
                return True
            try:
                # If the current port no longer exists, re-scan.
                # (POSIX only: on Windows a COM name is not a filesystem path.)
                needs_rescan = False
                if sys.platform != "win32":
                    needs_rescan = (not self.port) or (not os.path.exists(self.port))
                elif not self.port:
                    needs_rescan = True

                if needs_rescan:
                    detected = find_scope_port()
                    if detected:
                        self.port = detected

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
                
                with self._state_lock:
                    self.connected = True
                    self.last_error = ""
                return True
            except Exception as e:
                with self._state_lock:
                    self.connected = False
                    self.last_error = str(e)
                return False

    def close_port(self):
        with self._serial_lock:
            if self.ser and self.ser.is_open:
                try:
                    self.ser.close()
                except Exception:
                    pass
            self.ser = None
            with self._state_lock:
                self.connected = False

    def trigger_auto(self) -> bool:
        """
        Sends the remote AUTO calibration command (0x01 0x01) to the oscilloscope.
        Thread-safe across serial bus.
        """
        with self._serial_lock:
            if not self.ser or not self.ser.is_open:
                return False
            try:
                self.ser.reset_input_buffer()
                self.ser.write(bytes([0x01, 0x01]))
                time.sleep(0.3)
                return True
            except Exception as e:
                with self._state_lock:
                    self.last_error = str(e)
                return False

    def toggle_freeze(self) -> bool:
        """Freezes or unfreezes live telemetry updates."""
        with self._state_lock:
            self.is_frozen = not self.is_frozen
            if self.is_frozen:
                self.last_frozen_metrics = dict(self.latest_metrics)
            else:
                self.last_frozen_metrics = None
            return self.is_frozen

    def _read_synchronized_packet(self, timeout: float = 0.5) -> Optional[bytes]:
        """
        Reads from serial until HEADER (0xAB, 0xCD, 0xEF) is matched,
        then reads the exact remaining 52 bytes of the packet.
        Handles frame misalignment and drops leading noise automatically.
        """
        if not self.ser or not self.ser.is_open:
            return None

        deadline = time.time() + timeout
        header_buf = bytearray()

        # Step 1: Scan for 3-byte header
        while time.time() < deadline:
            b = self.ser.read(1)
            if not b:
                continue
            header_buf.append(b[0])
            if len(header_buf) > 3:
                header_buf.pop(0)
            if bytes(header_buf) == HEADER:
                break
        else:
            return None

        # Step 2: Read remaining 52 bytes of payload and signs
        remaining = bytearray()
        while len(remaining) < 52 and time.time() < deadline:
            chunk = self.ser.read(52 - len(remaining))
            if chunk:
                remaining.extend(chunk)

        if len(remaining) != 52:
            return None

        return HEADER + bytes(remaining)

    def _query_device_serial(self) -> Optional[Dict[str, Any]]:
        """
        Performs serial I/O to read 55-byte packet with frame resync.
        MUST BE CALLED under _serial_lock ONLY, NOT holding _state_lock.
        """
        if not self.ser or not self.ser.is_open:
            return None

        try:
            self.ser.reset_input_buffer()
            self.ser.write(bytes([0x02, 0x02]))
            
            data = self._read_synchronized_packet(timeout=0.6)
            if not data or len(data) != 55 or data[:3] != HEADER:
                return None

            signs = data[51:55]
            # Heuristic Sanity Check 1: Sign bytes must strictly be 0 (positive) or 1 (negative)
            for s in signs:
                if s not in (0, 1):
                    return None

            payload = data[3:51]
            raw = struct.unpack('<12I', payload)

            # Out-of-range field handling.
            # The firmware has explicit per-field overflow states (Max/Min/Ave/Rms/
            # Vpp/VP/Cyc/+PW/-PW/Fr all have an "overflow" display string), so an
            # implausible field is an expected instrument state, NOT a corrupt frame.
            # Discarding the packet here would make a perfectly healthy device look
            # disconnected after 5 such reads. Clamp the field and report the flag.
            overflow: List[str] = []
            raw = list(raw)

            for idx, name in ((8, "duty_pos"), (9, "duty_neg")):
                if raw[idx] > 1000:  # > 100.0 %
                    overflow.append(name)
                    raw[idx] = 1000

            # Instrument measuring range is +/-400V (Vpp 800V) per the manual.
            for idx, name in ((0, "v_max"), (1, "v_min"), (2, "v_ave"),
                              (3, "v_pp"), (4, "v_peak"), (5, "v_rms")):
                limit = 800_000_000 if idx == 3 else 400_000_000
                if raw[idx] > limit:
                    overflow.append(name)
                    raw[idx] = limit

            def parse_v(val: int, sign: int) -> float:
                v = -val if sign == 1 else val
                return round(v / 1_000_000.0, 4)

            vmax = parse_v(raw[0], signs[0])
            vmin = parse_v(raw[1], signs[1])
            vave = parse_v(raw[2], signs[2])
            vpp  = round(raw[3] / 1_000_000.0, 4)
            vp   = parse_v(raw[4], signs[3])
            vrms = round(raw[5] / 1_000_000.0, 4)

            # Period: 10ns ticks -> microseconds
            period_us = round((raw[6] * 10.0) / 1000.0, 3)
            # Frequency: centi-Hz (0.01 Hz) -> Hz
            freq_hz   = round(raw[7] / 100.0, 2)
            # Duty cycles: in 0.1 %
            duty_pos  = round(raw[8] * 0.1, 1)
            duty_neg  = round(raw[9] * 0.1, 1)
            # Pulse widths: in 10ns ticks -> microseconds
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
                "overflow": overflow,
                "timestamp": now,
                "formatted_time": time.strftime("%H:%M:%S", time.localtime(now))
            }
        except Exception as e:
            with self._state_lock:
                self.last_error = str(e)
            return None

    def read_once(self) -> Optional[Dict[str, Any]]:
        """
        Public single-shot acquisition, safe to call while the worker is running.
        Intended for CLI tools and tests so they never touch private members.
        """
        with self._serial_lock:
            return self._query_device_serial()

    def _worker_loop(self):
        """Background acquisition loop."""
        consecutive_failures = 0
        while self.running:
            if not self.connected:
                if not self.open_port():
                    time.sleep(1.0)
                    continue

            # Query hardware under _serial_lock
            with self._serial_lock:
                metrics = self._query_device_serial()

            if metrics:
                consecutive_failures = 0
                now = time.time()
                # Fast state update under _state_lock (< 1 microsecond)
                with self._state_lock:
                    self.connected = True
                    self.last_update_ts = now
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
                    with self._state_lock:
                        self.connected = False
                    self.close_port()
                    time.sleep(0.5)

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
        """
        Instantaneous, non-blocking fetch of latest metrics.
        Guaranteed zero delay for web event loop.
        """
        with self._state_lock:
            if self.is_frozen and self.last_frozen_metrics:
                m = dict(self.last_frozen_metrics)
            else:
                m = dict(self.latest_metrics)
            m["connected"] = self.connected
            m["is_frozen"] = self.is_frozen
            m["port"] = self.port
            return m

    def get_history(self) -> List[Dict[str, Any]]:
        with self._state_lock:
            return list(self.history)
