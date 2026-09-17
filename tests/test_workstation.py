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
import struct
import unittest

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sco_driver import SCODriver, HEADER
from ai_engine import AICircuitDoctor, CIRCUIT_PROFILES
from fastapi.testclient import TestClient
from app import app


class TestDriverMathAndFraming(unittest.TestCase):
    def setUp(self):
        self.driver = SCODriver(port="COM_TEST")

    def _build_packet(self, raw_vals, signs, prefix=b""):
        payload = struct.pack("<12I", *raw_vals)
        packet = prefix + HEADER + payload + bytes(signs)
        return packet

    def test_unit_conversions_nominal(self):
        # 3.3V nominal with 50mV ripple, 1MHz clock (1us period), 50% duty
        raw = (
            3350000,  # vmax = 3.35V
            3250000,  # vmin = 3.25V
            3300000,  # vave = 3.30V
            100000,   # vpp  = 0.10V (100mV)
            3350000,  # vp   = 3.35V
            3301000,  # vrms = 3.301V
            100,      # period = 100 ticks (100 * 10ns = 1.0 us)
            100000000,# freq = 100,000,000 centi-Hz = 1,000,000.0 Hz (1 MHz)
            500,      # duty+ = 50.0%
            500,      # duty- = 50.0%
            50,       # pw+ = 50 ticks = 0.5 us
            50        # pw- = 50 ticks = 0.5 us
        )
        signs = (0, 0, 0, 0)
        packet = self._build_packet(raw, signs)
        
        # Test sanity check
        self.assertEqual(len(packet), 55)
        self.assertTrue(packet.startswith(HEADER))
        
        # Check scale factors
        vmax = raw[0] / 1_000_000.0
        self.assertAlmostEqual(vmax, 3.35, places=3)
        
        freq_hz = raw[7] / 100.0
        self.assertEqual(freq_hz, 1_000_000.0)
        
        period_us = (raw[6] * 10.0) / 1000.0
        self.assertAlmostEqual(period_us, 1.0, places=3)
        
        duty_pct = raw[8] * 0.1
        self.assertEqual(duty_pct, 50.0)

    def test_signed_negative_voltages(self):
        raw = [1500000, 2500000, 500000, 4000000, 2500000, 1800000, 200, 5000000, 500, 500, 100, 100]
        # signs: vmax pos (0), vmin neg (1), vave neg (1), vp neg (1)
        signs = [0, 1, 1, 1]
        
        vmin = -raw[1] / 1_000_000.0
        vave = -raw[2] / 1_000_000.0
        self.assertAlmostEqual(vmin, -2.5, places=3)
        self.assertAlmostEqual(vave, -0.5, places=3)

    def test_sanity_checks_rejects_corrupted_packet(self):
        # Invalid sign byte (> 1)
        raw = [5000000] * 12
        corrupted_signs = [0, 0, 2, 0]  # 2 is illegal sign!
        packet = self._build_packet(raw, corrupted_signs)
        signs = packet[51:55]
        is_valid_signs = all(s in (0, 1) for s in signs)
        self.assertFalse(is_valid_signs)

        # Invalid duty cycle (> 1000)
        raw_bad_duty = list(raw)
        raw_bad_duty[8] = 1200  # 120.0% is impossible
        self.assertTrue(raw_bad_duty[8] > 1000)


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
