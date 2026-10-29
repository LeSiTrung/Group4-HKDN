# Dữ liệu và chỉ mục D7

Schema đang được triển khai bằng `sqlite3` chuẩn Python trong `backend/app/database/connection.py`, không dùng ORM. SQLite là nguồn dữ liệu nghiệp vụ; Qdrant chỉ giữ chỉ mục có thể tạo lại. Dữ liệu lưu tại `DATA_DIR/library.sqlite3`; đường dẫn tương đối neo vào `backend`, mặc định `backend/runtime`. Nếu tồn tại database ở vị trí làm việc cũ gây nhập nhằng, cấu hình phải đổi sang đường dẫn tuyệt đối của kho đúng trước khi khởi động.

## Bảng hiện có

| Bảng | Khóa và trường chính | Quan hệ/giới hạn |
| --- | --- | --- |
| `users` | `id` INTEGER PK; `email` UNIQUE; `name`, `password_hash`, `role` (mặc định reader), `active`, `created_at` | Email chuẩn hóa và mật khẩu băm bằng pwdlib; admin tạo qua CLI, không có tài khoản mặc định |
| `sessions` | `token_hash` TEXT PK; `user_id`, `expires_at` (Unix giây) | FK user, xóa cascade; chỉ lưu SHA-256 token ngẫu nhiên, không lưu cookie gốc |
| `conversations` | `id` PK; `user_id`, `title`, `created_at`, `updated_at` | FK user, xóa cascade; mọi API lịch sử kiểm tra chủ sở hữu |
| `messages` | `id` PK; `conversation_id`, `role`, `content`, `sources`, `status`, `mode`, `books`, `context_query`, `created_at` | FK conversation, xóa cascade; sources/books là JSON TEXT; context_query giữ chủ đề tra sách cho hỏi tiếp |
| `feedback` | PK ghép `(user_id,message_id)`; `rating`, `comment` | Hai FK cascade; CHECK rating IN (-1,1); API chỉ nhận message assistant thuộc người đánh giá |
| `knowledge` | `id` PK; `title`, `question`, `aliases`, `keywords`, `answer`, `category`, `source_url`, `source_title`, `checked_at`, `status`, `published`, `valid_from`, `valid_until`, `verified_by`, `updated_at` | aliases/keywords là JSON TEXT; validation nguồn HTTPS, ngày, người xác nhận thực hiện tại Pydantic/service |
| `books` | `id` INTEGER PK AUTOINCREMENT; `title`, `author`, `year`, `kind`, `subjects`, `description`, `source_url` UNIQUE, `checked_at`, `published` | Metadata độc lập, không FK tới knowledge; bản mới mặc định chưa xuất bản; import upsert theo source_url |
| `schedules` | `id` PK; `branch`, `weekday`, `opens`, `closes`, `valid_from`, `valid_until`, `note`, `verified_by`, `source_url`, `source_title`, `checked_at`, `closed` | Cơ sở 1/2/3, thứ Hai=0; ngày/giờ/người xác nhận được kiểm tra tại API |
| `jobs` | `id` PK; `url`, `status`, `imported`, `error`, `created_at` | Crawl queued/running/done/failed; job dở dang bị đánh failed lúc API khởi động lại |
| `audit` | `id` PK; `actor_id`, `action`, `target`, `created_at` | FK user ON DELETE SET NULL; nhật ký thao tác quản trị, không lưu access token |
| `renewals` | `idempotency_key` TEXT PK; `user_id`, `loan_id`, `state`, `result` | FK user cascade; result JSON TEXT hoặc NULL; pending/uncertain/succeeded/failed |
| `meta` | `key` TEXT PK; `value` | Tạo trong bước seed; cờ seeded/books_seeded ngăn dữ liệu đã xóa bị tạo lại mỗi lần khởi động |
| `channel_events` | `event_key` TEXT PK; `channel`, `status`, `created_at` (Unix giây) | Tạo khi nhận sự kiện đầu tiên; khóa SHA-256 từ channel/recipient/message_id; processing/failed/uncertain/sent |

Các cột thời gian `created_at`/`updated_at` mặc định dùng UTC ISO 8601; các ngày nghiệp vụ `checked_at`/hiệu lực là `YYYY-MM-DD`, được so với ngày Việt Nam. Không phải mọi enum/giới hạn độ dài đều có CHECK trong SQLite: ghi dữ liệu trực tiếp có thể bỏ qua validation của API. Không sửa dữ liệu nghiệp vụ bằng SQL ad hoc để vượt kiểm tra quyền hoặc ledger.

