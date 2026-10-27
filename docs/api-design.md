# API sơ bộ

## GET /health
Kiểm tra backend.

## POST /api/chat
Request:
```json
{ "message": "Thư viện mở cửa lúc mấy giờ?" }
```

Response hiện tại là câu trả lời mẫu:
```json
{ "answer": "..." }
```

TODO: bổ sung RAG, LLM, nguồn trích dẫn và xử lý lỗi.
