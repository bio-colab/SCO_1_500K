"""
AI Circuit Doctor - CLI Diagnostics Tool
Author: Antigravity Engineering
----------------------------------------
Interactive terminal assistant that diagnoses circuits using SCO_1_500K.
Uses the unified AICircuitDoctor engine with correct DC v_ave and v_pp analysis.
"""

import os
import sys
import time
import argparse

# Add parent directory to path to use unified engine and driver
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from sco_driver import SCODriver, find_scope_port
from ai_engine import AICircuitDoctor, CIRCUIT_PROFILES

def parse_args():
    parser = argparse.ArgumentParser(description="AI Circuit Doctor CLI")
    parser.add_argument("-p", "--port", type=str, default=None, help="Serial port (default: auto-detect)")
    parser.add_argument("-t", "--target", type=str, default="5V_RAIL", help="Target benchmark profile ID")
    parser.add_argument("--auto", action="store_true", help="Trigger AUTO calibration before diagnostic")
    return parser.parse_args()

def main():
    args = parse_args()
    port = find_scope_port(args.port) or args.port or ("COM3" if sys.platform == "win32" else "/dev/ttyUSB0")

    print("=" * 68)
    print("      🩺 AI CIRCUIT DOCTOR - OSCILLOSCOPE HARDWARE DIAGNOSTICS")
    print("=" * 68)
    print(f"[PORT] Connecting on: {port} at 9600 Baud...")

    driver = SCODriver(port=port, baudrate=9600)
    if not driver.open_port():
        print(f"[ERROR] Failed to open port {port}. Check physical connections.")
        sys.exit(1)

    try:
        profiles = CIRCUIT_PROFILES
        target_id = args.target if args.target in profiles else "5V_RAIL"
        prof = profiles[target_id]

        print(f"\n[TARGET] Testing: {prof['name_ar']} ({prof['name_en']})")
        print(f"         {prof['desc_ar']}")

        if args.auto:
            print("[ACTION] Triggering hardware AUTO SET (0x01)...")
            driver.trigger_auto()
            time.sleep(0.5)

        # Query hardware
        print("[ACTION] Querying 12 live electrical parameters (0x02)...")
        with driver._serial_lock:
            m = driver._query_device_serial()

        if not m:
            print("[ERROR] No response received from oscilloscope! Ensure scope is powered ON.")
            sys.exit(1)

        print("\n------------------- MEASURED TELEMETRY -------------------")
        print(f"  * V_MAX (Maximum)     : {m['v_max']:.3f} V")
        print(f"  * V_MIN (Minimum)     : {m['v_min']:.3f} V")
        print(f"  * V_AVE (Average DC)  : {m['v_ave']:.3f} V  <-- Primary DC Level")
        print(f"  * V_PP  (Ripple/Noise): {m['v_pp']:.3f} V   ({m['v_pp']*1000:.1f} mVpp)")
        print(f"  * Frequency           : {m['frequency_hz']:.2f} Hz")
        print(f"  * Period              : {m['period_us']:.2f} µs")
        print(f"  * Duty Cycle (+ / -)  : +{m['duty_pos_pct']}% / -{m['duty_neg_pct']}%")
        print("----------------------------------------------------------")

        # Run Doctor Diagnosis using unified engine
        report = AICircuitDoctor.diagnose_point(target_id, m)

        score = report['health_score']
        severity = report['severity']
        print(f"\n==================== AI DIAGNOSTIC REPORT ====================")
        print(f"  * Health Score : {score}%  [{severity}]")
        print(f"  * Assessment   : {report['status_title_ar']}")
        print(f"--------------------------------------------------------------")
        print("  Findings (الملاحظات الهندسية):")
        for f in report['findings']:
            print(f"    - [{f['level']}] {f['title_ar']}")
            print(f"      {f['detail_ar']}")
        
        print("\n  Recommendations (خطوات الإصلاح المقترحة):")
        for idx, r in enumerate(report['recommendations'], 1):
            print(f"    {idx}. {r['step_ar']}")
        print("==============================================================")

    finally:
        driver.close_port()

if __name__ == "__main__":
    main()
