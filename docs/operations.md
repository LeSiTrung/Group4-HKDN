# Vận hành Chatbot thư viện

Lịch chung của ba cơ sở dùng hướng dẫn LIC 2024/11, trang 12. Thứ Hai đến thứ Sáu phục vụ 07:30–18:30, thứ Bảy 08:30–16:30, Chủ nhật và Lễ, Tết nghỉ. Dùng Quản trị → Lịch phục vụ để nhập ngoại lệ có ngày hiệu lực và nguồn. Khi bạn đọc hỏi hôm nay hoặc ngày mai, chatbot ưu tiên ngoại lệ của cơ sở vào ngày đó. [Hướng dẫn LIC, trang 12](https://lic.ut.edu.vn/wp-content/uploads/2024/11/1.HD-su-dung-thu-vien-va-khai-thac-hieu-qua-cac-CSDL-tai-nguyen-thong-tin-thu-vien.pdf#page=12).

Ngày03/11/2026: gói Docker `uth-library:2026-11-03` đã build và kiểm tra trên Linux với UID10001, model Qwen qua Ollama của máy hiện tại, readiness200 và tình huống thiếu model503. Giao diện bạn đọc bỏ nhãn định tuyến/phiên bản nội bộ. Xem [gói triển khai cục bộ](local-release.md); đây là bước chuẩn bị theo yêu cầu nhóm chưa có máy chủ/tên miền, không phải nghiệm thu publicHTTPS hay toàn bộ Compose/Ollama volume.

Kiểm chứng ngày 01/11/2026: Docker Engine đã kết nối; image Linux build/chạy dưới UID10001, API/LLM, backup/restore và HTTPS nội bộ qua Caddy đã được kiểm tra thật. Main vẫn ở cổng8000; bản Docker dùng snapshot công khai riêng ở cổng8100. Xem [hướng dẫn và giới hạn Docker](docker-local-validation.md), [bằng chứng mới nhất](validation/2026-11-01-data-container.json). Đây chưa phải nghiệm thu tên miền/ACME công khai, sức tải hoặc toàn bộ Compose/Ollama trên máy đích.

Gói FAQ ngày01/11 bổ sung4 mục đã rà nguồn, nâng runtime đã nhập gói lên31 mục/145 đoạn. Sau backup, dùng `python -m app.cli import-knowledge ../data/faq/public-library-2026-11-01.json`. Hai tài liệu giờ phục vụ2022/2024 đang khác nhau: giữ cả hai với `needs_confirmation`, không tạo lịch hiện hành hoặc tự chọn theo tên thư mục mới hơn. Lịch theo ngày/cơ sở được cán bộ xác nhận vẫn ưu tiên. [Collector LIC](lic-collection.md) chỉ lưu staging, không tự nhập/công bố HTML thô.

Pipeline LLM/RAG và cách xem nguồn/kiểm tra model: [rag-pipeline.md](rag-pipeline.md). CLI `ai-check` có thể chạy khi API phục vụ vì không mở database/Qdrant; CLI `index` cần dừng API local. Khi đang chạy, dùng quản trị để đồng bộ. Collection chunks_v1 mới giữ collection cũ; không cần migration SQLite. Không xóa volume/runtime khi đổi phiên bản.

Gói nguồn công khai: sao lưu SQLite bằng CLI `backup`, rồi từ backend chạy `python -m app.cli import-knowledge ../data/faq/public-library-2026-10-31.json`. Lệnh kiểm tra toàn bộ gói trước khi ghi. Cặp câu hỏi và URL đã có được bỏ qua để bảo toàn chỉnh sửa hoặc rút công bố. Các mục mới dùng trạng thái trong tệp đã rà soát. API đang chạy sẽ đồng bộ vector theo nội dung mới khi truy xuất. Dừng API trước khi chạy CLI index. Các mục `hours_reference` lưu tài liệu lịch cũ để đối chiếu.

Chat chỉ phục vụ thư viện. Trần gateway1MiB dành cho tin nhắn dài; middleware vẫn chặn64KiB ở mutation khác. Giữ rate/auth/origin protections. LLM dùng context8.192, ngân sách assembled prompt6.144 byte UTF8 và capacity2. Prompt quá lớn không gọi model mà dùng FAQ có nguồn; input/context quá16.000 ký tự yêu cầu chia phần. Current message trong SQLite không bị cắt; lịch sử đưa vào model là trích đoạn rõ ràng. Không coi khả năng nhập dài là suy luận vô hạn hoặc tăng số user đồng thời đã nghiệm thu.

Tên triển khai hiện tại là `uth-library`, image chọn bằng `LIBRARY_IMAGE`, dữ liệu container nằm tại `/var/lib/library`. Nếu đã triển khai một bản cũ với tên project khác, hãy sao lưu và giữ volume cũ trước khi chuyển tên; Compose mặc định đặt tên volume theo project. Dữ liệu Windows vẫn ở `backend/runtime`. Đổi tên cookie phiên yêu cầu đăng nhập lại, không xóa tài khoản/lịch sử.

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
| LLM local | `LLM_PROVIDER=ollama`, `OLLAMA_URL`, `LLM_MODEL=qwen3:1.7b`, `LLM_NUM_GPU=0`, `LLM_TIMEOUT=60` trong mẫu cấu hình |
| LLM được phép | `LLM_PROVIDER=openai`, `LLM_BASE_URL` HTTPS gồm `/v1`, `LLM_API_KEY`, `LLM_MODEL` đúng provider; chỉ bật sau khi được phép sử dụng và tính phí |
| Crawl | `CRAWL_ALLOWED_HOSTS` hostname chính xác; `CRAWL_SEEDS` URL phân cách dấu phẩy; `CRAWL_INTERVAL_HOURS=0` tắt, >=1 mới chạy định kỳ |
| Library/channels | Các URL/token/secret trong [integrations.md](integrations.md); bỏ trống giữ unavailable |

Trên máy local `ollama serve` khởi động dịch vụ nếu chưa có; `ollama pull qwen3:4b` tải mô hình chủ động. `ollama list` chỉ xác nhận tệp hiện diện; phải gửi câu hỏi có nguồn qua ứng dụng để nghiệm thu sinh câu trả lời. CPU là mặc định đã chọn để tránh tranh GPU; thời gian phụ thuộc máy và cold start. Frontend chờ tối đa 90 giây; mẫu cấu hình đặt LLM timeout 60 giây để còn thời gian trả fallback. File `.env` cũ không được tự ghi đè: kiểm tra và điều chỉnh giá trị 120 nếu đang dùng. Đây là timeout HTTP, không phải cam kết tổng latency khi tải model/tạo vector lần đầu. Provider lỗi/JSON không hợp lệ dùng fallback, không bịa giao dịch.

## Docker Compose + HTTPS

Khi chuyển sang Qwen3-1.7B, cập nhật `LLM_MODEL=qwen3:1.7b` trong `.env` hiện có rồi khởi động lại API. Có thể đặt `LLM_NUM_GPU=-1` để Ollama tự chọn số lớp GPU khi có bộ nhớ phù hợp; `0` tiếp tục chạy CPU. Không cần xóa hay tạo lại Qdrant khi chỉ đổi LLM. Giữ timeout/fallback hiện có; lượt khởi động lạnh có thể vượt timeout dù model đã được cài. API model catalog chỉ xác nhận model hiện diện, cần kiểm tra thêm phản hồi có nguồn qua chat.

Sau một câu hỏi dùng Qwen, chạy `ollama ps` và xem cột `PROCESSOR`. Trên Windows có GPU AMD tích hợp và RTX 3060 rời, nếu Ollama vẫn chọn CPU, đặt `CUDA_VISIBLE_DEVICES` bằng UUID của RTX từ `nvidia-smi -L` và `OLLAMA_VULKAN=false` trong terminal chạy `ollama serve`. Cách này đã được kiểm chứng với Ollama 0.40.16. Khởi động API với `OLLAMA_URL` trỏ tới tiến trình Ollama đang dùng CUDA.

Nhóm tự chuẩn bị Docker Engine/Compose v2, DNS hostname về máy, và quyền cổng 80/443 TCP; 443 UDP tùy mạng cho HTTP/3. Chỉ chạy công khai khi có quyền triển khai. Không cần đăng ký dịch vụ AI trả phí cho cấu hình Ollama.

1. Copy `.env.example` nếu chưa có, thay `SITE_DOMAIN` bằng hostname thực của nhóm (không `https://`, path hoặc port). Secret thật chỉ ở file riêng của máy chủ. `SITE_DOMAIN` trống khiến Compose dừng rõ ràng. Chọn `LIBRARY_IMAGE` là tag duy nhất cho từng bản, ví dụ `uth-library:2026-10-29`.
2. Các lệnh sau chạy từ repository. `config --quiet` kiểm tra cấu trúc mà không in secret. Không gửi output đầy đủ của `docker compose config`, `docker inspect` hoặc `.env` cho người khác.

```bash
docker compose --env-file backend/.env config --quiet
docker compose --env-file backend/.env build app
docker compose --env-file backend/.env up -d ollama
docker compose --env-file backend/.env exec ollama ollama pull qwen3:1.7b
docker compose --env-file backend/.env run --rm --no-deps app python -m app.cli create-admin --email admin@example.org
# API chưa chạy nên CLI có thể giữ Qdrant local.
docker compose --env-file backend/.env run --rm --no-deps app python -m app.cli index
docker compose --env-file backend/.env up -d
docker compose --env-file backend/.env ps
```

Image app chứa frontend build cùng origin, chạy UID 10001, một worker. Compose ép Secure cookie, origin HTTPS chính xác, data path `/var/lib/library`, và Ollama URL nội bộ; không publish cổng 8000/11434. Chỉ Caddy publish cổng web. Caddy dùng hostname cụ thể, tự cấp/gia hạn TLS nếu DNS/cổng/CA hoạt động. Chứng chỉ và cấu hình Caddy có volume riêng. Image Ollama pin `0.40.13`, khớp phiên bản local đã chạy Qwen; manifest Linux amd64/arm64 đã xác minh. Caddy dùng tag `2-alpine`, Node/Python dùng tag dòng tương ứng trong Dockerfile: lưu image ID/digest đã nghiệm thu trước mỗi phát hành vì các tag dòng có thể đổi.

Proxy network dùng `172.30.47.0/29`, IP Caddy là `172.30.47.2` và IP app là `172.30.47.3`. Hai địa chỉ cố định để app khởi động trước vẫn dành đúng IP cho Caddy. Uvicorn chỉ tin forwarded headers từ IP của Caddy. Caddy lấy client IP và scheme từ kết nối thực. Chỉ publish cổng của Caddy và giữ danh sách IP tin cậy cụ thể. Nếu subnet trùng mạng có sẵn, sửa đồng thời subnet, hai IP và `--forwarded-allow-ips` trong Compose. Khi đặt CDN hoặc proxy trước Caddy, kiểm tra địa chỉ client và rate limit trên máy đích.

Volume `runtime` giữ SQLite, Qdrant local và cache embedding; `ollama` giữ LLM; `qdrant_data` giữ chỉ mục Qdrant độc lập khi bật profile `qdrant`; `caddy_data`/`caddy_config` giữ TLS. `docker compose down` giữ volume. Không dùng `down -v`, `volume prune` hoặc xóa runtime để cập nhật. Runtime local trên Windows và volume Docker là hai kho độc lập; chuyển dữ liệu bằng backup/restore được kiểm tra.

Khi danh mục vượt 100.000 đoạn vector, có thể bật dịch vụ Qdrant độc lập trên mạng nội bộ `model` (không mở cổng công khai) bằng cách đặt `QDRANT_URL=http://qdrant:6333` trong `backend/.env` và chạy `docker compose --env-file backend/.env --profile qdrant up -d`. Khi tạo collection mới trên Qdrant server, ứng dụng tự tạo payload index cho trường `source_id`.

## Kiểm tra sau khởi động

```bash
curl --fail https://HOSTNAME-THUC-TE/health
docker compose --env-file backend/.env exec ollama ollama list
docker compose --env-file backend/.env logs --tail 50 app proxy
```

Thay hostname trước khi chạy. Health 200 xác nhận API/SQLite khởi động, không phải LLM hay mọi tích hợp đã được chấp nhận. Đăng nhập, gửi một FAQ, câu hỏi ngữ nghĩa, kiểm tra nguồn/cảnh báo, lịch sử; dùng tài khoản khác kiểm tra không xem được hội thoại; kiểm tra cookie Secure/HttpOnly/SameSite, 403 khi Origin lạ, 413 body quá hạn và 429 khi vượt hạn trong môi trường thử. Không chạy kiểm thử burst trên production đang phục vụ.

Không bật access log chứa URL nhạy cảm: Uvicorn tắt access log trong cấu hình bàn giao; Caddy không bật access log. Log lỗi vẫn cần quyền truy cập, luân chuyển và kiểm tra trước khi chia sẻ. Volume/backup chứa thông tin người dùng và chat; dùng phân quyền hệ điều hành, mã hóa đĩa/backup và thời hạn lưu của đơn vị. Không có cơ chế mã hóa database ở cấp ứng dụng.

## Giọng đọc tiếng Việt

Ứng dụng dùng giọng tiếng Việt cài sẵn trên thiết bị khi có. Để hỗ trợ trình duyệt
thiếu giọng Việt, cài Piper CLI trong môi trường Python của backend và tải model
vào thư mục `tts` bên trong `DATA_DIR`. Ví dụ trên Linux, chạy từ `backend/` với
môi trường ảo đã kích hoạt và `DATA_DIR` mặc định:

```sh
python -m pip install piper-tts==1.8.0
python -m piper.download_voices --download-dir runtime/tts vi_VN-vais1000-medium
```

Piper chạy trên máy chủ khi bạn đọc bấm nút. Backend nhận tối đa 4.000 ký tự mỗi
lượt và xử lý một yêu cầu tổng hợp giọng nói tại một thời điểm. Docker mặc định
cần cài thêm Piper và đặt hai tệp model trong `DATA_DIR/tts` để bật phương án này.
Xem [tài liệu Piper](https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/API_PYTHON.md)
và [thẻ model VAIS1000](https://huggingface.co/rhasspy/piper-voices/blob/main/vi/vi_VN/vais1000/medium/MODEL_CARD).

## Kiến thức và crawl

Nội dung thu thập là bản nháp, không tự trở thành bằng chứng đã được thư viện duyệt. Quản trị kiểm tra trang gốc, quyền sử dụng, đoạn văn đã trích, ngày kiểm tra, trạng thái và hiệu lực trước xuất bản. Quy định/phí/giờ cần người xác nhận nghiệp vụ và khoảng ngày hiệu lực. Không diễn giải 403/challenge/robots-denied thành kết quả trống thành công; không vượt chặn của nguồn. Sau thay đổi nguồn dùng reindex ở UI; khi lỗi vector, kiểm tra cache/kết nối từ trạng thái quản trị. Dữ liệu thu hồi/hết hạn được lọc lại từ SQLite ngay cả khi vector còn cũ.

Job crawl bị ngắt được đánh dấu failed khi khởi động lại; quản trị quyết định chạy lại. Renewal/channel có trạng thái pending/uncertain cần đối soát upstream trước thử lại; không xóa ledger để ép gửi. Xem [integrations.md](integrations.md) về giới hạn delivery/idempotency.

## Danh mục và đối soát gia hạn

Quản trị → Danh mục cho phép tạo/sửa/xóa và nhập mảng JSON metadata. Mỗi mục phải có nhan đề, URL HTTPS của biểu ghi/nguồn và ngày đối chiếu không ở tương lai; kiểm tra `published` trước nhập. Mặc định bản mới là nháp. URL đã có sẽ được cập nhật toàn bộ trường trong một transaction, không tự ghép giữ trường cũ. Tối đa 200 mục mỗi request, nhưng tổng body vẫn chỉ 64 KiB: mô tả dài cần lô nhỏ hơn. Không dùng import để đưa dữ liệu chưa được phép hoặc số lượng lưu thông suy đoán. Không có tác vụ đồng bộ catalog định kỳ; seed ban đầu chỉ chạy một lần.

Tìm local dùng metadata đã xuất bản, phân trang và cảnh báo không phải tồn kho. OPAC chỉ đọc trang đầu; lỗi upstream/challenge cần mở nguồn gốc, không diễn giải là thư viện không có sách. Reindex UI/CLI tạo FAQ; chỉ mục ngữ nghĩa sách xây khi cần tìm semantic. Thay đổi sách/nội dung làm mất hiệu lực fingerprint; khi cập nhật nhiều metadata, lần truy xuất vector tiếp theo có thể chậm do rebuild.

### Nhập biểu ghi MARC đã thu thập

Chạy từ thư mục gốc trên Windows với dữ liệu cục bộ mặc định. Trước khi áp
dụng, thử trên bản sao nội dung và kiểm tra số liệu nhập. Dừng API dùng chỉ
mục Qdrant cục bộ trước khi chạy lệnh dựng chỉ mục thủ công.

```powershell
$python = './backend/.venv/Scripts/python.exe'
$collection = 'backend/runtime/opac-public-20261101'
& $python scripts/import_opac.py "$collection/catalog-listings.jsonl"
& $python -m scripts.enrich_opac_marc $collection
```

Đối chiếu số biểu ghi thiếu với manifest. Sao lưu SQLite theo hướng dẫn bên
dưới, rồi chạy hai bước nhập theo thứ tự. Chọn thư mục sao lưu mới cho mỗi
lần cập nhật.

```powershell
& $python scripts/import_opac.py "$collection/catalog-listings.jsonl" --apply --publish
if ($LASTEXITCODE -ne 0) { throw 'Kiểm tra báo cáo nhập OPAC trước khi tiếp tục.' }
& $python -m scripts.enrich_opac_marc $collection --apply backend/runtime/library.sqlite3
```

Lệnh nhập giữ các nhan đề đã có. Khi từ khóa OPAC vượt giới hạn 1.000 ký tự,
danh mục lấy phần đầu đến hết từ khóa hoàn chỉnh. Tệp nguồn giữ chuỗi đầy đủ.
Lệnh làm giàu chỉ lấy chủ đề, tóm tắt và đối tượng đọc từ các trường MARC
được hỗ trợ. Biểu ghi thiếu MARC vẫn tra cứu được theo danh mục đã thu thập.
Khởi động API để đồng bộ chỉ mục sách và kiểm tra trạng thái
`capabilities.vectors.namespaces.books` tại `/health`.

Quản trị → Gia hạn hiển thị tối đa 100 yêu cầu mới nhất. Chỉ đánh succeeded/failed sau kiểm tra upstream hoặc đầu mối thư viện; nhập tham chiếu rõ ràng và hạn trả chính thức nếu thành công, xác nhận trách nhiệm. Thao tác chỉ ghi ledger/audit, không gọi gia hạn lần nữa. Chỉ pending/uncertain được đối soát; trạng thái đã kết thúc không được ghi đè. Người dùng còn pending/uncertain nhận 409 khi xóa tài khoản, nhưng vẫn có thể xóa hội thoại. Không sửa SQL/xóa ledger để vượt khóa này. Webhook chưa có giao diện đối soát/gửi lại tương tự; liên hệ vận hành kiểm tra delivery theo hợp đồng tích hợp.

## Backup

CLI dùng SQLite backup API để có bản nhất quán khi API đang chạy. Không copy riêng `library.sqlite3` trong khi còn WAL đang ghi. Chọn thư mục mới mỗi lần; CLI từ chối ghi đè file backup đã có.

Windows, từ `backend`:

```powershell
./.venv/Scripts/python.exe -m app.cli backup ../backups/2026-10-29-before-update
```

Docker:

```bash
docker compose --env-file backend/.env exec app python -m app.cli backup /var/lib/library/backups/2026-10-29-before-update
mkdir -p backups/2026-10-29-before-update
docker compose --env-file backend/.env cp app:/var/lib/library/backups/2026-10-29-before-update/library.sqlite3 backups/2026-10-29-before-update/library.sqlite3
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
docker compose --env-file backend/.env run --rm --no-deps -v "${PWD}/backups:/restore:ro" app python /app/scripts/restore.py /restore/2026-10-29-before-update/library.sqlite3 /var/lib/library/recovered-2026-10-29/library.sqlite3
```

Sửa `environment.DATA_DIR` của service app trong Compose thành `/var/lib/library/recovered-2026-10-29` (chỉ đổi `.env` không đủ vì Compose đang override), chạy `run --rm --no-deps app python -m app.cli index`, rồi `up -d`. Thư mục mới vẫn nằm trong volume bền vững. Xác nhận số lượng dữ liệu, đăng nhập mới, nguồn và lịch sử thử trước khi tiếp tục phục vụ. Giữ bản runtime cũ và tệp cấu hình trước restore.

Trước nâng cấp, tag image hiện tại để giữ lại, ví dụ `docker image tag uth-library:local uth-library:before-update-2026-10-29`, rồi backup. Rollback phần mềm bằng đặt `LIBRARY_IMAGE` về tag đã giữ và chạy `docker compose --env-file backend/.env up -d --no-build app proxy`. Database mới không được mặc định coi là tương thích phiên bản cũ: nếu schema đã đổi, restore backup trước nâng cấp vào thư mục mới và trỏ DATA_DIR tương ứng. Bản hiện tại dùng schema 3. Lần mở đầu tiên sau nâng cấp sẽ chuyển mã hội thoại và tin nhắn sang AUTOINCREMENT. Sao lưu trước khi mở kho bằng bản mới. Xem [schema dữ liệu](database-design.md). Không hạ schema bằng cách xóa bảng/cột.

## Nguồn cấu hình

Nếu Docker Desktop trên Windows đã chạy nhưng build báo không tìm thấy
`docker-credential-desktop`, kiểm tra thư mục chứa `docker.exe`. Trong phiên
PowerShell hiện tại có thể bổ sung thư mục đó vào PATH rồi thử lại; không cần
xóa cấu hình hoặc kho thông tin đăng nhập:

```powershell
$dockerBin = Split-Path -Parent (Get-Command docker.exe).Source
$env:PATH = "$dockerBin;$env:PATH"
docker version
docker build --pull=false -t uth-library:local .
```

`docker compose config --quiet` cần `SITE_DOMAIN` qua `--env-file backend/.env`
hoặc biến môi trường của shell. Giá trị `localhost` chỉ dùng để kiểm tra cấu hình
cục bộ; trước khi chạy công khai phải dùng tên miền và môi trường được phê duyệt.
Build image và smoke với kho seed/model tắt không xác minh toàn bộ Compose,
HTTPS, dữ liệu đã nhập hoặc model trong container.

Đối chiếu ngày 29/10/2026: [Caddy reverse proxy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy), [giới hạn request body](https://caddyserver.com/docs/caddyfile/directives/request_body), [Compose interpolation](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/). Lệnh manifest chỉ xác nhận image tag tồn tại; kiểm tra build/runtime/HTTPS thực tế vẫn phải có kết quả riêng trong [validation.md](validation.md).
