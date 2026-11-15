# FAQ thư viện
`library.json` là baseline; `public-library-2026-10-31.json` bổ sung10 KnowledgeInput có URL và ngày đối chiếu. `reviewed_public` nghĩa là đã đọc nguồn công khai, không phải thư viện đã nghiệm thu; `needs_confirmation` giữ rõ nội dung chưa xác nhận hiện hành. Không tạo verifier hoặc ngày hiệu lực giả.

Nhập rõ ràng bằng `python -m app.cli import-knowledge ../data/faq/public-library-2026-10-31.json` từ backend. Lệnh không ghi đè câu hỏi/nguồn đã có hoặc tự công bố lại nội dung quản trị đã rút. Kho cũ không tự thay đổi khi checkout hoặc khởi động lại.
Không đưa dữ liệu cá nhân hoặc tài liệu chưa được phép sử dụng vào repository.
# Reviewed additions, 1 November 2026

`public-library-2026-11-01.json` adds four manually reviewed summaries: publishing support, library orientation, the dated uniform notice and the differently worded hours in the33-page guide linked from LIC's2024/11 directory. The hours and uniform policy remain `needs_confirmation`; no current effective interval or staff verifier is invented. Multiple published hours references are displayed together until a verified date/branch schedule is available. The misleading `photo-scan` URL is interpreted from its actual orientation content, never as a price list.

Use the existing `app.cli import-knowledge` command after a private backup. Repeat import skips all four entries and preserves edits/withdrawals. This pack does not contain the bulk HTML staging, staff profiles, spam or example credentials. Technical source/hash evidence: `docs/validation/2026-11-01-data-container.json`.

## Đối chiếu LIC ngày 12/11/2026

Gói `public-library-2026-11-12.json` bổ sung đầu mối xác nhận giờ phục vụ, địa chỉ từ mục Thư viện các cơ sở trên trang chủ và bản tóm tắt chính sách mượn liên thư viện UTH–Đại học Bách khoa. Các trang địa chỉ và liên hệ được xem trực tiếp. Nội dung PDF được đối chiếu từ bản lưu có SHA-256 khớp. [Trang chủ LIC](https://lic.ut.edu.vn/), [trang liên hệ](https://lic.ut.edu.vn/lien-he/), [chính sách mượn liên thư viện](https://lic.ut.edu.vn/wp-content/uploads/2025/08/2025.07.08_Chinhsachmuonlienthuvien.pdf).

Trang đào tạo vẫn liên kết hướng dẫn trong thư mục `2024/11`. Trang 12 của bản lưu ghi lịch chung, trong khi bản `2022/10` tách giờ theo cơ sở. Mục Tin tức và các trang cơ sở được rà chưa cung cấp lịch mới hơn kèm hiệu lực. Chatbot hiển thị lịch tham khảo cùng kênh liên hệ và ưu tiên lịch đã xác nhận trong bảng `schedules` khi có bản ghi phù hợp. [Trang đào tạo LIC](https://lic.ut.edu.vn/dich-vu-thu-vien/photo-scan-tai-lieu/), [Tin tức LIC](https://lic.ut.edu.vn/category/tin-tuc/).

Từ thư mục `backend`, nhập gói bằng `python -m app.cli import-knowledge ../data/faq/public-library-2026-11-12.json` sau khi sao lưu. Có thể chạy lại lệnh để kiểm tra các mục đã nhập.

Sau khi khung giờ chung được xác nhận cho chatbot, câu hỏi giờ phục vụ dùng trang 12 của bản 2024/11. Lịch đã nhập trong Quản trị → Lịch phục vụ được ưu tiên theo cơ sở và ngày được hỏi. Bản 2022/10 vẫn nằm trong kho nguồn tham khảo.
