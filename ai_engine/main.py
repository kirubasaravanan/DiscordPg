"""ai_engine/ entrypoint — a standalone FastAPI service the backend's
services layer calls over HTTP (docs/ARCHITECTURE.md §4.5, §5). Never
called from an API router, the dashboard, or the Discord bot directly;
never given database credentials (see config.py).
"""

import json
import logging

from fastapi import FastAPI, HTTPException

from ollama_client import OllamaError, chat, embed
from prompts import answer_messages, classification_messages, summary_messages
from schemas import (
    AnswerRequest,
    AnswerResponse,
    ClassifyRequest,
    ClassifyResponse,
    EmbedRequest,
    EmbedResponse,
    SummarizeRequest,
    SummarizeResponse,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai_engine")

app = FastAPI(title="PG OS AI Engine", version="0.1.0")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/classify", response_model=ClassifyResponse)
async def classify(payload: ClassifyRequest) -> ClassifyResponse:
    try:
        raw = await chat(classification_messages(payload.description), json_mode=True)
    except OllamaError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=f"Model did not return valid JSON: {raw[:500]}") from exc
    return ClassifyResponse(
        category=str(data.get("category", "")),
        priority=str(data.get("priority", "")),
        suggested_action=data.get("suggested_action"),
    )


@app.post("/summarize", response_model=SummarizeResponse)
async def summarize(payload: SummarizeRequest) -> SummarizeResponse:
    try:
        text = await chat(summary_messages(payload.stats))
    except OllamaError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return SummarizeResponse(summary=text.strip())


@app.post("/answer", response_model=AnswerResponse)
async def answer(payload: AnswerRequest) -> AnswerResponse:
    context = [{"source": c.source, "content": c.content} for c in payload.context]
    try:
        text = await chat(answer_messages(payload.question, context))
    except OllamaError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return AnswerResponse(answer=text.strip())


@app.post("/embed", response_model=EmbedResponse)
async def embed_endpoint(payload: EmbedRequest) -> EmbedResponse:
    try:
        vector = await embed(payload.text)
    except OllamaError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return EmbedResponse(embedding=vector)
