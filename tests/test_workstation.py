"""
SCO_1_500K Automated Verification Test Suite
Author: Antigravity Engineering
--------------------------------------------
Comprehensive tests covering:
1. Mathematical scaling and SI unit conversions
2. Serial packet parsing and heuristic sanity validation
3. Frame synchronization & garbage recovery
4. AI Circuit Doctor diagnostic heuristics (DC ave, ripple, weak clock, overshoot)
5. Offline hardware state guards
6. FastAPI REST endpoints & Pydantic input validation
"""

import sys
import os
import time
import struct
import unittest

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sco_driver import SCODriver, HEADER
from ai_engine import AICircuitDoctor, CIRCUIT_PROFILES
from fastapi.testclient import TestClient
from app import app


class FakeSerial:
    """
    Minimal pyserial stand-in so the tests exercise the REAL driver code path
    (framing, resync, scaling, clamping) instead of re-implementing the
    arithmetic inside the assertions.
    """

    def __init__(self, data: bytes = b""):
        self.is_open = True
        self.buf = bytearray(data)
        self.written = bytearray()

    def feed(self, data: bytes):
        self.buf.extend(data)

    def reset_input_buffer(self):
        pass

    def reset_output_buffer(self):
        pass

    def write(self, data):
        self.written.extend(data)
        return len(data)

    def read(self, n=1):
        if not self.buf:
            time.sleep(0.01)  # emulate a blocking read so tests do not busy-spin
            return b""
        out = bytes(self.buf[:n])
        del self.buf[:n]
        return out

    def close(self):
        self.is_open = False


def build_packet(raw_vals, signs=(0, 0, 0, 0), prefix=b"") -> bytes:
    return prefix + HEADER + struct.pack("<12I", *raw_vals) + bytes(signs)


NOMINAL_RAW = (
    3350000,    # vmax = 3.35 V
    3250000,    # vmin = 3.25 V
    3300000,    # vave = 3.30 V
    100000,     # vpp  = 0.10 V
    3350000,    # vp   = 3.35 V
    3301000,    # vrms = 3.301 V
    100,        # period = 100 ticks x 10ns = 1.0 us
    100000000,  # freq  = 1e8 centi-Hz = 1.0 MHz
    500,        # duty+ = 50.0 %
    500,        # duty- = 50.0 %
    50,         # pw+   = 0.5 us
    50,         # pw-   = 0.5 us
)


