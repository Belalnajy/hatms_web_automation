from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import asyncio
import os

app = FastAPI(title="HATMS Web Automation API")

class RunPayload(BaseModel):
    cookie: str

@app.post("/api/index")
async def run_script(payload: RunPayload):
    cookie = payload.cookie
    
    async def log_generator():
        # Clean cookie format
        clean_cookie = cookie.replace("MoodleSession=", "").strip()
        
        # Absolute path calculation to the script
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        script_path = os.path.join(base_dir, "hatms_full_automation.py")

        # Start subprocess
        process = await asyncio.create_subprocess_exec(
            "python3", script_path, "--cookie", clean_cookie,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=base_dir,
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

# No uvicorn required for Vercel Serverless
