from pydantic import BaseModel


class ChatRequest(BaseModel):
    user_id: str
    user_name: str
    user_text: str
    extra_prompt: str | None = None
