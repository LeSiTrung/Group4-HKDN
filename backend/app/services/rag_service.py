"""Khung xử lý RAG cho tài liệu thư viện.

Luồng dự kiến:
- Nạp tài liệu được thư viện cho phép sử dụng.
- Chia văn bản thành các đoạn.
- Tạo embedding và lưu vào vector store.
- Truy xuất đoạn liên quan trước khi gọi LLM.
"""


def retrieve_context(question: str) -> str:
    # TODO: Triển khai truy xuất tài liệu, ví dụ với PostgreSQL + pgvector.
    return ""
