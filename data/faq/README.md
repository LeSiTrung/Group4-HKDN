# FAQ thư viện
`library.json` là baseline; `public-library-2026-10-31.json` bổ sung10 KnowledgeInput có URL và ngày đối chiếu. `reviewed_public` nghĩa là đã đọc nguồn công khai, không phải thư viện đã nghiệm thu; `needs_confirmation` giữ rõ nội dung chưa xác nhận hiện hành. Không tạo verifier hoặc ngày hiệu lực giả.

Nhập rõ ràng bằng `python -m app.cli import-knowledge ../data/faq/public-library-2026-10-31.json` từ backend. Lệnh không ghi đè câu hỏi/nguồn đã có hoặc tự công bố lại nội dung quản trị đã rút. Kho cũ không tự thay đổi khi checkout hoặc khởi động lại.
Không đưa dữ liệu cá nhân hoặc tài liệu chưa được phép sử dụng vào repository.
# Reviewed additions, 1 November 2026

`public-library-2026-11-01.json` adds four manually reviewed summaries: publishing support, library orientation, the dated uniform notice and the differently worded hours in the33-page guide linked from LIC's2024/11 directory. The hours and uniform policy remain `needs_confirmation`; no current effective interval or staff verifier is invented. Multiple published hours references are displayed together until a verified date/branch schedule is available. The misleading `photo-scan` URL is interpreted from its actual orientation content, never as a price list.

Use the existing `app.cli import-knowledge` command after a private backup. Repeat import skips all four entries and preserves edits/withdrawals. This pack does not contain the bulk HTML staging, staff profiles, spam or example credentials. Technical source/hash evidence: `docs/validation/2026-11-01-data-container.json`.