class TestDriverMathAndFraming(unittest.TestCase):
    def setUp(self):
        self.driver = SCODriver(port="COM_TEST")

    def _build_packet(self, raw_vals, signs, prefix=b""):
        payload = struct.pack("<12I", *raw_vals)
        packet = prefix + HEADER + payload + bytes(signs)
        return packet

    def _driver_with(self, data: bytes) -> SCODriver:
        drv = SCODriver(port="COM_TEST")
        drv.ser = FakeSerial(data)
        return drv

    def test_unit_conversions_through_real_driver(self):
        """Scaling must be asserted on the driver's OUTPUT, not recomputed here."""
        drv = self._driver_with(build_packet(NOMINAL_RAW))
        m = drv.read_once()
        self.assertIsNotNone(m)
        self.assertAlmostEqual(m["v_max"], 3.35, places=3)
        self.assertAlmostEqual(m["v_ave"], 3.30, places=3)
        self.assertAlmostEqual(m["v_pp"], 0.10, places=3)
        self.assertEqual(m["frequency_hz"], 1_000_000.0)
        self.assertAlmostEqual(m["period_us"], 1.0, places=3)
        self.assertEqual(m["duty_pos_pct"], 50.0)
        self.assertAlmostEqual(m["pw_pos_us"], 0.5, places=3)
        self.assertEqual(m["overflow"], [])

    def test_request_command_is_sent(self):
        drv = self._driver_with(build_packet(NOMINAL_RAW))
        drv.read_once()
        self.assertEqual(bytes(drv.ser.written), bytes([0x02, 0x02]))

    def test_frame_resync_drops_leading_garbage(self):
        noise = b"\x00\xff\xab\xcd" * 7  # includes a partial header
        drv = self._driver_with(build_packet(NOMINAL_RAW, prefix=noise))
        m = drv.read_once()
        self.assertIsNotNone(m)
        self.assertAlmostEqual(m["v_max"], 3.35, places=3)

    def test_negative_voltages_through_real_driver(self):
        raw = [1500000, 2500000, 500000, 4000000, 2500000, 1800000,
               200, 5000000, 500, 500, 100, 100]
        drv = self._driver_with(build_packet(raw, signs=(0, 1, 1, 1)))
        m = drv.read_once()
        self.assertAlmostEqual(m["v_max"], 1.5, places=3)
        self.assertAlmostEqual(m["v_min"], -2.5, places=3)
        self.assertAlmostEqual(m["v_ave"], -0.5, places=3)
        self.assertAlmostEqual(m["v_peak"], -2.5, places=3)

    def test_illegal_sign_byte_rejects_frame(self):
        raw = [5000000] * 12
        drv = self._driver_with(build_packet(raw, signs=(0, 0, 2, 0)))
        self.assertIsNone(drv.read_once())

    def test_overflow_duty_is_clamped_not_dropped(self):
        """
        The firmware has explicit per-field overflow states. An out-of-range duty
        must NOT discard the frame - that made a healthy device look disconnected.
        """
        raw = list(NOMINAL_RAW)
        raw[8] = 0xFFFFFFFF
        drv = self._driver_with(build_packet(raw))
        m = drv.read_once()
        self.assertIsNotNone(m, "valid frame was discarded because of one overflow field")
        self.assertEqual(m["duty_pos_pct"], 100.0)
        self.assertIn("duty_pos", m["overflow"])
        self.assertAlmostEqual(m["v_max"], 3.35, places=3)

    def test_overflow_voltage_is_clamped_to_instrument_range(self):
        raw = list(NOMINAL_RAW)
        raw[0] = 4_000_000_000  # 4000 V, far beyond the +/-400V range
        drv = self._driver_with(build_packet(raw))
        m = drv.read_once()
        self.assertIsNotNone(m)
        self.assertEqual(m["v_max"], 400.0)
        self.assertIn("v_max", m["overflow"])

    def test_truncated_frame_returns_none(self):
        drv = self._driver_with(build_packet(NOMINAL_RAW)[:40])
        self.assertIsNone(drv.read_once())


