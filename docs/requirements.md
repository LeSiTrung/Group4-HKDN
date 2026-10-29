# Yêu cầu kỹ thuật và phạm vi D7

Tài liệu phản ánh chức năng có trong mã hiện tại; mức kiểm chứng nằm riêng ở [validation.md](validation.md). Mục tiêu là trợ lý dịch vụ thư viện có nguồn, tra cứu metadata sách và hỗ trợ tích hợp chính thức. Sự hiện diện của code không xác nhận dữ liệu/quy định đã được thư viện duyệt hoặc dịch vụ ngoài đã hoạt động thật.

## Chức năng được triển khai

| Nhóm | Hành vi và giới hạn |
| --- | --- |
| Chat tiếng Việt | FAQ chuẩn hóa dấu, truy xuất lexical rồi semantic khi cần; trả nguồn/ngày rà soát/cảnh báo, gợi ý làm rõ và fallback khi thiếu căn cứ |
| RAG/LLM | FastEmbed + Qdrant; Ollama cục bộ mặc định CPU; provider HTTPS tương thích OpenAI tùy chọn khi đã được phép. JSON/source ID, số, URL và lời xác nhận giao dịch được kiểm tra trước chấp nhận câu trả lời |
| Danh mục | Tìm metadata theo nhan đề/tác giả/chủ đề/mô tả, lọc sách in/tài liệu số, lexical có dung sai chính tả, semantic fallback, phân trang local, chi tiết và tối đa ba tài liệu liên quan |
| Nguồn OPAC | Chế độ auto ưu tiên local rồi đọc OPAC nếu không có kết quả; cho phép chọn local/opac; bộ nối OPAC chỉ đọc trang đầu và trả cảnh báo lỗi/chặn nguồn |
| Ngữ cảnh | Một số hỏi tiếp về sách/tác giả/năm/tình trạng và cơ sở cho câu hỏi giờ hôm nay; hỏi lại khi nhiều cuốn. Không cam kết hiểu mọi câu nhiều ý hoặc mọi lỗi chính tả |
| Tài khoản | Đăng ký reader, đăng nhập cookie HttpOnly, đổi mật khẩu, đăng xuất; admin tạo qua CLI; khóa/mở tài khoản qua admin |
| Lịch sử | Khách chỉ giữ chat ở bộ nhớ giao diện và gửi tối đa sáu lượt ngữ cảnh; tài khoản lưu, mở, xóa hội thoại, export dữ liệu của mình và đánh giá câu trả lời. Server bỏ qua lịch sử client của tài khoản đã đăng nhập |
| Quản trị | CRUD knowledge và danh mục sách; nhập JSON danh mục nguyên lô theo URL; quản lý lịch có thời hạn/người xác nhận; crawl thành bản nháp, xem jobs/audit/trạng thái và reindex FAQ |
| Khoản mượn/gia hạn | Bộ nối nhận access token được cấp hợp lệ, yêu cầu phiên ứng dụng/xác nhận/idempotency; pending/uncertain chặn gửi lại và xóa tài khoản; admin ghi kết quả đã đối soát, không gửi giao dịch mới |
| Kênh | Webhook Messenger/Zalo kiểm tra chữ ký, chống trùng ledger, gửi trả lời text; chưa liên kết tài khoản web với người dùng kênh hay mở công cụ giao dịch cho chatbot |
| Giao diện | React responsive có trạng thái tải/rỗng/lỗi, cards nguồn/sách, chi tiết tài liệu, lịch sử, quản trị; modal/điều hướng có hỗ trợ bàn phím; voice input phụ thuộc Web Speech API trình duyệt |
| Vận hành | SQLite WAL, một worker với Qdrant local; Windows launcher, frontend build cùng origin, Docker Compose/Caddy, CLI backup và restore offline vào kho mới |

Mỗi biểu ghi sách cần HTTPS nguồn gốc và ngày đối chiếu, mặc định bản nháp. Không suy ra số bản rỗi, vị trí kệ, ISBN hoặc tình trạng lưu thông từ metadata không có những trường đó. Đề xuất liên quan dựa tác giả/chủ đề/nhan đề; không sử dụng lịch sử mượn để cá nhân hóa.

