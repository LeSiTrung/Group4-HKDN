# Kiểm chứng kỹ thuật

## Nguồn LIC và Docker/Linux thực tế — 01/11/2026

[Bằng chứng](validation/2026-11-01-data-container.json): **405 backend**, **45 frontend**, npm audit0, production build Node22 trong Docker thành công. **86/86** tình huống chat qua API trên cả Windows/baseline và Linux/candidate sau lần build/nhập dữ liệu cuối.25 kiểm tra ứng dụng/phân quyền/khởi động lại ở checkpoint ban đầu và10 kiểm tra HTTPS nội bộ/Caddy/cookie đạt; backup/restore SQLite thực tế trong Linux đạt. CA chỉ truyền cho client kiểm thử, không đổi trust store máy. Chưa nghiệm thu public DNS/ACME, sức tải hoặc toàn bộ Compose/Ollama.

[LIC](validation/2026-11-01-lic-collection.json):100 URL trang sitemap,141 outcome có phân loại,60 snapshot/30 ứng viên nội dung duy nhất. Không đồng nhất hoàn tất frontier HTML với toàn bộ PDF/ảnh/web. Đã rà riêng PDF hướng dẫn33 trang ở thư mục2024/11, phát hiện lịch khác bản2022, thêm nguồn nhưng giữ `needs_confirmation`. Bốn FAQ đã duyệt nhập idempotent, runtime31 mục/145 đoạn; nguồn bị thu hồi/hết hiệu lực vẫn được lọc. [OPAC](validation/2026-11-01-opac-access.json) xác nhận các bộ đếm qua browser nhưng robots/403 chặn bulk; không tuyên bố đã thu toàn bộ sách.

Điểm truy xuất354 câu ở mốc31/10 bên dưới là số đo lịch sử; phiên này không retrain, chỉnh test hay công bố điểm mới. Các mục cũ dưới đây ghi kết quả tại thời điểm tương ứng.

## Embedding thử nghiệm và phân trang quản trị — 31/10/2026

[Bằng chứng mới nhất](validation/2026-10-31-candidate-integration.json): **387 backend**, **45 frontend**, production build; **80/80 chat qua API cho mỗi cấu hình** với Ollama hoạt động. Truy xuất 354 câu tổng hợp qua Qdrant thật trên cùng 5.569 bản ghi: Hit@5 48,6%→66,1%, nDCG@5 0,464→0,624; 81 cải thiện/7 giảm/266 bằng nhau, không loại câu vượt ngân sách hoặc chỉnh tham số theo test. Giữ toàn bộ 7 ca giảm trong JSON để nghiệm thu; đây không phải độ chính xác người dùng thật.

Quản trị đã tìm kiếm/phân trang ở server, giảm 99,5992% payload trang đầu trong phép đo tương đương. Browser kiểm tra 20 bản ghi/trang, trang 2/279, lọc 1/1 và nguồn; tài khoản QA ở môi trường riêng đã xóa, tab/server QA đã đóng. Helper tạo snapshot chỉ sao chép bảng nội dung công khai, không sao chép tài khoản/lịch sử. Review độc lập phát hiện và sửa chấp nhận file tokenizer chưa được kiểm chứng; không còn Important/Critical trong phần được review. [Hướng dẫn chạy lại](candidate-runtime.md).

Main giữ embedding gốc. Docker Linux Engine chưa kết nối được; host/HTTPS, sức tải, nghiệp vụ thư viện thật và đánh giá cán bộ/người dùng còn chờ nghiệm thu. Các phần bên dưới là kết quả lịch sử theo từng mốc.

## Nguồn công khai và lịch thường lệ — 31/10/2026

[Bằng chứng](validation/2026-10-31-public-data.json):253 backend tests pass42.65s;45/45 thư viện,10/10 hội thoại,2/2 semantic và10/10 case dữ liệu/lịch mới qua API thật. LIC đọc30 trang/2 trang rỗng; OPAC robots disallow nên không thu catalog. PDF LIC33 trang đã trích và kiểm ảnh trang12. Nhập10 FAQ: tổng27 mục/126 đoạn; nhập lại bỏ qua10, không ghi đè. SQLite đã được sao lưu.

