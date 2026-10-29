# Kiểm chứng kỹ thuật

Ngày làm việc: 28–29/10/2026. Đây là nhật ký kỹ thuật; kiểm thử cục bộ không thay thế nghiệm thu thư viện hoặc triển khai production.

## Mốc hội thoại chỉ dành cho thư viện, tin nhắn dài — 29/10

- Yêu cầu mới nhất của người dùng giới hạn chatbot trong nghiệp vụ thư viện. Không giữ nhánh trả lời kiến thức chung; lời chào và câu cảm ơn vẫn được hỗ trợ. Câu ngoài phạm vi được hướng về tìm tài liệu/dịch vụ; câu hỏi thiếu căn cứ được yêu cầu làm rõ.
- Backend: **188 passed**, 25.75s, một cảnh báo deprecation TestClient/httpx. Frontend: **35 passed**, 5 file; production build thành công (JS300.60kB, gzip90.57kB; CSS27.39kB). `npm audit --audit-level=moderate`: **0 vulnerabilities**. Restore self-test và `run.ps1 -Check` pass.
- Bộ45 câu thư viện: **45/45** [offline](validation/2026-10-29-library-chat-offline.json) và **45/45** [API thật](validation/2026-10-29-library-chat-api.json). Bộ10 câu phạm vi/tin nhắn dài: **10/10** [offline](validation/2026-10-29-library-dialogue-offline.json) và **10/10** [API thật](validation/2026-10-29-library-dialogue-api.json). Hai probe ngữ nghĩa: **2/2** [API thật](validation/2026-10-29-library-chat-semantic.json); semantic-author trả mode `rag`, nguồn OPAC trang6, 7331.09ms. Đây là kiểm tra phát triển, chưa được cán bộ thư viện nghiệm thu và không đo đầy đủ tỷ lệ hallucination.
- Ca OPAC5.133 ký tự trả FAQ có nguồn ở mode `fallback` trong36.76ms sau khi thêm chặn ngân sách prompt; cùng ca trước đó phải chờ model timeout khoảng60.283s. Đây là một phép đo cục bộ, không phải SLA. Complete prompt quá lớn không được gửi cho model hoặc cắt evidence; hệ thống dùng FAQ đầy đủ làm phương án dự phòng.
- Không còn giới hạn2.000 ký tự ở ô nhập/validator câu hỏi. Bản gốc tin nhắn được nhận và lưu nguyên vẹn cho tài khoản; toàn bộ body chat tối đa1MiB, mutation khác64KiB. Câu hiện tại hoặc ngữ cảnh truy xuất hơn16.000 ký tự được yêu cầu chia nhỏ trước retrieval. Model giữ tối đa6 lượt/4.000 ký tự lịch sử có đánh dấu trích đoạn, complete prompt tối đa6.144 byte UTF-8, Ollama context8192/output1000 token và tối đa2 yêu cầu đồng thời. Không có cam kết dung lượng vô hạn.
- Thử âm11 regression phạm vi với responder ở commit `b371d79` thất bại; phiên bản mới pass. Thử prompt budget và Unicode lỗi tái hiện FAIL rồi sửa PASS. HTTP loopback thật: body UTF-8 69.015 byte được nhận với200/clarify, body1.050.015 byte bị từ chối413; `/health` trả200. Browser smoke mới chưa chạy được vì CUA báo browser user unavailable; không dùng kết quả browser cũ để khẳng định UI mới đã kiểm tra trực tiếp.
- Không thay schema, không xóa dữ liệu runtime, không gọi API trả phí. Caddy body ceiling đã cập nhật nhưng runtime Docker/Caddy/public TLS chưa được kiểm chứng; provider ngoài, danh mục đầy đủ, gia hạn thật và kênh nhắn tin thật vẫn cần quyền/cấu hình chính thức.

## Mốc cập nhật hội thoại và phản hồi — 29/10

