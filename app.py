from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import subprocess
import asyncio
import os

app = FastAPI(title="HATMS Web Automation")

# Mount aesthetic static files
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def get_index():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

class RunPayload(BaseModel):
    cookie: str

@app.post("/api/run")
async def run_script(payload: RunPayload):
    cookie = payload.cookie
    
    async def log_generator():
        # Clean cookie format
        clean_cookie = cookie.replace("MoodleSession=", "").strip()
        
        # Start subprocess
        process = await asyncio.create_subprocess_exec(
            "python3", "hatms_full_automation.py", "--cookie", clean_cookie,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=dict(os.environ, PYTHONUNBUFFERED="1") # Force unbuffered Python output
        )
        
        try:
            while True:
                line = await process.stdout.readline()
                if not line and process.returncode is not None:
                    break
                if line:
                    decoded_line = line.decode('utf-8', errors='replace').strip()
                    # Yield as Server-Sent Event (SSE)
                    yield f"data: {decoded_line}\n\n"
        except asyncio.CancelledError:
            process.terminate()
            raise
        finally:
            await process.wait()
            yield f"data: 🏁 Process completed.\n\n"
            
    return StreamingResponse(log_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