Knowledge xuất bản vẫn có thể mang `needs_confirmation`; câu trả lời phải giữ cảnh báo. Phí/quy định/giờ chỉ áp dụng dữ liệu đã xác nhận phù hợp và hiệu lực; câu hỏi lịch hiện hỗ trợ hôm nay theo cơ sở, không có lịch mặc định giả định đã duyệt. Crawl không tự xuất bản hoặc nâng mức xác nhận của nguồn.

## Yêu cầu bảo mật và độ tin cậy

- Backend là nơi kiểm tra phiên, quyền admin và quyền sở hữu hội thoại; 404 cho hội thoại không thuộc mình. Không lưu mật khẩu thư viện/access token upstream vào database hoặc localStorage.
- Mọi mutation web cần `X-Requested-With: D7` và Origin cho phép; cookie SameSite Strict, bật Secure khi HTTPS. Request body tối đa 64 KiB, kể cả import và webhook; rate limit trong bộ nhớ theo IP.
- Evidence và lịch sử là dữ liệu không đáng tin, không được thay system instructions. LLM không có công cụ ghi dữ liệu/gia hạn; kết quả timeout của giao dịch phải đối soát, không tự coi thất bại.
- Truy xuất phải dùng nguồn còn xuất bản/còn hiệu lực; thiếu nguồn trả rõ giới hạn. Bộ lọc LLM là lớp phòng vệ, không phải chứng minh hết hallucination.
- Không tăng chi phí API, dùng dữ liệu cá nhân thật cho test, triển khai công khai hoặc đổi production khi chưa được phép. Bí mật nằm ngoài Git/frontend; volume và backup cần phân quyền và chính sách lưu giữ.
- Kiểm chứng phải bao phủ quyền truy cập, dữ liệu rỗng/sai, lỗi upstream, fallback, regression, frontend build và các luồng quan trọng. Chỉ công bố số liệu từ lần chạy thực tế có bằng chứng.

## Phần phụ thuộc bên ngoài — BLOCKED cho nghiệm thu thực tế

1. Đơn vị thư viện xác nhận nguồn dữ liệu được phép nhập/thu thập, quy định hiện hành, giờ/phí/thời hạn và người duyệt nội dung.
2. Bridge khoản mượn/gia hạn có API, tài khoản thử, xác thực và quyền chính thức; kiểm tra idempotency/đối soát với upstream thật. Không có URL/token thì giữ unavailable, không giao dịch giả.
3. Messenger/Zalo cần app/OA/page, secret/token, quyền và webhook HTTPS được duyệt; test fixture không thay thế gửi/nhận thật.
4. Máy chủ/DNS/TLS/quyền triển khai, backup/restore/rollback trên máy đích, thời hạn lưu/xóa dữ liệu và đầu mối vận hành phải được chấp thuận trước production.

Không yêu cầu xây hệ thống lưu thông thay thế: chưa có quản lý bản sách, mượn/trả nội bộ, đặt trước, tồn kho trực tiếp, phân loại danh mục riêng, quản lý độc giả thư viện hoặc khuyến nghị cá nhân hóa. Chưa có streaming token, tự tóm tắt hội thoại hay hệ thống nhiều replica; không thêm để chứng minh hoàn thiện phạm vi cốt lõi. Tài liệu học thuật/báo cáo/slide không thuộc công việc phát triển hiện tại.

## Điều kiện hoàn thành

Ứng dụng/API/database khởi động; các luồng tài khoản, chat có nguồn, tìm/chi tiết sách, hỏi tiếp, lịch sử riêng, quản trị và xử lý lỗi phải có bằng chứng chạy. Dữ liệu metadata và dữ liệu lưu thông phải được phân biệt trên giao diện/câu trả lời. Test cục bộ và build phải đạt; P0/P1 còn biết phải được xử lý hoặc ghi blocker cụ thể. Tích hợp thật và triển khai trên máy đích chỉ đạt khi đã nghiệm thu riêng; không đánh dấu PROJECT COMPLETE trong khi các điều kiện bắt buộc còn bị chặn.