Không có bảng tồn kho, bản sách, đặt trước, mượn/trả nội bộ, danh mục phân cấp hay mật khẩu thư viện. Thông tin khoản mượn/gia hạn đến từ bridge được thư viện phê duyệt; `renewals` là ledger chống gửi trùng, không phải hệ thống lưu thông thay thế.

## Toàn vẹn và cập nhật schema

Mỗi kết nối bật `foreign_keys=ON`, `busy_timeout=15000` và đóng sau transaction; lỗi rollback. Database dùng WAL. Chỉ mục bổ sung: `ix_messages_conversation(conversation_id,id)`, `ix_conversations_user(user_id,updated_at)`; UNIQUE/PK có chỉ mục SQLite tương ứng. Tìm local hiện đọc metadata đã xuất bản rồi xếp hạng trong Python, chưa có SQLite FTS hoặc phân trang tại SQL; cần đo lại trước khi dùng danh mục lớn.

Schema hiện tại có `PRAGMA user_version=2`. Khi mở kho cũ, ứng dụng tạo bảng còn thiếu, thêm `messages.books` và `messages.context_query` nếu thiếu rồi đặt version 2; từ chối kho có version lớn hơn 2. Đây là nâng cấp cộng thêm cho schema trước của dự án, chưa có framework migration tổng quát hay migration ngược. Backup trước nâng cấp; không mặc định dùng binary cũ với schema mới.

API dùng `BEGIN IMMEDIATE` ở các thao tác cần kiểm tra và ghi cùng transaction, gồm nhập danh mục và đối soát gia hạn. Import được kiểm tra toàn bộ request trước khi ghi và commit nguyên lô. Trước gọi upstream, ledger gia hạn được commit `pending`; lỗi chưa rõ kết quả giữ `uncertain`. Không giữ transaction SQLite trong lúc chờ HTTP. Xóa tài khoản trả 409 khi còn pending/uncertain để bảo toàn khóa chống gửi lại; sau đối soát mới xóa được. Xóa user thành công cascade lịch sử, feedback, sessions và ledger đã kết thúc.

Khách không ghi conversations/messages vào SQLite. Tài khoản gửi chat được kiểm tra lại trạng thái trước khi lưu; không có cơ chế tự tóm tắt hội thoại hoặc lưu toàn bộ lịch sử vào prompt. Phiên đăng nhập hết hạn sau bảy ngày; đổi mật khẩu/khóa tài khoản thu hồi phiên. Database/backup chứa email và nội dung chat, chưa mã hóa ở cấp ứng dụng và chưa có tác vụ xóa dữ liệu tự động theo thời hạn lưu.

## Qdrant và đồng bộ nguồn

FastEmbed dùng `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` theo cấu hình; cache ở `DATA_DIR/models`, Qdrant local ở `DATA_DIR/vectors` hoặc remote qua `QDRANT_URL`. Collection `knowledge_<model-hash>` và `books_<model-hash>` tách hai loại dữ liệu, cosine distance; payload là ID để nối lại metadata SQLite. Fingerprint nguồn điều khiển rebuild; thay đổi nội dung/danh mục làm mất hiệu lực fingerprint. CLI/nút reindex quản trị tạo lại FAQ; tìm ngữ nghĩa sách tạo chỉ mục books khi cần.

Knowledge được lọc trạng thái xuất bản và hiệu lực từ SQLite; kết quả vector nối lại nguồn hiện có. Sách chỉ truy xuất bản published và kiểm tra lại trước trả kết quả. Không dùng vector làm nguồn xác nhận số lượng sách, quy định hoặc giao dịch. Không tự xóa volume Qdrant khi đang chạy; một tiến trình giữ Qdrant local, không chạy CLI index đồng thời API.

## Backup và restore

CLI `python -m app.cli backup <thư-mục-mới>` dùng SQLite backup API để lấy toàn bộ kho nhất quán, gồm ledger và audit. Không copy riêng file SQLite khi WAL đang ghi. `scripts/restore.py` chỉ nhận nguồn read-only hợp lệ và file đích mới, kiểm tra integrity rồi thu hồi sessions; giữ nguyên ledger chưa rõ kết quả. Vectors tái tạo sau restore. Xem [vận hành](operations.md) cho lệnh và rollback; thời hạn lưu, mã hóa và phân quyền backup cần đơn vị vận hành xác nhận.