Đã tái hiện và sửa5 lỗi thiếu luồng lịch/import; test từ chối robots trước delay RED→GREEN503→403. Lịch thường lệ giữ needs_confirmation và nguồn, không tạo hiệu lực/người xác nhận giả. Review độc lập không có lỗi Important/Critical phạm vi import/lịch. Browser control không khả dụng; chưa smoke UI lượt này, frontend unchanged/not rerun. Không coi đây là độ chính xác AI tổng quát hoặc kho sách đầy đủ.

## Qwen3-1.7B — 30/10/2026

Model mặc định và cấu hình Ollama local đã chuyển sang `qwen3:1.7b`. [Bằng chứng](validation/2026-10-30-qwen17.json):239 backend tests,45/45 tình huống thư viện,10/10 hội thoại và2/2 probe ngữ nghĩa qua API thật; browser chat hiển thị câu trả lời và nguồn OPAC. Chỉ một probe ngữ nghĩa yêu cầu LLM sinh nội dung. Đây không phải độ chính xác tổng quát hoặc so sánh hiệu năng với4B.

Probe thực tế ban đầu trả nguyên placeholder ngôn ngữ trong prompt. Đã bổ sung yêu cầu nội dung trường Tác giả/mode rag vào evaluation (RED), sửa hướng dẫn gây nhầm (GREEN), giữ các chặn nguồn/phạm vi/fallback. Lượt probe sau sửa4915.23ms, không phải SLA. Máy local dùng GPU auto-fit; mẫu cấu hình vẫn CPU. Không đổi frontend hoặc chạy lại frontend suite; launcher dùng build hiện có. Các số liệu bên dưới thuộc model/cấu hình tại lần đo cũ.

## Pipeline LLM/RAG tích hợp — 30/10/2026

- **239/239 backend**,43.88s; một cảnh báo Starlette TestClient/httpx cũ. **42/42 frontend** trên6 file; production build thành công42 module, JS303.25kB/gzip91.23kB. Restore self-test và launcher preflight pass. Không thêm dependency.
- **45/45** câu thư viện và **10/10** câu phạm vi/tin nhắn dài pass offline và API thật; **2/2** probe semantic pass API thật. semantic-author trả mode rag, nguồn OPAC trang6,8648.44ms; author-field13836.73ms, câu dài5133 ký tự trả nguồn trong60.94ms. Các phép đo cục bộ này không phải SLA. [JSON kiểm chứng và hash mã](validation/2026-10-30-rag.json).
- CLI index thực tế17 mục/74 đoạn, model multilingual MiniLM384 chiều; Ollama0.40.2/qwen3:4b đã có, không pull thêm hoặc gọi provider trả phí. Kiểm thử Qdrant dùng thư viện thật với embedding giả có tính xác định để kiểm tra restart/tăng dần/lỗi ghi/hash/lọc/pagination; không gọi những bài này là đo chất lượng model.
- Probe riêng dùng embedding và LLM thật: bọc câu trả lời OPAC đã rà soát bằng phần mở đầu kiểm thử, tổng6.840 ký tự; giữ nội dung cần tìm ở cuối. Truy xuất semantic và model trả “Tác giả”, source ID4,13.354,98ms. Database/vector tạm riêng, không nhập nội dung kiểm thử vào kho chính. [JSON probe](validation/2026-10-30-rag-long-source.json). Đây là một ví dụ phát triển, không phải nguồn mới hoặc đánh giá độc lập.
- Browser thật trên database QA riêng: đăng nhập admin giả lập, kiểm tra catalog model, xem trích đoạn/URL/ngày nguồn OPAC, đăng xuất. Tab/server QA đã đóng. Không tạo tài khoản quản trị mặc định hoặc sửa tài khoản/dữ liệu bạn đọc trong runtime chính.
- Rà soát độc lập phát hiện số bị cắt ở biên đoạn vẫn được chấp nhận; đã tái hiện RED và sửa GREEN. Thêm chặn URL tiền tố, ưu tiên câu hỏi đã duyệt trước từ xuất hiện tình cờ, giữ thứ tự đoạn semantic tốt nhất, chặn mã sách lạ thành đề xuất và query embedding dài bị cắt. Regression cũ được giữ; không sửa expected của corpus để che lỗi.
- Nội dung vẫn17 FAQ/1 biểu ghi sách thật, không đủ danh mục đầy đủ. Nguồn/ID/số/URL được kiểm tra không bảo đảm mọi diễn giải đều faithful. Cần nghiệm thu nghiệp vụ và dữ liệu có quyền. Pipeline chỉ phục vụ thư viện; không huấn luyện model nền mới hoặc tuyên bố production hoàn chỉnh.
- PR1 và main77699cd đã có CI backend/frontend thành công29/10. Nhánh RAG mới chưa có run từ xa. Docker/Caddy/public TLS, giao dịch/kênh thật và thiết bị giọng nói vẫn chưa nghiệm thu. Chi tiết cách chạy/giới hạn: [pipeline](rag-pipeline.md).

