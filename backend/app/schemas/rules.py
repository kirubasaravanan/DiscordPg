from pydantic import BaseModel


class RulesResponse(BaseModel):
    content: str
