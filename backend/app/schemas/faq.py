from pydantic import BaseModel, Field


class FAQRequest(BaseModel):
    question: str = Field(..., min_length=1)


class FAQResponse(BaseModel):
    answer: str
    cited_sources: list[str]
