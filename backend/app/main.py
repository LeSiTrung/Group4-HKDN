from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router

app = FastAPI(
    title="D7 Library Chatbot API",
    description="API khởi đầu cho chatbot thư viện UTH",
    version="0.1.0",
)

# Chỉ cấu hình mở rộng khi triển khai thật; cần giới hạn origin trong production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router, prefix="/api")


@app.get("/health")
def health_check():
    return {"status": "ok", "project": "D7 Chatbot Thu Vien"}