Ngày làm việc: 28–30/10/2026. Đây là nhật ký kỹ thuật; kiểm thử cục bộ không thay thế nghiệm thu thư viện hoặc triển khai production.

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

Mốc SEARCH-03/EXPORT-01: [bằng chứng mới](validation/2026-10-31-retrieval-quality.json). Bộ25 ca `tests/evaluation/catalog-lookup.json` được cố định trước khi sửa và ràng buộc hash của5.569 metadata đang công bố. Chạy `backend/.venv/Scripts/python.exe scripts/evaluate_catalog.py --output tmp/catalog-lookup-recheck.json`; corpus đổi sẽ yêu cầu một phiên bản bộ đo mới, không âm thầm đổi nhãn. `--baseline-all` so sánh chiến lược tất cả trường của checkout hiện tại; số đo trước khi sửa đã lưu riêng trong bằng chứng. Returned precision@5 chia cho số kết quả thực trả (tối đa5), Recall@20 tính trên tập URL gold; các ca gold rỗng đo riêng. Trường tác giả còn có tên ngắn khớp tên dài, chưa có dữ liệu định danh tác giả để phân giải. Numerical ONNX/FastEmbed parity là kiểm tra chuyển đổi, không phải đo relevance hay faithfulness.

Mốc dữ liệu số/embedding31/10: [bằng chứng kỹ thuật](validation/2026-10-31-dspace-training.json), [nhập danh mục](dspace-import.md), [kết quả train](embedding-training.md). Bộ `tests/evaluation/dspace.json` cần corpus công khai đã nhập; chạy bằng `scripts/evaluate.py --base-url http://127.0.0.1:8000 --cases tests/evaluation/dspace.json --output tmp/dspace-evaluation.json`. Không coi thiếu corpus trong một checkout mới là thư viện không có tài liệu. Kiểm thử tổng hợp không thay cho nhãn do thư viện/người dùng thật rà soát.

- Authentication/history/admin/security tests chạy với database tạm chứng minh các case tự động, không thay thế kiểm tra phân quyền trên deployment đang dùng.
- Embedding/index/model cache cần kiểm tra thực bằng CLI index và câu hỏi semantic; unit test mock không chứng minh đã tải model. LLM phải được gọi thật với evidence, kiểm tra JSON/nguồn và fallback; cài model hay health 200 chưa đủ.
- OPAC backend đã nhận HTTP 403/challenge trong khảo sát ngày 28/10; browser xem được trang không chứng minh parser backend gọi được upstream. Cần quyền tích hợp từ thư viện để nghiệm thu tìm kiếm trực tiếp, không né chặn.
- Messenger/Zalo, library bridge/gia hạn và OpenAI-compatible endpoint chưa có thông tin cấp quyền/credential để nghiệm thu live. Contract tests mô phỏng không xác nhận token, phí/quota, signature bytes thực, quyền provider hoặc giao dịch thành công.
- Voice có feature detection; khả năng microphone/STT/TTS phụ thuộc trình duyệt, thiết bị và quyền người dùng. Không coi jsdom là kiểm tra giọng nói thật.
- Chưa có kết quả load test/uptime/TLS công khai, DNS/firewall, Linux native hay GPU production được xác nhận tại mốc tạo tài liệu. Cấu hình một process dành cho demo/triển khai nhỏ và phải đo tài nguyên trên máy nhóm.
