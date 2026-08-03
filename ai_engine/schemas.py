from pydantic import BaseModel


class ClassifyRequest(BaseModel):
    description: str


class ClassifyResponse(BaseModel):
    category: str
    priority: str
    suggested_action: str | None = None


class SummarizeRequest(BaseModel):
    stats: dict


class SummarizeResponse(BaseModel):
    summary: str


class ContextChunk(BaseModel):
    source: str
    content: str


class AnswerRequest(BaseModel):
    question: str
    context: list[ContextChunk]


class AnswerResponse(BaseModel):
    answer: str


class EmbedRequest(BaseModel):
    text: str


class EmbedResponse(BaseModel):
    embedding: list[float]
