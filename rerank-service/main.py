"""
远程重排微服务（部署到 GPU 服务器）

说明：
    Ollama 官方没有 /api/rerank 接口，因此重排序需要独立部署。
    本服务在远程 GPU 服务器上用 sentence-transformers 加载交叉编码器
    （bge-reranker-v2-m3，中文效果好），暴露 HTTP 接口供本地 ai-service 调用。
    本地 ai-service 只发 HTTP 请求，不消耗本地 CPU/内存。

启动（在远程 GPU 服务器上）：
    pip install -r requirements.txt
    uvicorn main:app --host 0.0.0.0 --port 8001

首次启动会自动从 HuggingFace 下载模型（约 1.3GB），之后加载到显存。
"""

import os
from typing import List, Optional

from fastapi import FastAPI
from pydantic import BaseModel

from sentence_transformers import CrossEncoder
import torch

app = FastAPI(title="Aegis Rerank Service", version="1.0.0")

# 模型与设备配置（可用环境变量覆盖）
_MODEL_CANDIDATES = [
    os.getenv("RERANK_MODEL", "BAAI/bge-reranker-v2-m3"),
    "BAAI/bge-reranker-large",
    "BAAI/bge-reranker-base",
]
_DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
_MAX_LEN = int(os.getenv("RERANK_MAX_LEN", "512"))

_model = None
_loaded_model_name = ""


class RerankRequest(BaseModel):
    query: str
    documents: List[str]
    top_n: Optional[int] = None


class RerankResponse(BaseModel):
    model: str
    results: List[dict]  # [{"index": 0, "relevance_score": 0.9}, ...]


def _load_model() -> str:
    """加载重排模型：优先 v2-m3，失败依次回退到 large/base。返回实际加载的模型名。"""
    global _model, _loaded_model_name
    for model_name in _MODEL_CANDIDATES:
        if not model_name:
            continue
        try:
            kwargs = {"device": _DEVICE, "max_length": _MAX_LEN}
            try:
                _model = CrossEncoder(model_name, **kwargs)
            except TypeError:
                kwargs.pop("trust_remote_code", None)
                _model = CrossEncoder(model_name, **kwargs)
            _loaded_model_name = model_name
            return model_name
        except Exception as e:
            print(f"加载 {model_name} 失败: {e}")
    raise RuntimeError("所有重排模型加载失败，请检查网络或模型名")


@app.on_event("startup")
def on_startup():
    name = _load_model()
    print(f"重排模型加载完成: {name} (device={_DEVICE})")


@app.get("/health")
def health():
    return {"status": "UP", "model": _loaded_model_name, "device": _DEVICE}


@app.post("/rerank", response_model=RerankResponse)
def rerank(req: RerankRequest):
    if _model is None:
        _load_model()
    if not req.documents:
        return {"model": _loaded_model_name, "results": []}

    pairs = [[req.query, doc] for doc in req.documents]
    scores = _model.predict(pairs)
    results = [
        {"index": i, "relevance_score": float(s)}
        for i, s in enumerate(scores)
    ]
    results.sort(key=lambda x: x["relevance_score"], reverse=True)
    if req.top_n and req.top_n > 0:
        results = results[: req.top_n]
    return {"model": _loaded_model_name, "results": results}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8001")))
