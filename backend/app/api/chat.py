from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    answer: str


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest):
    # TODO: Thay câu trả lời mẫu bằng pipeline RAG + LLM.
    question = payload.message.strip()
    return ChatResponse(
        answer=(
            f"Bạn vừa hỏi: “{question}”. Đây là câu trả lời mẫu của D7. "
            "Nhóm cần kết nối dữ liệu chính thức của thư viện để chatbot trả lời chính xác."
        )
    )
