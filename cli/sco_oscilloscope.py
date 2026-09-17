"""
SCO_1_500K Oscilloscope CLI Telemetry Tool
Author: Antigravity Engineering
------------------------------------------
CLI utility to connect to SCO_1_500K and print real-time measurements.
Uses the unified SCODriver engine to ensure 100% mathematical consistency.
"""

import os
import sys
import time
import argparse

# Add parent directory to path to use unified sco_driver
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from sco_driver import SCODriver, find_scope_port

def parse_args():
    parser = argparse.ArgumentParser(description="SCO_1_500K CLI Monitor")
    parser.add_argument("-p", "--port", type=str, default=None, help="Serial port (default: auto-detect)")
    parser.add_argument("-b", "--baud", type=int, default=9600, help="Baud rate (default: 9600)")
    parser.add_argument("-c", "--count", type=int, default=1, help="Number of samples to read (default: 1)")
    parser.add_argument("--auto", action="store_true", help="Trigger AUTO calibration first")
    return parser.parse_args()

def main():
    args = parse_args()
    port = find_scope_port(args.port) or args.port or ("COM3" if sys.platform == "win32" else "/dev/ttyUSB0")
    
    print("=" * 66)
    print("       SCO_1_500K CLI TELEMETRY MONITOR (UNIFIED DRIVER)")
    print("=" * 66)
    print(f"[INFO] Target Port: {port} at {args.baud} Baud")

    driver = SCODriver(port=port, baudrate=args.baud)
    if not driver.open_port():
        print(f"[ERROR] Could not open serial port {port}. Check connection or permissions.")
        sys.exit(1)

    try:
        if args.auto:
            print("[ACTION] Triggering AUTO calibration (0x01 0x01)...")
            driver.trigger_auto()
            time.sleep(0.6)

        for i in range(args.count):
            # Query hardware directly using unified driver method
            with driver._serial_lock:
                m = driver._query_device_serial()

            if not m:
                print(f"[WARN] Sample {i+1}/{args.count}: No response from oscilloscope. Is it powered ON?")
                time.sleep(0.5)
                continue

            print(f"\n--- SAMPLE {i+1}/{args.count} [{m['formatted_time']}] ---")
            print(f"  * V_MAX (Maximum)     : {m['v_max']:.3f} V  ({m['v_max']*1000.0:.1f} mV)")
            print(f"  * V_MIN (Minimum)     : {m['v_min']:.3f} V  ({m['v_min']*1000.0:.1f} mV)")
            print(f"  * V_AVE (Average DC)  : {m['v_ave']:.3f} V  ({m['v_ave']*1000.0:.1f} mV)")
            print(f"  * V_PP  (Ripple/Noise): {m['v_pp']:.3f} V   ({m['v_pp']*1000.0:.1f} mVpp)")
            print(f"  * V_RMS (Effective)   : {m['v_rms']:.3f} V  ({m['v_rms']*1000.0:.1f} mV)")
            
            # Frequency formatting
            freq = m['frequency_hz']
            if freq >= 1_000_000:
                print(f"  * Frequency           : {freq/1_000_000.0:.3f} MHz ({freq:.1f} Hz)")
            elif freq >= 1_000:
                print(f"  * Frequency           : {freq/1_000.0:.2f} kHz ({freq:.1f} Hz)")
            else:
                print(f"  * Frequency           : {freq:.2f} Hz")

            # Period formatting
            period = m['period_us']
            if period >= 1000:
                print(f"  * Period              : {period/1000.0:.3f} ms ({period:.2f} µs)")
            else:
                print(f"  * Period              : {period:.2f} µs")

            print(f"  * Duty Cycle (+ / -)  : +{m['duty_pos_pct']}% / -{m['duty_neg_pct']}%")
            print(f"  * Pulse Width (+ / -) : +{m['pw_pos_us']:.2f} µs / -{m['pw_neg_us']:.2f} µs")
            
            if i < args.count - 1:
                time.sleep(0.5)

    finally:
        driver.close_port()
        print("\n[INFO] Connection closed.")

if __name__ == "__main__":
    main()
