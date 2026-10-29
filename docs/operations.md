# Vận hành D7

Một tiến trình Uvicorn + SQLite WAL + Qdrant local là cấu hình hiện tại. Không thêm `--reload`, `--workers >1`, nhiều replica hoặc cùng gắn volume Qdrant vào các API. CLI index chạy khi API đã dừng; khi đang phục vụ, dùng quản trị → tạo lại chỉ mục. Remote Qdrant có thể cấu hình nhưng chưa biến SQLite/rate limit/job hiện tại thành hệ thống phân tán.

## Cài trên Linux

Cần Python 3.11, Node.js 22/npm và tùy chọn Ollama. Từ repository, dùng tài khoản ứng dụng riêng và quyền đọc `.env` giới hạn:

```bash
python3.11 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements-dev.txt
# Chỉ copy lần đầu, không ghi đè cấu hình đang có.
cp -n backend/.env.example backend/.env
chmod 600 backend/.env
cd frontend
npm ci
npm run build
cd ../backend
.venv/bin/python -m app.cli create-admin --email admin@example.org --name 'Quản trị viên'
.venv/bin/python -m app.cli index
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 --no-proxy-headers --no-access-log
```

Lệnh index chủ động tải embedding lần đầu. `DATA_DIR` tương đối được neo vào `backend`; nếu phát hiện database theo đường dẫn làm việc cũ khác vị trí này, ứng dụng dừng để tránh mở nhầm. Đặt đường dẫn tuyệt đối tới database đang dùng trước khi tiếp tục; không xóa kho cũ để vượt lỗi. Cấu hình service manager giữ working directory `backend`, chạy dưới user ứng dụng, restart khi lỗi và dừng có thời gian để hoàn tất SQLite. Không cài Python package vào hệ thống/root. Linux native, systemd và GPU cần kiểm tra trên máy đích; không coi kiểm tra Windows là nghiệm thu Linux.

## Cấu hình

`backend/.env.example` liệt kê các biến được mã sử dụng. `.env` được nạp ở backend, còn biến môi trường có sẵn ưu tiên cao hơn. Không dùng biến `VITE_*` cho bí mật: bundle frontend công khai.

| Nhóm | Biến và ý nghĩa |
| --- | --- |
| Dữ liệu | `DATA_DIR`: SQLite, vectors, cache model. Mặc định backend/runtime khi không cấu hình |
| Browser | `COOKIE_SECURE=true` trên HTTPS; `ALLOWED_ORIGINS=https://hostname-thuc-te`, không wildcard, không path |
| Retrieval | `ENABLE_VECTORS`, `EMBEDDING_MODEL`; `QDRANT_URL`/`QDRANT_API_KEY` trống dùng local |
| LLM local | `LLM_PROVIDER=ollama`, `OLLAMA_URL`, `LLM_MODEL=qwen3:4b`, `LLM_NUM_GPU=0`, `LLM_TIMEOUT=60` trong mẫu cấu hình |
| LLM được phép | `LLM_PROVIDER=openai`, `LLM_BASE_URL` HTTPS gồm `/v1`, `LLM_API_KEY`, `LLM_MODEL` đúng provider; chỉ bật sau khi được phép sử dụng và tính phí |
| Crawl | `CRAWL_ALLOWED_HOSTS` hostname chính xác; `CRAWL_SEEDS` URL phân cách dấu phẩy; `CRAWL_INTERVAL_HOURS=0` tắt, >=1 mới chạy định kỳ |
| Library/channels | Các URL/token/secret trong [integrations.md](integrations.md); bỏ trống giữ unavailable |

Trên máy local `ollama serve` khởi động dịch vụ nếu chưa có; `ollama pull qwen3:4b` tải mô hình chủ động. `ollama list` chỉ xác nhận tệp hiện diện; phải gửi câu hỏi có nguồn qua ứng dụng để nghiệm thu sinh câu trả lời. CPU là mặc định đã chọn để tránh tranh GPU; thời gian phụ thuộc máy và cold start. Frontend chờ tối đa 90 giây; mẫu cấu hình đặt LLM timeout 60 giây để còn thời gian trả fallback. File `.env` cũ không được tự ghi đè: kiểm tra và điều chỉnh giá trị 120 nếu đang dùng. Đây là timeout HTTP, không phải cam kết tổng latency khi tải model/tạo vector lần đầu. Provider lỗi/JSON không hợp lệ dùng fallback, không bịa giao dịch.

