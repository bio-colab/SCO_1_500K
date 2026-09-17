"""
AI Circuit Doctor - Intelligent Hardware Fault Diagnosis Assistant
------------------------------------------------------------------
Uses the SCO_1_500K oscilloscope to diagnose circuit test points,
detect electrical anomalies, power supply ripples, missing clocks, and shorts.
"""

import sys
import time
import json
from sco_oscilloscope import SCO1Oscilloscope

CIRCUIT_BENCHMARKS = {
    "1": {
        "name": "5V Power Rail (VCC)",
        "expected_v": 5.0,
        "tolerance_pct": 5.0,
        "max_ripple_v": 0.150,
        "type": "DC"
    },
    "2": {
        "name": "3.3V Power Rail / LDO",
        "expected_v": 3.3,
        "tolerance_pct": 5.0,
        "max_ripple_v": 0.080,
        "type": "DC"
    },
    "3": {
        "name": "12V Power Rail / Automotive",
        "expected_v": 12.0,
        "tolerance_pct": 10.0,
        "max_ripple_v": 0.400,
        "type": "DC"
    },
    "4": {
        "name": "Clock / PWM / Oscillator",
        "type": "AC_SWITCHING"
    },
    "5": {
        "name": "General Test Point / Custom Probe",
        "type": "CUSTOM"
    }
}

def diagnose(benchmark: dict, m: dict) -> list:
    findings = []
    b_type = benchmark.get("type")
    vmax = m.get("v_max_v", 0.0)
    vmin = m.get("v_min_v", 0.0)
    vpp = m.get("v_pp_v", 0.0)
    vave = m.get("v_ave_v", 0.0)
    freq = m.get("frequency_hz", 0)

    if b_type == "DC":
        exp_v = benchmark["expected_v"]
        tol = benchmark["tolerance_pct"]
        max_ripple = benchmark["max_ripple_v"]
        min_allowed = exp_v * (1.0 - tol / 100.0)
        max_allowed = exp_v * (1.0 + tol / 100.0)

        # Voltage level check
        if vmax < 0.2 and vave < 0.2:
            findings.append(f"[CRITICAL] Rail is DEAD (0V). Possible short-to-ground, open fuse, or disabled regulator.")
        elif vmax < min_allowed:
            findings.append(f"[WARNING] Voltage SAG detected: measured {vmax:.2f}V, expected {exp_v:.2f}V (under minimum {min_allowed:.2f}V). Check for heavy loading or failing regulator.")
        elif vmax > max_allowed:
            findings.append(f"[CRITICAL] Voltage OVER-VOLTAGE detected: measured {vmax:.2f}V, exceeds {max_allowed:.2f}V. Risk of frying ICs! Regulator feedback loop failure.")
        else:
            findings.append(f"[PASS] DC voltage is nominal: {vmax:.2f}V (within +/-{tol}% of {exp_v:.2f}V).")

        # Ripple check
        if vpp > max_ripple:
            findings.append(f"[ALERT] Excessive RIPPLE detected ({vpp*1000:.1f} mVpp > {max_ripple*1000:.1f} mV limit). High likelihood of dried/failed filter capacitors (bad ESR).")
        else:
            findings.append(f"[PASS] Power rail noise/ripple is clean ({vpp*1000:.1f} mVpp).")

    elif b_type == "AC_SWITCHING":
        if freq == 0 or vpp < 0.1:
            findings.append(f"[CRITICAL] No clock/switching activity detected! Frequency is 0 Hz or flatline. Crystal stopped, MCU halted, or PWM driver inactive.")
        else:
            findings.append(f"[PASS] Active switching detected at {freq} Hz with {vpp:.2f} Vpp amplitude.")
            findings.append(f"[INFO] Duty Cycle: +{m.get('duty_cycle_pos_pct', 0)}% / -{m.get('duty_cycle_neg_pct', 0)}%.")

    return findings

def main():
    print("==================================================================")
    print("      AI CIRCUIT DOCTOR - OSCILLOSCOPE HARDWARE DIAGNOSTICS       ")
    print("==================================================================")

    scope = SCO1Oscilloscope(port="COM3", baudrate=9600)
    if not scope.connect():
        sys.exit(1)

    try:
        print("Select the circuit point you are testing:")
        for k, v in CIRCUIT_BENCHMARKS.items():
            print(f"  [{k}] {v['name']}")

        choice = "1"  # default
        if len(sys.argv) > 1:
            choice = sys.argv[1]
        
        benchmark = CIRCUIT_BENCHMARKS.get(choice, CIRCUIT_BENCHMARKS["1"])
        print(f"\n[TARGET] Testing: {benchmark['name']}...")
        
        # Trigger Auto for best signal view
        scope.trigger_auto()
        time.sleep(0.5)

        # Get measurements
        report = scope.run_ai_diagnostic_snapshot()
        m = report.get("measurements", {})
        
        print("\n------------------- MEASURED TELEMETRY -------------------")
        print(f"  Max Voltage   : {m.get('v_max_v', 0):.3f} V")
        print(f"  Min Voltage   : {m.get('v_min_v', 0):.3f} V")
        print(f"  Vpp (Ripple)  : {m.get('v_pp_v', 0):.3f} V")
        print(f"  Frequency     : {m.get('frequency_hz', 0)} Hz")
        print(f"  Period        : {m.get('period', 0)}")
        print("----------------------------------------------------------")

        # Run Doctor diagnosis
        findings = diagnose(benchmark, m)
        print("\n================== AI DIAGNOSTIC REPORT ==================")
        for f in findings:
            print(f"  {f}")
        print("==========================================================")

    finally:
        scope.close()

if __name__ == "__main__":
    main()
