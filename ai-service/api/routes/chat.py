from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import httpx

router = APIRouter()

class QueryRequest(BaseModel):
    question: str

@router.post("/internal/rag/query")
async def rag_query(request: QueryRequest):
    ollama_url = "http://localhost:11434/api/generate"
    payload = {
        "model": "qwen2.5:7b",
        "prompt": request.question,
        "stream": False
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(ollama_url, json=payload, timeout=60.0)
            response.raise_for_status()
            data = response.json()
            return {"answer": data.get("response", "")}
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Ollama request failed: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