## Docker Compose + HTTPS

Nhóm tự chuẩn bị Docker Engine/Compose v2, DNS hostname về máy, và quyền cổng 80/443 TCP; 443 UDP tùy mạng cho HTTP/3. Chỉ chạy công khai khi có quyền triển khai. Không cần đăng ký dịch vụ AI trả phí cho cấu hình Ollama.

1. Copy `.env.example` nếu chưa có, thay `SITE_DOMAIN` bằng hostname thực của nhóm (không `https://`, path hoặc port). Secret thật chỉ ở file riêng của máy chủ. `SITE_DOMAIN` trống khiến Compose dừng rõ ràng. Chọn `D7_IMAGE` là tag duy nhất cho từng bản, ví dụ `d7-library:2026-10-29`.
2. Các lệnh sau chạy từ repository. `config --quiet` kiểm tra cấu trúc mà không in secret. Không gửi output đầy đủ của `docker compose config`, `docker inspect` hoặc `.env` cho người khác.

```bash
docker compose --env-file backend/.env config --quiet
docker compose --env-file backend/.env build app
docker compose --env-file backend/.env up -d ollama
docker compose --env-file backend/.env exec ollama ollama pull qwen3:4b
docker compose --env-file backend/.env run --rm --no-deps app python -m app.cli create-admin --email admin@example.org
# API chưa chạy nên CLI có thể giữ Qdrant local.
docker compose --env-file backend/.env run --rm --no-deps app python -m app.cli index
docker compose --env-file backend/.env up -d
docker compose --env-file backend/.env ps
```

Image app chứa frontend build cùng origin, chạy UID 10001, một worker. Compose ép Secure cookie, origin HTTPS chính xác, data path `/var/lib/d7`, và Ollama URL nội bộ; không publish cổng 8000/11434. Chỉ Caddy publish cổng web. Caddy dùng hostname cụ thể, tự cấp/gia hạn TLS nếu DNS/cổng/CA hoạt động. Chứng chỉ và cấu hình Caddy có volume riêng. Image Ollama pin `0.40.2`; Caddy dùng tag `2-alpine`, Node/Python dùng tag dòng tương ứng trong Dockerfile: lưu image ID/digest đã nghiệm thu trước mỗi phát hành vì các tag dòng có thể đổi.

Proxy network dùng `172.30.47.0/29`, IP Caddy cố định `172.30.47.2`. Uvicorn chỉ tin forwarded headers từ IP đó; Caddy ghi đè client IP/scheme từ kết nối thực, không tin X-Forwarded-For của khách. Không publish API trực tiếp hoặc đổi thành trust `*`. Nếu subnet trùng mạng có sẵn, sửa đồng thời subnet, IP Caddy và `--forwarded-allow-ips` trong Compose. Khi đặt thêm CDN/proxy trước Caddy, địa chỉ thực/rate limit cần cấu hình và nghiệm thu riêng; cấu hình này dành cho Caddy là biên trực tiếp.

Volume `runtime` giữ SQLite, Qdrant và cache embedding; `ollama` giữ LLM; `caddy_data`/`caddy_config` giữ TLS. `docker compose down` giữ volume. Không dùng `down -v`, `volume prune` hoặc xóa runtime để cập nhật. Runtime local trên Windows và volume Docker là hai kho độc lập; chuyển dữ liệu bằng backup/restore được kiểm tra.

## Kiểm tra sau khởi động

```bash
curl --fail https://HOSTNAME-THUC-TE/health
docker compose --env-file backend/.env exec ollama ollama list
docker compose --env-file backend/.env logs --tail 50 app proxy
```

Thay hostname trước khi chạy. Health 200 xác nhận API/SQLite khởi động, không phải LLM hay mọi tích hợp đã được chấp nhận. Đăng nhập, gửi một FAQ, câu hỏi ngữ nghĩa, kiểm tra nguồn/cảnh báo, lịch sử; dùng tài khoản khác kiểm tra không xem được hội thoại; kiểm tra cookie Secure/HttpOnly/SameSite, 403 khi Origin lạ, 413 body quá hạn và 429 khi vượt hạn trong môi trường thử. Không chạy kiểm thử burst trên production đang phục vụ.