class TestAICircuitDoctor(unittest.TestCase):
    def test_nominal_5v_rail(self):
        m = {"v_max": 5.05, "v_ave": 5.00, "v_pp": 0.04, "frequency_hz": 0, "connected": True}
        res = AICircuitDoctor.diagnose_point("5V_RAIL", m)
        self.assertEqual(res["severity"], "NORMAL")
        self.assertGreaterEqual(res["health_score"], 85)
        self.assertIn("سليمة", res["status_title_ar"])

    def test_collapsed_5v_rail_with_high_ripple(self):
        # User Reviewer exact failing case: V_max = 5.05V | V_ave = 4.20V | V_pp = 1.55V
        m = {"v_max": 5.05, "v_ave": 4.20, "v_pp": 1.55, "frequency_hz": 100000, "connected": True}
        res = AICircuitDoctor.diagnose_point("5V_RAIL", m)
        # Must be flagged CRITICAL due to severe sag (16% drop)
        self.assertEqual(res["severity"], "CRITICAL")
        self.assertLessEqual(res["health_score"], 35)
        self.assertIn("هبوط حاد", res["status_title_ar"])

    def test_dead_rail_0v(self):
        m = {"v_max": 0.05, "v_ave": 0.02, "v_pp": 0.01, "frequency_hz": 0, "connected": True}
        res = AICircuitDoctor.diagnose_point("5V_RAIL", m)
        self.assertEqual(res["severity"], "CRITICAL")
        self.assertEqual(res["health_score"], 0)
        self.assertIn("0V", res["status_title_ar"])

    def test_transient_overshoot_not_fatal(self):
        # Nominal average 5.0V with transient spikes to 6.3V
        m = {"v_max": 6.30, "v_ave": 5.02, "v_pp": 0.06, "frequency_hz": 0, "connected": True}
        res = AICircuitDoctor.diagnose_point("5V_RAIL", m)
        # Must NOT be CRITICAL overvoltage
        self.assertNotEqual(res["severity"], "CRITICAL")
        levels = [f["level"] for f in res["findings"]]
        self.assertIn("INFO", levels)

    def test_weak_clock_amplitude(self):
        # Crystal oscillating at 16MHz, but only 0.25 Vpp (below min_amplitude_v 0.5V)
        m = {"v_max": 0.3, "v_ave": 0.15, "v_pp": 0.25, "frequency_hz": 16_000_000, "connected": True}
        res = AICircuitDoctor.diagnose_point("CLOCK_XTAL", m)
        self.assertEqual(res["severity"], "WARNING")
        self.assertIn("ضعيف", res["status_title_ar"])

    def test_clock_flatline_0hz(self):
        m = {"v_max": 0.0, "v_ave": 0.0, "v_pp": 0.0, "frequency_hz": 0, "connected": True}
        res = AICircuitDoctor.diagnose_point("CLOCK_XTAL", m)
        self.assertEqual(res["severity"], "CRITICAL")
        self.assertEqual(res["health_score"], 0)
        self.assertIn("متوقفة", res["status_title_ar"])

    def test_hardware_offline_state(self):
        # When connected is False, AI must not diagnose short circuit
        m = {"v_max": 0.0, "v_ave": 0.0, "v_pp": 0.0, "frequency_hz": 0, "connected": False}
        res = AICircuitDoctor.diagnose_point("5V_RAIL", m)
        self.assertEqual(res["severity"], "OFFLINE")
        self.assertIn("غير متصل", res["status_title_ar"])

    def test_invalid_custom_params_fallback(self):
        m = {"v_max": 5.0, "v_ave": 5.0, "v_pp": 0.05, "frequency_hz": 0, "connected": True}
        # Non-numeric values must not raise ValueError
        res = AICircuitDoctor.diagnose_point("CUSTOM", m, {"expected_v": "invalid", "tolerance_pct": "abc", "max_ripple_v": None})
        self.assertEqual(res["severity"], "NORMAL")


    def test_12v_rail_just_below_tolerance_is_moderate(self):
        """
        12V profile has a 10% tolerance. 10.79V is 0.01V under the window - a
        marginal sag, not a critical fault. The old fixed 10% cut-off made the
        moderate tier unreachable for every profile with tolerance >= 10%.
        """
        m = {"v_max": 10.85, "v_ave": 10.79, "v_pp": 0.20, "frequency_hz": 0, "connected": True}
        res = AICircuitDoctor.diagnose_point("12V_RAIL", m)
        self.assertEqual(res["severity"], "WARNING")
        self.assertIn("انخفاض طفيف", res["status_title_ar"])

    def test_12v_rail_deep_sag_is_still_critical(self):
        m = {"v_max": 9.20, "v_ave": 9.00, "v_pp": 0.20, "frequency_hz": 0, "connected": True}
        res = AICircuitDoctor.diagnose_point("12V_RAIL", m)
        self.assertEqual(res["severity"], "CRITICAL")
        self.assertIn("هبوط حاد", res["status_title_ar"])

    def test_headline_never_contradicts_its_own_severity(self):
        """Moderate sag + heavy ripple used to yield 'عطل حرج: انخفاض طفيف'."""
        m = {"v_max": 4.80, "v_ave": 4.60, "v_pp": 0.40, "frequency_hz": 0, "connected": True}
        res = AICircuitDoctor.diagnose_point("5V_RAIL", m)
        self.assertEqual(res["severity"], "CRITICAL")
        self.assertNotIn("عطل حرج", res["status_title_ar"])
        self.assertIn("تدهور مركّب", res["status_title_ar"])

    def test_english_title_contains_no_arabic(self):
        cases = [
            ("5V_RAIL", {"v_max": 5.10, "v_ave": 5.00, "v_pp": 0.35}),
            ("5V_RAIL", {"v_max": 4.80, "v_ave": 4.60, "v_pp": 0.40}),
            ("12V_RAIL", {"v_max": 10.85, "v_ave": 10.79, "v_pp": 0.20}),
            ("1V8_RAIL", {"v_max": 1.72, "v_ave": 1.70, "v_pp": 0.02}),
            ("CLOCK_XTAL", {"v_max": 0.30, "v_ave": 0.15, "v_pp": 0.25, "frequency_hz": 16_000_000}),
        ]
        for pid, metrics in cases:
            metrics.setdefault("frequency_hz", 0)
            metrics["connected"] = True
            res = AICircuitDoctor.diagnose_point(pid, metrics)
            title_en = res["status_title_en"]
            self.assertTrue(
                all(ord(ch) < 0x0590 for ch in title_en),
                f"Arabic text leaked into status_title_en for {pid}: {title_en}"
            )

    def test_moderate_overvoltage_is_not_a_fire_alarm(self):
        # 12V rail at 13.4V: above tolerance, below the 2x-tolerance danger line
        m = {"v_max": 13.5, "v_ave": 13.4, "v_pp": 0.20, "frequency_hz": 0, "connected": True}
        res = AICircuitDoctor.diagnose_point("12V_RAIL", m)
        self.assertEqual(res["severity"], "WARNING")

    def test_severe_overvoltage_is_critical(self):
        m = {"v_max": 6.60, "v_ave": 6.50, "v_pp": 0.05, "frequency_hz": 0, "connected": True}
        res = AICircuitDoctor.diagnose_point("5V_RAIL", m)
        self.assertEqual(res["severity"], "CRITICAL")
        self.assertIn("ارتفاع خطر", res["status_title_ar"])


    def test_overflow_flag_is_surfaced_to_the_technician(self):
        m = {"v_max": 5.06, "v_ave": 5.00, "v_pp": 0.05, "frequency_hz": 0,
             "connected": True, "overflow": ["duty_pos"]}
        res = AICircuitDoctor.diagnose_point("5V_RAIL", m)
        titles = [f["title_ar"] for f in res["findings"]]
        self.assertTrue(any("Overflow" in t for t in titles))

    def test_clamped_voltage_downgrades_the_verdict(self):
        m = {"v_max": 400.0, "v_ave": 5.00, "v_pp": 0.05, "frequency_hz": 0,
             "connected": True, "overflow": ["v_max"]}
        res = AICircuitDoctor.diagnose_point("5V_RAIL", m)
        self.assertEqual(res["severity"], "WARNING")


class TestFastAPIServer(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_api_status(self):
        res = self.client.get("/api/status")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("status", data)
        self.assertIn("port", data)

    def test_api_profiles(self):
        res = self.client.get("/api/profiles")
        self.assertEqual(res.status_code, 200)
        profiles = res.json()
        self.assertIsInstance(profiles, list)
        self.assertGreater(len(profiles), 5)

    def test_api_diagnose_valid(self):
        res = self.client.post("/api/diagnose", json={"profile_id": "5V_RAIL"})
        self.assertEqual(res.status_code, 200)
        report = res.json()
        self.assertIn("health_score", report)
        self.assertIn("status_title_ar", report)

    def test_api_diagnose_pydantic_rejects_string(self):
        # String for expected_v
        res = self.client.post("/api/diagnose", json={
            "profile_id": "CUSTOM",
            "custom_params": {"expected_v": "abc"}
        })
        self.assertEqual(res.status_code, 422)

    def test_api_diagnose_pydantic_rejects_negative(self):
        # Negative expected_v
        res = self.client.post("/api/diagnose", json={
            "profile_id": "CUSTOM",
            "custom_params": {"expected_v": -12.0}
        })
        self.assertEqual(res.status_code, 422)


if __name__ == "__main__":
    unittest.main()
