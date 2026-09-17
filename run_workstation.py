"""
SCO_1_500K AI Lab Workstation Launcher
Author: Antigravity Engineering
--------------------------------------
Starts the local server and automatically launches the web interface
in the user's default browser with full cross-platform port discovery.
"""

import os
import sys
import time
import argparse
import threading
import webbrowser
import uvicorn
import serial.tools.list_ports

from sco_driver import find_scope_port

def parse_args():
    parser = argparse.ArgumentParser(description="SCO_1_500K Smart AI Workstation")
    parser.add_argument("-p", "--port", type=str, default=None, help="Serial port (e.g. COM3, /dev/ttyUSB0)")
    parser.add_argument("-w", "--web-port", type=int, default=8765, help="Web server port (default: 8765)")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically open the browser")
    return parser.parse_args()

def open_browser(url: str):
    time.sleep(1.5)
    print(f"\n[LAUNCH] Opening web workstation in your browser: {url} ...")
    webbrowser.open(url)

def main():
    args = parse_args()
    url = f"http://127.0.0.1:{args.web_port}"

    print("=" * 68)
    print("      ⚡ SCO_1_500K INTELLIGENT AI OSCILLOSCOPE WORKSTATION ⚡")
    print("=" * 68)
    print(f"[SYSTEM] OS: {sys.platform} | Python: {sys.version.split()[0]}")

    # Discover or select serial port
    detected_port = find_scope_port(args.port)
    if detected_port:
        os.environ["SCO_PORT"] = detected_port
        print(f"[PORT] Auto-detected SCO_1_500K hardware on port: \033[92m{detected_port}\033[0m")
    else:
        fallback = "COM3" if sys.platform == "win32" else "/dev/ttyUSB0"
        os.environ["SCO_PORT"] = fallback
        print(f"[PORT] \033[93mNo UART bridge auto-detected. Defaulting to fallback: {fallback}\033[0m")
        print("       (Connect your USB-to-TTL adapter or specify with: --port <PORT>)")

    print(f"[SERVER] Starting high-performance FastAPI service at {url} ...")

    if not args.no_browser:
        threading.Thread(target=open_browser, args=(url,), daemon=True).start()

    os.environ["PORT"] = str(args.web_port)
    uvicorn.run("app:app", host="127.0.0.1", port=args.web_port, log_level="info")

if __name__ == "__main__":
    main()
