from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .orchestrator import orchestrator
from pydantic import BaseModel
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app = FastAPI(title="VoltStream Week6 Vertex AI ADK")

class Query(BaseModel):
    message: str


@app.post("/chat")
def chat(req: Query):
    # ADK Agent call (Vertex handles execution)
    response = orchestrator.run(req.message)
    return {"response": response}