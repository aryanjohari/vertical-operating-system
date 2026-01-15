# backend/main.py
from fastapi import FastAPI, HTTPException
from backend.core.models import AgentInput, AgentOutput
from backend.core.kernel import kernel
import uvicorn

# Initialize the App
app = FastAPI(
    title="Apex Sovereign OS", 
    version="1.0",
    description="The Vertical Operating System for Revenue & Automation"
)

@app.get("/")
def health_check():
    """Ping this to check if the OS is alive."""
    return {
        "status": "online", 
        "system": "Apex Kernel", 
        "version": "1.0",
        "loaded_agents": list(kernel.agents.keys())
    }

@app.post("/api/run", response_model=AgentOutput)
async def run_command(payload: AgentInput):
    """
    The Single Entry Point.
    Receives a Universal Packet -> Dispatches to Kernel -> Returns Result.
    """
    try:
        result = await kernel.dispatch(payload)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    # Dev Mode: Runs on localhost:8000
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)