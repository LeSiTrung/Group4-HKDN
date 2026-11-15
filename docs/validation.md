# Kiểm thử dự án

Chạy bộ kiểm thử như trong [hướng dẫn cài đặt](getting-started.md#phát-triển-và-kiểm-thử). Workflow Verify chạy kiểm thử backend, kiểm tra phục hồi, đánh giá hội thoại offline và build frontend. Các bài kiểm thử offline dùng SQLite tạm và không yêu cầu dịch vụ AI.

- [Tích hợp MARC ngày 15/11/2026](validation/2026-11-15-marc-integration.json) ghi kết quả nhập, kiểm thử trình duyệt, Docker, Qdrant và hội thoại khi dùng dữ liệu cục bộ.
- [Đánh giá truy xuất embedding](validation/2026-10-31-candidate-integration.json) ghi kết quả so sánh trên tập truy vấn tổng hợp cố định. Quy trình chạy lại có tại [hướng dẫn embedding thử nghiệm](candidate-runtime.md).
- [Kiểm thử truy xuất theo nhan đề và tác giả](validation/2026-10-31-retrieval-quality.json) ghi phép đo trên ảnh chụp danh mục cố định.
- [Các bộ testcase và lệnh đánh giá](../tests/README.md) mô tả phần bao phủ, tập dữ liệu và giới hạn khi diễn giải kết quả.

Đánh giá trên máy phát triển và Docker cục bộ chưa thay thế nghiệm thu bởi thư viện hoặc kiểm thử giao dịch thật, kênh nhắn tin và triển khai trên máy chủ đích.
