"""
SCO_1_500K Oscilloscope Python Driver & AI Diagnostics Bridge
-------------------------------------------------------------
Communicates with the SCO_1_500K handheld oscilloscope via serial UART.
Parses real-time electrical parameters, triggers AUTO adjustment,
and formats telemetry for AI hardware fault diagnosis.
"""

import sys
import time
import struct
import json
from typing import Dict, Any, Optional

import serial
import serial.tools.list_ports

HEADER = bytes([0xAB, 0xCD, 0xEF])

class SCO1Oscilloscope:
    def __init__(self, port: str = "COM3", baudrate: int = 9600, timeout: float = 1.0):
        self.port_name = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser: Optional[serial.Serial] = None

    def connect(self) -> bool:
        try:
            print(f"[INFO] Connecting to SCO_1_500K on {self.port_name} at {self.baudrate} baud...")
            self.ser = serial.Serial(
                port=self.port_name,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.timeout
            )
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            time.sleep(0.1)
            print(f"[SUCCESS] Connected successfully to {self.port_name}!\n")
            return True
        except Exception as e:
            print(f"[ERROR] Failed to open {self.port_name}: {e}")
            self.ser = None
            return False

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            self.ser = None

    def trigger_auto(self) -> bool:
        """Triggers AUTO calibration/adjustment on the oscilloscope."""
        if not self.ser:
            return False
        self.ser.reset_input_buffer()
        self.ser.write(bytes([0x01, 0x01]))
        time.sleep(0.5)
        print("[ACTION] Triggered AUTO adjustment on oscilloscope.")
        return True

    def get_parameters(self) -> Optional[Dict[str, Any]]:
        """Queries the 12 live electrical parameters from the oscilloscope."""
        if not self.ser:
            return None

        self.ser.reset_input_buffer()
        # Send 0x02 request
        self.ser.write(bytes([0x02, 0x02]))

        # Read 55 bytes
        data = self.ser.read(55)
        if len(data) != 55:
            # Retry once
            time.sleep(0.1)
            data = self.ser.read(55)
            if len(data) != 55:
                return None

        if data[:3] != HEADER:
            # Header mismatch
            return None

        payload = data[3:51]
        signs = data[51:55]
        raw = struct.unpack('<12I', payload)

        def to_val(val: int, is_neg: int, scale: float = 1.0) -> float:
            signed = -val if is_neg == 1 else val
            return round(signed * scale, 3)

        # Scale factors according to SCO1 firmware representation
        vmax = to_val(raw[0], signs[0], 0.001)   # in Volts
        vmin = to_val(raw[1], signs[1], 0.001)   # in Volts
        vave = to_val(raw[2], signs[2], 0.001)   # in Volts
        vpp  = round(raw[3] * 0.001, 3)          # in Volts
        vp   = to_val(raw[4], signs[3], 0.001)   # in Volts
        vrms = round(raw[5] * 0.001, 3)          # in Volts

        period = raw[6]  # Period
        freq   = raw[7]  # Frequency
        pdut   = round(raw[8] * 0.1, 1)   # Duty + %
        ddut   = round(raw[9] * 0.1, 1)   # Duty - %
        ppw    = raw[10] # Pulse width +
        dpw    = raw[11] # Pulse width -

        return {
            "v_max_v": vmax,
            "v_min_v": vmin,
            "v_ave_v": vave,
            "v_pp_v": vpp,
            "v_peak_v": vp,
            "v_rms_v": vrms,
            "period": period,
            "frequency_hz": freq,
            "duty_cycle_pos_pct": pdut,
            "duty_cycle_neg_pct": ddut,
            "pulse_width_pos": ppw,
            "pulse_width_neg": dpw,
            "raw_hex": data.hex()
        }

    def run_ai_diagnostic_snapshot(self) -> Dict[str, Any]:
        """Captures real-time telemetry and assesses preliminary fault conditions."""
        params = self.get_parameters() or {}

        # AI Heuristic Analysis
        fault_flags = []
        freq = params.get("frequency_hz", 0)
        vpp = params.get("v_pp_v", 0)
        vmax = params.get("v_max_v", 0)
        vrms = params.get("v_rms_v", 0)

        if vpp == 0 and vmax > 0:
            fault_flags.append("DC_VOLTAGE_RAIL: Stable DC level detected without AC ripple.")
        elif vpp > 0 and freq > 0:
            fault_flags.append("ACTIVE_AC_SIGNAL: Oscillating signal detected.")
        elif vpp == 0 and vmax == 0:
            fault_flags.append("NO_SIGNAL_CONNECTED: Probe floating or input grounded (0V).")

        report = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "measurements": params,
            "ai_preliminary_diagnostics": fault_flags
        }

        with open("scope_ai_report.json", "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        return report


def main():
    print("==================================================================")
    print("         SCO_1_500K LIVE OSCILLOSCOPE & AI DIAGNOSTICS HUB        ")
    print("==================================================================")

    scope = SCO1Oscilloscope(port="COM3", baudrate=9600)
    if not scope.connect():
        sys.exit(1)

    try:
        report = scope.run_ai_diagnostic_snapshot()
        m = report.get("measurements", {})

        print("---------------- LIVE ELECTRICAL MEASUREMENTS ----------------")
        print(f"  * V_MAX (Maximum)     : {m.get('v_max_v', 0):.3f} V")
        print(f"  * V_MIN (Minimum)     : {m.get('v_min_v', 0):.3f} V")
        print(f"  * V_AVE (Average)     : {m.get('v_ave_v', 0):.3f} V")
        print(f"  * V_PP  (Peak-to-Peak): {m.get('v_pp_v', 0):.3f} V")
        print(f"  * V_RMS (Effective)   : {m.get('v_rms_v', 0):.3f} V")
        print(f"  * Period (Cycle)      : {m.get('period', 0)}")
        print(f"  * Frequency (Raw/Hz)  : {m.get('frequency_hz', 0)}")
        print(f"  * +Duty Cycle         : {m.get('duty_cycle_pos_pct', 0)} %")
        print(f"  * -Duty Cycle         : {m.get('duty_cycle_neg_pct', 0)} %")
        print("--------------------------------------------------------------")
        print(f"[AI Assessment] {report.get('ai_preliminary_diagnostics')}")
        print("\n[SUCCESS] Telemetry snapshot saved to 'scope_ai_report.json'!")

    finally:
        scope.close()

if __name__ == '__main__':
    main()