Không bật access log chứa URL nhạy cảm: Uvicorn tắt access log trong cấu hình bàn giao; Caddy không bật access log. Log lỗi vẫn cần quyền truy cập, luân chuyển và kiểm tra trước khi chia sẻ. Volume/backup chứa thông tin người dùng và chat; dùng phân quyền hệ điều hành, mã hóa đĩa/backup và thời hạn lưu của đơn vị. Không có cơ chế mã hóa database ở cấp ứng dụng.

## Kiến thức và crawl

Nội dung thu thập là bản nháp, không tự trở thành bằng chứng đã được thư viện duyệt. Quản trị kiểm tra trang gốc, quyền sử dụng, đoạn văn đã trích, ngày kiểm tra, trạng thái và hiệu lực trước xuất bản. Quy định/phí/giờ cần người xác nhận nghiệp vụ và khoảng ngày hiệu lực. Không diễn giải 403/challenge/robots-denied thành kết quả trống thành công; không vượt chặn của nguồn. Sau thay đổi nguồn dùng reindex ở UI; khi lỗi vector, kiểm tra cache/kết nối từ trạng thái quản trị. Dữ liệu thu hồi/hết hạn được lọc lại từ SQLite ngay cả khi vector còn cũ.

Job crawl bị ngắt được đánh dấu failed khi khởi động lại; quản trị quyết định chạy lại. Renewal/channel có trạng thái pending/uncertain cần đối soát upstream trước thử lại; không xóa ledger để ép gửi. Xem [integrations.md](integrations.md) về giới hạn delivery/idempotency.

## Danh mục và đối soát gia hạn

Quản trị → Danh mục cho phép tạo/sửa/xóa và nhập mảng JSON metadata. Mỗi mục phải có nhan đề, URL HTTPS của biểu ghi/nguồn và ngày đối chiếu không ở tương lai; kiểm tra `published` trước nhập. Mặc định bản mới là nháp. URL đã có sẽ được cập nhật toàn bộ trường trong một transaction, không tự ghép giữ trường cũ. Tối đa 200 mục mỗi request, nhưng tổng body vẫn chỉ 64 KiB: mô tả dài cần lô nhỏ hơn. Không dùng import để đưa dữ liệu chưa được phép hoặc số lượng lưu thông suy đoán. Không có tác vụ đồng bộ catalog định kỳ; seed ban đầu chỉ chạy một lần.

Tìm local dùng metadata đã xuất bản, phân trang và cảnh báo không phải tồn kho. OPAC chỉ đọc trang đầu; lỗi upstream/challenge cần mở nguồn gốc, không diễn giải là thư viện không có sách. Reindex UI/CLI tạo FAQ; chỉ mục ngữ nghĩa sách xây khi cần tìm semantic. Thay đổi sách/nội dung làm mất hiệu lực fingerprint; khi cập nhật nhiều metadata, lần truy xuất vector tiếp theo có thể chậm do rebuild.

Quản trị → Gia hạn hiển thị tối đa 100 yêu cầu mới nhất. Chỉ đánh succeeded/failed sau kiểm tra upstream hoặc đầu mối thư viện; nhập tham chiếu rõ ràng và hạn trả chính thức nếu thành công, xác nhận trách nhiệm. Thao tác chỉ ghi ledger/audit, không gọi gia hạn lần nữa. Chỉ pending/uncertain được đối soát; trạng thái đã kết thúc không được ghi đè. Người dùng còn pending/uncertain nhận 409 khi xóa tài khoản, nhưng vẫn có thể xóa hội thoại. Không sửa SQL/xóa ledger để vượt khóa này. Webhook chưa có giao diện đối soát/gửi lại tương tự; liên hệ vận hành kiểm tra delivery theo hợp đồng tích hợp.

## Backup

CLI dùng SQLite backup API để có bản nhất quán khi API đang chạy. Không copy riêng `library.sqlite3` trong khi còn WAL đang ghi. Chọn thư mục mới mỗi lần; CLI từ chối ghi đè file backup đã có.

