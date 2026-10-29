# API kỹ thuật

FastAPI cung cấp OpenAPI tại `/openapi.json`, giao diện tại `/docs`. API JSON có tiền tố `/api`; frontend build được phục vụ cùng origin ở `/`. Các route bên dưới phản ánh mã hiện có; OpenAPI là nguồn schema chi tiết.

## Xác thực và giới hạn

Đăng nhập/đăng ký trả `{user:{id,name,email,role}}` và cookie `d7_session` HttpOnly, SameSite=Strict, hạn 7 ngày. Production bật Secure. Token phiên là chuỗi ngẫu nhiên; SQLite chỉ lưu hash. Frontend dùng `credentials:'include'`; không lưu mật khẩu/token thư viện vào localStorage.

Mọi thao tác thay đổi `/api/*` cần header `X-Requested-With: D7`; Origin nếu có phải nằm trong `ALLOWED_ORIGINS`. Webhook dùng kiểm tra chữ ký riêng. Body tối đa 65.536 byte tại middleware và Caddy; hạn tổng body này cũng áp dụng webhook. Mỗi địa chỉ IP có tối đa 10 thao tác auth/phút hoặc 120 yêu cầu API khác/phút; vượt hạn trả 429 và `Retry-After: 60`. Hạn trong bộ nhớ một tiến trình, không phải hạn phân tán.

Lỗi chuẩn `{detail: string}`; Pydantic có thể trả `detail` là danh sách lỗi. 401 cần đăng nhập; 403 thiếu quyền/origin; 404 không có tài nguyên thuộc người dùng; 409 xung đột; 413 body lớn; 422 dữ liệu không hợp lệ; 502/503 dịch vụ bên ngoài lỗi/chưa sẵn sàng. Không suy ra thành công từ HTTP timeout.

## Các route

| Method + đường dẫn | Quyền | Nội dung |
| --- | --- | --- |
| `GET /health` | Công khai | Version, số nội dung xuất bản, trạng thái cấu hình/capability; không kiểm tra giao dịch upstream |
| `POST /api/auth/register` | Công khai | `{name,email,password}`; luôn tạo reader, 201 |
| `POST /api/auth/login` | Công khai | `{email,password}` |
| `GET /api/auth/me` | Đăng nhập | User hiện tại |
| `POST /api/auth/logout` | Cookie hiện tại | Thu hồi phiên, `{ok:true}` |
| `POST /api/auth/password` | Đăng nhập | `{current_password,new_password}`; thu hồi các phiên cũ |
| `DELETE /api/auth/me` | Đăng nhập | `{password}`; xóa tài khoản/lịch sử của mình; 409 với admin hoặc ledger gia hạn `pending/uncertain` |
| `POST /api/chat` | Khách/đăng nhập | `{message,conversation_id?,history?}`; khách không lưu lịch sử server |
| `GET /api/conversations` | Đăng nhập | Danh sách hội thoại của mình |
| `GET /api/conversations/{id}` | Chủ sở hữu | Hội thoại + messages |
| `DELETE /api/conversations/{id}` | Chủ sở hữu | Xóa hội thoại của mình |
| `GET /api/export` | Đăng nhập | `{user,conversations}` của mình |
| `POST /api/feedback` | Chủ message | `{message_id,rating:-1\|1,comment?}` |
| `GET /api/catalog` | Công khai | `q`, `kind=all\|books\|digital`, `source=auto\|local\|opac`, `page>=1`, `page_size=1..50` (mặc định 20) |
| `GET /api/catalog/{id}` | Công khai | Chi tiết biểu ghi local đã xuất bản, tối đa ba tài liệu liên quan và cảnh báo metadata |
| `POST /api/library/loans` | Đăng nhập | `{access_token}`; bridge được phê duyệt |
| `POST /api/library/renew` | Đăng nhập | `{access_token,loan_id,confirmation:true,idempotency_key}` |
| `GET /api/admin/status` | Admin | Counts, drafts, vector/LLM/integration configuration, audit |
| `GET/POST /api/admin/books` | Admin | Danh sách gồm bản nháp/tạo biểu ghi; POST trả 201 |
| `PUT/DELETE /api/admin/books/{id}` | Admin | Thay toàn bộ biểu ghi/xóa; không tồn tại trả 404; trùng URL trả 409 |
| `POST /api/admin/books/import` | Admin | `{items:[BookInput,...]}`; 1..200 mục, upsert theo URL nguồn trong một transaction; 201 `{imported}` |
| `GET /api/admin/renewals` | Admin | Tối đa 100 giao dịch gia hạn mới nhất, kết quả JSON hoặc null |
| `POST /api/admin/renewals/{key}/reconcile` | Admin | Ghi nhận kết quả đã đối soát; không gửi lại upstream |
| `GET/POST /api/admin/knowledge` | Admin | Danh sách/tạo nội dung |
| `PUT/DELETE /api/admin/knowledge/{id}` | Admin | Thay toàn bộ trường nội dung/xóa nguồn |
| `POST /api/admin/reindex` | Admin | Rebuild vectors trong tiến trình hiện tại |
| `POST /api/admin/crawl` | Admin | `{url,max_pages?:1..10}`; 202 `{job_id}` |
| `GET /api/admin/jobs` | Admin | 100 job gần nhất |
| `GET /api/admin/users` | Admin | User metadata, không hash mật khẩu |
| `PATCH /api/admin/users/{id}` | Admin | `{active:bool}`; không tự khóa mình |
| `GET/POST /api/admin/schedules` | Admin | Liệt kê/tạo lịch có nguồn xác nhận |
| `DELETE /api/admin/schedules/{id}` | Admin | Xóa lịch |
| `GET/POST /api/webhooks/messenger` | Chữ ký/verify token | Xác minh webhook, tiếp nhận text và chống trùng |
| `POST /api/webhooks/zalo` | Chữ ký | Tiếp nhận text và chống trùng |