- Backend cuối: **135 passed**, 28.27s, một cảnh báo deprecation TestClient/httpx; restore self-test và launcher preflight pass.
- Frontend cài sạch từ lock mới: **29 passed** trên Vitest4.1.12, production build pass. Kiểm tra local dùng Node24/Python3.11; workflow đặt Node22/Python3.11 trên Linux nhưng chưa có run từ xa.
- Bộ phát triển mở rộng: **45/45** deterministic ([JSON](validation/2026-10-29-quality-offline.json)), **45/45** API thật ([JSON](validation/2026-10-29-quality-api.json)), **2/2** probe ngữ nghĩa thật ([JSON](validation/2026-10-29-quality-semantic.json)). Gồm cách hỏi tự nhiên, đổi/ngắt ngữ cảnh, thuộc tính chưa biết và ngày/cơ sở mơ hồ. Không held-out, không staff-validated; vẫn chỉ có17 FAQ/1 sách thật được seed.
- API semantic-author mất2087.93ms khi đã ấm. Request ngoài phạm vi đầu tiên mất10001.2ms trong lúc khởi tạo chỉ mục lười và các kiểm tra khác đang chạy; đây là latency request, không phải đo riêng thời gian embedding. `capabilities` trong JSON là health đầu lượt, không phải trạng thái cuối.
- Browser với QA database riêng: đăng nhập admin,21 rating giả lập; trang2/2 đúng1 kết quả, lọc hữu ích đưa về trang1/1 đúng1 kết quả, đăng xuất; server/tab QA đã đóng. Không đưa các hàng giả lập vào runtime chính.
- Rà soát độc lập:6 regression mới cho “tra cứu”, đổi chủ đề, câu hỏi sở hữu sách quá hạn và ngày bổ sung; đã tái hiện FAIL rồi sửa PASS. Test feedback kiểm tra401/403, minimal projection, câu hỏi liền trước, filter/pagination, page rất lớn và cascade; UI kiểm tra text/URL không tin cậy, trạng thái và disclosure.
- Audit npm sau cập nhật báo **0** lỗ hổng ([JSON](validation/2026-10-29-quality-npm-audit.json)). Audit trước đó có3 package dev-tool bị báo, gồm tinypool/mocker/Vitest. Chọn bản Vitest4.1.12 tương thích Vite6; không chạy audit fix force hay đổi framework. Tham chiếu: [tinypool advisory](https://github.com/advisories/GHSA-85c8-ppgw-ccpr), [Vitest mocker advisory](https://github.com/advisories/GHSA-qxg6-89mg-rqv8). Audit không bảo đảm không còn lỗ hổng chưa được công bố.
- CI chỉ được xác nhận cấu hình/YAML và lệnh local. Không claim GitHub Actions, Docker, public TLS, provider giao dịch hoặc thiết bị giọng nói đã nghiệm thu.

## Kết quả chốt ngày 29/10

Sau chỉnh tên sản phẩm: chạy lại backend 101/101 (16.94s), frontend 24/24 và build thành công (JS 297.26kB, gzip89.72kB). Trang đang mở đã tải lại và hiển thị UTH Library. Các JSON đánh giá bên dưới giữ nguyên kết quả đo trước chỉnh tên; không ghi đè bằng kết quả suy đoán.

| Kiểm tra thực hiện | Kết quả |
| --- | --- |
| Backend pytest toàn bộ | 101/101, 14.45s; một cảnh báo deprecation TestClient/httpx |
| Frontend Vitest | 24/24; 3 file kiểm thử |
| Frontend production build | Thành công; JS 297.18 kB (gzip 89.69 kB), CSS 27.39 kB |
| Bộ câu hỏi deterministic, database tạm, không model | 27/27; [JSON kết quả](validation/2026-10-29-offline.json) |
| Cùng bộ câu hỏi qua API cục bộ thật | 27/27; [JSON kết quả](validation/2026-10-29-api.json) |
| Hai câu ngữ nghĩa với embedding/LLM thật | 2/2; [JSON kết quả](validation/2026-10-29-semantic.json) |
| Probe FAQ: 20 request khách, 10 worker đồng thời | 20 HTTP200 có FAQ/nguồn; tổng 510.45ms; mỗi request 50.26–410.84ms, tính cả tạo HTTP client; [JSON](validation/2026-10-29-concurrency.json) |
| Migration v1→v2 | Giữ nội dung hội thoại cũ, thêm books/context mặc định; từ chối database từ phiên bản mới hơn |
| Independent review | Tái hiện và sửa model JSON/envelope lỗi, phản hồi gia hạn muộn ghi đè đối soát; 8 case review + 6 operations pass |
| Sao lưu/phục hồi database runtime thật | Giữ schema v2 và bảng books; quick_check OK; sessions ở bản phục hồi bị thu hồi; nguồn không bị thay |
| Built-app Edge smoke | Tìm sách Olympic trả đúng biểu ghi thật; câu tiếp nối về còn sách giữ ngữ cảnh, hiển thị “Cần xác nhận” |

Lần chạy cuối backend trả exit0 và 101 passed. Các giá trị API/model/probe trong JSON đã được đo thực. Bộ câu hỏi là kiểm tra phát triển, có cả câu trùng FAQ/alias và đã dùng để sửa lỗi; không phải held-out hay tập được cán bộ thư viện xác nhận. Đúng status/source không đo đầy đủ faithfulness hoặc hallucination rate.

Routing mạnh được kiểm chứng bằng case sách giấy: trước sửa trả hướng dẫn chung qua RAG, sai nguồn mục tiêu, 28.446s; sau sửa giữ FAQ cụ thể từ trang4, 10.72ms. Probe semantic-author trả nguồn trang6, mode rag, 2065.94ms khi model đã ấm. Lần khởi tạo embedding trong bộ API mất khoảng 4.928s. Không suy rộng các phép đo này thành SLA, chất lượng trên mọi câu hỏi hoặc năng lực nhiều người dùng LLM.

Embedding: FastEmbed 0.9.1, `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, vector384 chiều, Qdrant local. LLM thật: Ollama `qwen3:4b` Q4_K_M, digest `359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`; CPU num_gpu0, context2048, temperature0. Không gọi nhà cung cấp tính phí.

Bộ nội dung ban đầu: 17 FAQ và **1** biểu ghi sách thật, không đủ để khẳng định đã có danh mục toàn thư viện. Các bản nháp/tài khoản kiểm thử browser đã được xóa đúng định danh sau khi sao lưu riêng; không có admin/mật khẩu mặc định trong gói.

## Kiểm tra gói bàn giao

| Kiểm tra | Kết quả quan sát |
| --- | --- |
| `./run.ps1 -Check` | Thành công: import dependency của venv và tìm frontend build; không khởi tạo model hay thay dữ liệu |
| PowerShell AST parse `run.ps1` | Không lỗi cú pháp |
| `backend/.venv/Scripts/python.exe scripts/restore.py --self-test` | Thành công: giữ row người dùng + ledger renewal/channel, thu hồi phiên, từ chối ghi đè/corrupt source, không để thư mục đích với corrupt source |
| Round trip `app.cli backup` → `scripts/restore.py` trên Store thật trong thư mục tạm | Thành công: user + renewal uncertain được giữ, phiên ở bản phục hồi bị thu hồi, dữ liệu/phiên nguồn không đổi, quick_check OK |
| `docker manifest inspect ollama/ollama:0.40.2` | Tag tồn tại, manifest Linux amd64/arm64; chưa chứng minh chạy container |
| `docker manifest inspect caddy:2-alpine` | Tag tồn tại; chưa chứng minh TLS/runtime |
| Compose `config --no-env-resolution` với example env và `SITE_DOMAIN=validation.invalid` | Thành công; kiểm tra cấu trúc và assert không publish app/Ollama, Secure cookie, origin HTTPS và IP proxy khớp |
| Compose với `SITE_DOMAIN` rỗng | Từ chối khởi tạo cấu hình như dự kiến |
| Docker daemon | Lần kiểm tra đầu không có pipe Docker Desktop Linux Engine; build/runtime chưa được xác nhận tại mốc này |

Dependency Python trực tiếp được pin từ `importlib.metadata` của venv đang dùng: FastAPI 0.162.0, Uvicorn 0.54.0, Pydantic 2.14.1, python-dotenv 1.2.4, HTTPX 0.28.1, BeautifulSoup 4.15.0, pwdlib 0.3.1, qdrant-client 1.20.0, FastEmbed 0.9.1, tzdata 2026.6; pytest 9.2.0 nằm ở requirements-dev. Đây chưa phải lock transitive đa nền tảng. npm dùng package-lock và `npm ci`.

## Lệnh tái lập

Từ repository trên Windows:

```powershell
backend/.venv/Scripts/python.exe -m pytest -q
backend/.venv/Scripts/python.exe scripts/restore.py --self-test
backend/.venv/Scripts/python.exe scripts/evaluate.py --output tmp/evaluation-offline.json
backend/.venv/Scripts/python.exe scripts/evaluate.py --base-url http://127.0.0.1:8000 --output tmp/evaluation-api.json
backend/.venv/Scripts/python.exe scripts/evaluate.py --base-url http://127.0.0.1:8000 --cases tests/evaluation/semantic.json --output tmp/evaluation-semantic.json
Push-Location frontend
npm test
npm run build
Pop-Location
./run.ps1 -Check
```

Sau khi có hostname thực và `.env` riêng, `docker compose --env-file backend/.env config --quiet` kiểm tra Compose. Build, Caddy validation, health, HTTPS và các luồng browser trên máy đích cần chạy như [operations.md](operations.md). Không ghi kết quả chưa chạy thành pass.

## Ranh giới nghiệm thu

- Authentication/history/admin/security tests chạy với database tạm chứng minh các case tự động, không thay thế kiểm tra phân quyền trên deployment đang dùng.
- Embedding/index/model cache cần kiểm tra thực bằng CLI index và câu hỏi semantic; unit test mock không chứng minh đã tải model. LLM phải được gọi thật với evidence, kiểm tra JSON/nguồn và fallback; cài model hay health 200 chưa đủ.
- OPAC backend đã nhận HTTP 403/challenge trong khảo sát ngày 28/10; browser xem được trang không chứng minh parser backend gọi được upstream. Cần quyền tích hợp từ thư viện để nghiệm thu tìm kiếm trực tiếp, không né chặn.
- Messenger/Zalo, library bridge/gia hạn và OpenAI-compatible endpoint chưa có thông tin cấp quyền/credential để nghiệm thu live. Contract tests mô phỏng không xác nhận token, phí/quota, signature bytes thực, quyền provider hoặc giao dịch thành công.
- Voice có feature detection; khả năng microphone/STT/TTS phụ thuộc trình duyệt, thiết bị và quyền người dùng. Không coi jsdom là kiểm tra giọng nói thật.
- Chưa có kết quả load test/uptime/TLS công khai, DNS/firewall, Linux native hay GPU production được xác nhận tại mốc tạo tài liệu. Cấu hình một process dành cho demo/triển khai nhỏ và phải đo tài nguyên trên máy nhóm.