Windows, từ `backend`:

```powershell
./.venv/Scripts/python.exe -m app.cli backup ../backups/2026-10-29-before-update
```

Docker:

```bash
docker compose --env-file backend/.env exec app python -m app.cli backup /var/lib/d7/backups/2026-10-29-before-update
mkdir -p backups/2026-10-29-before-update
docker compose --env-file backend/.env cp app:/var/lib/d7/backups/2026-10-29-before-update/library.sqlite3 backups/2026-10-29-before-update/library.sqlite3
```

Giữ bản thứ hai ngoài máy/volume nguồn với quyền giới hạn; lưu riêng `.env` bằng kho bí mật được phép và image/tag phiên bản. Database chứa ledger gia hạn/webhook, kiến thức và user; phải backup tất cả cùng nhau. Vectors là dữ liệu tái tạo, không phải bản sao duy nhất. Cache model có thể giữ riêng để tránh tải lại nhưng không thay thế backup database.

## Restore và rollback

Chỉ restore offline sau khi dừng API/proxy và có backup hiện trạng. Script `scripts/restore.py` mở nguồn read-only, kiểm tra SQLite + bảng cần thiết, chỉ ghi file đích mới và thu hồi các phiên cũ. Người dùng phải đăng nhập lại. Script không thay đổi bản gốc hoặc ghi đè dữ liệu đang có.

Windows, từ repository:

```powershell
# Dừng run.ps1 bằng Ctrl+C trước khi restore.
backend/.venv/Scripts/python.exe scripts/restore.py backups/2026-10-29-before-update/library.sqlite3 backend/runtime-recovered-2026-10-29/library.sqlite3
```

Sau đó đặt `DATA_DIR` trong `backend/.env` thành đường dẫn tuyệt đối của `backend/runtime-recovered-2026-10-29`, chạy CLI index từ backend rồi chạy API. Giữ nguyên runtime cũ để quay lại. Linux dùng cùng script với `backend/.venv/bin/python` và đường dẫn máy đích.

Docker, backup đã nằm trên host trong `backups/`:

```bash
docker compose --env-file backend/.env stop proxy app
docker compose --env-file backend/.env run --rm --no-deps -v "${PWD}/backups:/restore:ro" app python /app/scripts/restore.py /restore/2026-10-29-before-update/library.sqlite3 /var/lib/d7/recovered-2026-10-29/library.sqlite3
```

Sửa `environment.DATA_DIR` của service app trong Compose thành `/var/lib/d7/recovered-2026-10-29` (chỉ đổi `.env` không đủ vì Compose đang override), chạy `run --rm --no-deps app python -m app.cli index`, rồi `up -d`. Thư mục mới vẫn nằm trong volume bền vững. Xác nhận số lượng dữ liệu, đăng nhập mới, nguồn và lịch sử thử trước khi tiếp tục phục vụ. Giữ bản runtime cũ và tệp cấu hình trước restore.

Trước nâng cấp, tag image hiện tại để giữ lại, ví dụ `docker image tag d7-library:local d7-library:before-update-2026-10-29`, rồi backup. Rollback phần mềm bằng đặt `D7_IMAGE` về tag đã giữ và chạy `docker compose --env-file backend/.env up -d --no-build app proxy`. Database mới không được mặc định coi là tương thích phiên bản cũ: nếu schema đã đổi, restore backup trước nâng cấp vào thư mục mới và trỏ DATA_DIR tương ứng. Bản hiện tại dùng schema version 2, bổ sung bảng books và cột books/context_query của messages; ứng dụng từ chối schema mới hơn 2. Xem [schema dữ liệu](database-design.md). Không hạ schema bằng cách xóa bảng/cột.

## Nguồn cấu hình

Đối chiếu ngày 29/10/2026: [Caddy reverse proxy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy), [giới hạn request body](https://caddyserver.com/docs/caddyfile/directives/request_body), [Compose interpolation](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/). Lệnh manifest chỉ xác nhận image tag tồn tại; kiểm tra build/runtime/HTTPS thực tế vẫn phải có kết quả riêng trong [validation.md](validation.md).