## Chat và nguồn

Ví dụ request:

```json
{"message":"Làm sao tra cứu tài liệu?"}
```

`message` là chuỗi không rỗng tối đa 2.000 ký tự. `history` tối đa sáu mục `{role:'user'|'assistant',content}` với tối đa 2.000 ký tự mỗi mục. Khách gửi lịch sử từ bộ nhớ giao diện; dữ liệu này là ngữ cảnh không đáng tin, không phải chỉ thị hay quyền truy cập. Tài khoản đã đăng nhập bỏ qua `history` do client gửi và đọc tối đa sáu message gần nhất từ `conversation_id` thuộc mình. ID của người khác hoặc ID gửi bởi khách trả 404. Chat mới của tài khoản không nhận ngữ cảnh từ cuộc chat khác.

Response có `answer`, `status`, `sources:[{title,url,checked_at}]`, `suggestions`, `mode:'faq'|'rag'|'fallback'`, `books` (mảng biểu ghi local), `conversation_id` và `message_id` (null cho khách). Status có thể là `answered`, `needs_confirmation`, `clarify`, `not_found`. Câu trả lời nguồn thiếu xác nhận giữ cảnh báo. LLM chỉ diễn đạt evidence cho câu hỏi phù hợp; tra metadata sách và lịch phục vụ dùng logic cấu trúc. LLM phải trả JSON hợp lệ và IDs thuộc evidence; số/URL lạ hoặc lời xác nhận giao dịch bị loại. Các kiểm tra này không chứng minh mọi câu trả lời đều đúng ngữ nghĩa và không thay thế kiểm chứng nghiệp vụ của thư viện.

## Danh mục và gia hạn

