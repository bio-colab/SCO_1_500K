"""
SCO_1_500K Smart AI Workstation Server
Author: Antigravity Engineering
--------------------------------------
FastAPI application providing:
- Real-time WebSocket streaming of oscilloscope telemetry
- Hardware control endpoints (AUTO SET, Freeze, Diagnostics)
- AI Circuit Doctor integration
- CSV history export
- Static web interface hosting
"""

import os
import sys
import io
import csv
import json
import asyncio
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from sco_driver import SCODriver
from ai_engine import AICircuitDoctor

# Global Oscilloscope Driver instance
driver = SCODriver(port="COM3", baudrate=9600, history_len=200)

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[SERVER] Starting SCO_1_500K Hardware Telemetry Worker...")
    driver.start()
    yield
    print("[SERVER] Stopping SCO_1_500K Hardware Driver...")
    driver.stop()

app = FastAPI(title="SCO_1_500K AI Lab Workstation", lifespan=lifespan)

# Pydantic models for REST requests
class DiagnoseRequest(BaseModel):
    profile_id: str
    custom_params: Optional[Dict[str, Any]] = None

# 1. ROOT & STATIC ASSETS
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
async def get_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "index.html not found in static folder"}

# 2. STATUS & HEALTH CHECK
@app.get("/api/status")
async def get_status():
    m = driver.get_current_metrics()
    return {
        "status": "online",
        "port": driver.port,
        "baudrate": driver.baudrate,
        "connected": m.get("connected", False),
        "is_frozen": m.get("is_frozen", False),
        "last_update": m.get("formatted_time", "")
    }

# 3. REMOTE AUTO CALIBRATION
@app.post("/api/auto")
async def trigger_auto():
    success = driver.trigger_auto()
    return {"status": "ok" if success else "error"}

# 4. TOGGLE FREEZE / HOLD
@app.post("/api/freeze")
async def toggle_freeze():
    frozen = driver.toggle_freeze()
    return {"is_frozen": frozen}

# 5. CIRCUIT BENCHMARK PROFILES
@app.get("/api/profiles")
async def get_profiles():
    return AICircuitDoctor.get_profiles()

# 6. AI CIRCUIT DIAGNOSIS ENDPOINT
@app.post("/api/diagnose")
async def run_diagnose(req: DiagnoseRequest):
    metrics = driver.get_current_metrics()
    report = AICircuitDoctor.diagnose_point(req.profile_id, metrics, req.custom_params)
    return report

# 7. EXPORT DATA TO CSV
@app.get("/api/export")
async def export_csv():
    history = driver.get_history()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Timestamp", "Time", "V_MAX (V)", "V_AVE (V)", "V_PP (V)", "Frequency (Hz)"])
    for pt in history:
        writer.writerow([
            pt.get("ts", ""),
            pt.get("t", ""),
            pt.get("v_max", 0.0),
            pt.get("v_ave", 0.0),
            pt.get("v_pp", 0.0),
            pt.get("freq", 0.0)
        ])
    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=sco_oscilloscope_telemetry.csv"}
    )

# 8. WEBSOCKET REAL-TIME TELEMETRY STREAM
@app.websocket("/ws/telemetry")
async def ws_telemetry(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            metrics = driver.get_current_metrics()
            payload = {
                "type": "telemetry",
                "data": metrics
            }
            await websocket.send_text(json.dumps(payload))
            await asyncio.sleep(0.1)  # 10 Hz stream to frontend
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    except Exception as e:
        print(f"[WS ERROR] {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8765, reload=False)
