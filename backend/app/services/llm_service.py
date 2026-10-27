"""Điểm tích hợp mô hình ngôn ngữ (LLM).

TODO:
1. Chọn nhà cung cấp/model phù hợp.
2. Đọc API key từ biến môi trường.
3. Gửi câu hỏi cùng ngữ cảnh đã truy xuất từ tài liệu thư viện.
4. Xử lý lỗi, giới hạn chi phí và kiểm soát dữ liệu.
"""


def generate_answer(question: str, context: str = "") -> str:
    raise NotImplementedError("Chưa tích hợp LLM; hãy triển khai sau khi nhóm chọn nhà cung cấp.")