`BookInput` gồm `title` (bắt buộc, tối đa 500), `author` (300), `year` (rỗng hoặc bốn chữ số), `kind:'books'|'digital'`, `subjects` (1.000), `description` (8.000), `source_url` (HTTPS, tối đa 1.000, duy nhất), `checked_at` (ngày không ở tương lai theo Việt Nam), `published` (mặc định false). Response thêm `id` và `url` (cùng giá trị `source_url`). Không có ISBN, vị trí kệ, số lượng hay trạng thái lưu thông nếu nguồn hiện tại không cung cấp. Import không nhận file upload: client gửi JSON; toàn bộ request vẫn bị giới hạn 64 KiB, nên phải chia lô nhỏ hơn 200 nếu metadata dài. URL trùng trong cùng lô trả 422; URL đã có trong database được cập nhật đủ trường, kể cả trạng thái xuất bản.

`source=auto` ưu tiên tìm local, dùng OPAC khi local không có kết quả; `local` không gọi OPAC; `opac` bỏ qua local. Tìm local chuẩn hóa dấu tiếng Việt, xếp hạng từ khóa/có dung sai chính tả, sau đó mới thử vector nếu không có kết quả và đã bật. Local trả `{items,total,page,page_size,source:'local',search_url,warning}`; không có kết quả không chứng minh thư viện không có sách. OPAC hiện chỉ hỗ trợ trang đầu (`page!=1` trả 422); schema kết quả đọc upstream xem OpenAPI/mã bộ nối. `GET /catalog/{id}` chỉ áp dụng ID local, không phải mã OPAC. Tài liệu liên quan là kết quả lexical theo tác giả/chủ đề/nhan đề, không phải đề xuất cá nhân hóa.

Gia hạn cần phiên ứng dụng, access token được cấp hợp lệ, xác nhận rõ và idempotency key 12..128 ký tự chữ/số/`_`/`-`. Không lưu access token trong SQLite. Cùng key đã thành công trả kết quả đã lưu; key của người/khoản mượn khác hoặc key chưa rõ kết quả trả 409. Khoản mượn có giao dịch `pending/uncertain` bị chặn gửi lại ngay cả khi đổi key. Timeout không chứng minh thất bại; phải đối soát trước khi gửi giao dịch mới hoặc xóa tài khoản.

Body đối soát là `{confirmation:true,state:'succeeded'|'failed',reference,due_date?}`. `reference` dài 3..500 ký tự và không được trắng; thành công bắt buộc có `due_date`. Chỉ đổi được trạng thái `pending/uncertain`; ghi audit và lưu kết quả có `origin:'manual_reconciliation'`. Quản trị phải xác minh với hệ thống/đầu mối thư viện trước khi ghi; API không tự kiểm chứng tham chiếu bên ngoài.

## Nội dung và lịch phục vụ

Knowledge CRUD nhận `title,question,aliases,keywords,answer,category,source_url,source_title,checked_at,status,published,valid_from?,valid_until?,verified_by?`. Status: `needs_confirmation`, `reviewed_public`, `verified`. Nguồn phải HTTPS; thời gian hợp lệ dùng ngày Việt Nam. Chính sách/giờ/phí có status verified cần người xác nhận và khoảng ngày hiệu lực. Nội dung crawl luôn `published:false`, `needs_confirmation`. Vector được đối chiếu lại với SQLite hiện tại để loại nội dung bị xóa/thu hồi/hết hạn.

Schedule nhận `branch:'1'|'2'|'3',weekday:0..6,opens,closes,valid_from,valid_until,note,verified_by,source_url,source_title,checked_at,closed`. Thứ Hai là 0; `closed:true` dùng cho ngày nghỉ; khoảng giờ hợp lệ có dạng `HH:MM` và đóng sau mở. Không có lịch mặc định được giả định là đã xác minh.

Chi tiết chữ ký, replay, giới hạn upstream và xử lý gia hạn chưa rõ kết quả nằm trong [hợp đồng tích hợp](integrations.md). Endpoint gia hạn luôn qua backend có xác thực/xác nhận; LLM không có quyền gọi giao dịch.
