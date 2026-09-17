"""
SCO_1_500K AI Lab Workstation Launcher
Author: Antigravity Engineering
--------------------------------------
Starts the local server and automatically launches the web interface
in the user's default browser.
"""

import sys
import time
import threading
import webbrowser
import uvicorn
import serial.tools.list_ports

PORT = 8765
URL = f"http://127.0.0.1:{PORT}"

def open_browser():
    time.sleep(1.5)
    print(f"\n[LAUNCH] Opening web workstation at {URL} ...")
    webbrowser.open(URL)

def main():
    print("=" * 65)
    print("    SCO_1_500K INTELLIGENT AI OSCILLOSCOPE WORKSTATION")
    print("=" * 65)
    
    ports = [p.device for p in serial.tools.list_ports.comports()]
    print(f"[STATUS] Detected serial ports: {ports}")
    if "COM3" in ports:
        print("[STATUS] Found SCO_1_500K adapter on COM3 - Ready!")
    else:
        print("[WARNING] COM3 not detected! Check USB-to-TTL adapter connection.")

    print(f"[STATUS] Starting web server at {URL} ...")
    
    # Open browser in a separate thread
    threading.Thread(target=open_browser, daemon=True).start()

    # Start Uvicorn web server
    uvicorn.run("app:app", host="127.0.0.1", port=PORT, log_level="info")

if __name__ == "__main__":
    main()
