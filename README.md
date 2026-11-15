# Trợ lý Thư viện UTH

Ứng dụng hỏi đáp về dịch vụ thư viện có dẫn nguồn, tra cứu danh mục theo nhan đề, tác giả và nội dung, xem thông tin MARC và hỏi tiếp trong hội thoại. Bạn đọc có thể lưu lịch sử bằng tài khoản. Quản trị viên duyệt nội dung, danh mục và phản hồi riêng của bạn đọc.

**[Cài đặt và chạy dự án](docs/getting-started.md)** dành cho thành viên mới. Có thể chạy FAQ và tra cứu mẫu trên Windows, Linux hoặc Docker. Ollama và tìm kiếm ngữ nghĩa là bước thiết lập riêng.

- **Giao diện và API** React, Vite và FastAPI.
- **Dữ liệu** SQLite lưu danh mục, tài khoản và hội thoại. FastEmbed và Qdrant tạo chỉ mục tìm kiếm ngữ nghĩa.
- **Sinh câu trả lời** Qwen3-1.7B qua Ollama. Các câu hỏi nghiệp vụ và thông tin sách cần có nguồn.
- **Dữ liệu thư viện** Clone có FAQ và danh mục khởi đầu. Danh mục OPAC/DSpace đầy đủ của nhóm cần nhập riêng từ bộ dữ liệu công khai đã duyệt. [Nhập OPAC và MARC](docs/opac-import.md) · [Nhập DSpace](docs/dspace-import.md).
- **Thư viện mẫu** Có thể bật luồng đăng ký, nhận, gia hạn và trả sách giả lập. Tích hợp giao dịch thật cần cấu hình kết nối với thư viện. [Tích hợp](docs/integrations.md).

[Kiểm thử và kết quả](docs/validation.md) · [Vận hành, triển khai và sao lưu](docs/operations.md) · [Lược đồ dữ liệu](docs/database-design.md) · [Quy ước đóng góp](CONTRIBUTING.md)
