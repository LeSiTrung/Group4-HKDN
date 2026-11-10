# Kiểm thử kỹ thuật

## Tải đồng thời, Qwen và hợp đồng giao dịch07/11/2026

Xem [quy trình và giới hạn](../docs/performance-quality-validation.md) và
[báo cáo tổng hợp](../docs/validation/2026-11-07-load-quality-summary.json).
`scripts/benchmark_load.py` chỉ cho phép localhost, tối đa100 lượt, giữ rate
limit và ghi cả lỗi HTTP, p50/p95, throughput, mode/fallback. Không gọi OPAC,
đăng ký tài khoản hay giao dịch thật. `test_multi_reader_concurrency.py` kiểm
5 tài khoản giả lập lưu hội thoại đồng thời và chống đọc chéo trên DB tạm.
`test_transaction_contract.py` bổ sung11 ca hợp đồng;49 test giao dịch chọn lọc đạt.

Bộ20 câu được đóng băng bởi agent riêng, trước khi xem code/đầu ra; kết quả
ban đầu và7 biên nhận Ollama thật được giữ nguyên. Sau sửa chỉ gọi là hồi quy
trên bộ đã biết:13đạt đầy đủ/5một phần/2không đạt; Qwen với nguồn đúng5/2/0.
Không lấy HTTP200 hoặc mode làm độ chính xác hay thay nhãn AI bằng nghiệm thu
thủ thư. `test_grounded_sentence_selection.py` kiểm tra chỉ số chọn câu, nguồn,
phủ định, số cực dài và không báo giao dịch thành công; các fixture model trong
capacity/retrieval tests dùng định dạng chọn câu hiện tại, không nới kỳ vọng nguồn.

## Ngữ cảnh và nhan đề cụ thể07/11/2026

`test_conversation_memory.py` bổ sung14 ca: nhan đề mới trong ngoặc kép phải
thay ngữ cảnh cũ khi hỏi tác giả/tóm tắt/ISBN/nhà xuất bản/kệ; thiếu dữ liệu
phải nói chưa xác nhận. Hai nhan đề chưa rõ phải hỏi lại, kể cả câu hỏi tiếp
theo, không dùng lại sách cũ. Kiểm cả khách/tài khoản và URL kiểm tra số bản
bằng dữ liệu giả lập; không gửi giao dịch thật hoặc giả kết quả OPAC.
Xem [bằng chứng và kỳ vọng đã rà lại](../docs/validation/2026-11-07-conversation-regressions.json).
Backend1097/frontend144/build,49 ca offline,12 ca API mới và21 ca bạn đọc đạt;
đây không phải phép đo độ chính xác tổng quát hay kiểm thử tải production.

## Kiểm thử web và câu trả lời06/11/2026

`test_conversation_memory.py` bổ sung9 ca cách hỏi lịch sự/thiếu ngữ cảnh;
`test_hybrid_answer_routing.py` kiểm tra riêng độ tin cậy từ khóa và điểm
vector, gồm cả ý định thực sự mơ hồ. `frontend/src/guideImages.test.jsx`
kiểm tra trả focus sau đóng ảnh bằng nút, Escape và nền hộp thoại.
Đã xác nhận13 lỗi đỏ trước sửa và giữ một ca mơ hồ làm đối chứng.
Xem [bằng chứng kiểm thử web](../docs/validation/2026-11-06-web-quality.json)
cho backend1083/frontend144/build,49 ca offline,8 câu hỏi mở rộng qua API và
kiểm thử Edge thực tế ở desktop/390px. Đây là kiểm thử có giới hạn; không phải
điểm chính xác tổng quát của LLM, chấp nhận của thư viện hay kiểm thử tải.

## Định tuyến hướng dẫn tra cứu03/11/2026

`test_search_guidance.py` kiểm tra câu thật trên màn hình mở đầu và các cách hỏi cùng ý, lịch sử, nhan đề chứa từ hướng dẫn/ngoặc kép, hỏi nhiều ý và rút công bố nguồn. Bộ live riêng `evaluation/search-guidance-2026-11-03.json` kiểm cả bốn nút gợi ý với FAQ/danh mục hiện hành. Cần kiểm nội dung + nguồn + không có sách sai, không chỉ HTTP200. Xem [cách tái hiện và giới hạn](../docs/search-guidance.md).

Harness offline không truy cập OPAC để lấy tình trạng sách; các ca đó phải giữ `needs_confirmation`. Chỉ chế độ live mới dùng quan sát thực tế. Không thay đổi kỳ vọng của bộ câu hỏi đã đóng băng.

## Bộ kiểm thử biên03/11/2026

`test_assistant_edge_matrix.py`, `test_catalog_edge_matrix.py`, `test_auth_security_matrix.py` và `test_opac_transport_retry.py` tái hiện các lỗi định tuyến/thủ tục, mất từ trong nhan đề, chuyển chủ đề, số lượng, IDvượtSQLite, Unicodekhônghợp lệ, phiên hết hạn, phân tách dữ liệu và phục hồi mạng tạm thời. Frontend `failureFlows.test.jsx` kiểm tra retry, kết quả trễ, đổi tài khoản/hội thoại, xuất dữ liệu, đổi/xóa tài khoản và đóng hộp đăng nhập khi request đang chạy. Đây là ca hồi quy phát triển với dữ liệu tạm; không phải bằng chứng mọi câu tiếng Việt hoặc mọi race đều được bao phủ.

Bộ live `evaluation/edge-library-2026-11-03.json` có31tình huống, yêu cầu catalogUTH và FAQ đã nhập. Chạy trên loopback bằng Ollama hoặc không model; không bật provider có phí để thử. Bộ này được viết từ lỗi thật trước sửa, không chỉnh các benchmark đã đóng băng:

```powershell
backend/.venv/Scripts/python.exe -m pytest -q tests
backend/.venv/Scripts/python.exe scripts/evaluate.py --base-url http://127.0.0.1:8000 --cases tests/evaluation/edge-library-2026-11-03.json --output tmp/edge-library-live.json
```

Kiểm tra tải nhỏ được thực hiện trên container riêng:16lượt chào/FAQ,4luồng; chỉ đo luồng không sinhLLM. Các phép thử burst/rate-limit dùng dữ liệu và container riêng, không chạy trên deployment đang phục vụ bạn đọc. Kết quả và giới hạn tại [bằng chứng](../docs/validation/2026-11-03-edge-cases.json).

Tại root: `backend/.venv/Scripts/python.exe -m pytest -q`. Frontend: `cd frontend`, `npm test`, `npm run build`.

Test dùng database tạm, tài khoản/giao dịch giả lập; không dùng mật khẩu thư viện, gửi tin thật hay phát sinh phí. Bao gồm quyền sở hữu dữ liệu, CSRF/rate/body limits, nguồn/LLM lỗi, migration, crawler/OPAC parser, webhook signature/replay và idempotency/đối soát gia hạn.

`evaluation/questions.json` có 45 kịch bản phát triển, gồm câu hỏi trùng FAQ, cách hỏi tự nhiên, tiếp nối/đổi chủ đề, thiếu metadata, ngày/cơ sở mơ hồ và yêu cầu nhiều ý. Đây không phải held-out hay bộ nghiệm thu của thư viện. `evaluation/semantic.json` cần embedding thật.

`evaluation/public-library.json` có10 case dữ liệu/lịch thường lệ; chạy live sau khi CLI import-knowledge nhập gói `data/faq/public-library-2026-10-31.json`. Offline mặc định không tự nhập gói bổ sung. `test_public_library_data.py` dùng DB tạm kiểm import toàn bộ trước khi ghi, nhập lại giữ chỉnh sửa/rút công bố, nguồn lịch/nghỉ trưa/Chủ nhật, ưu tiên lịch ngày và giới hạn ngày/cơ sở. Đây chưa phải bộ nghiệm thu độc lập.

```powershell
backend/.venv/Scripts/python.exe scripts/evaluate.py --output tmp/evaluation-offline.json
backend/.venv/Scripts/python.exe scripts/evaluate.py --base-url http://127.0.0.1:8000 --output tmp/evaluation-api.json
backend/.venv/Scripts/python.exe scripts/evaluate.py --base-url http://127.0.0.1:8000 --cases tests/evaluation/semantic.json --output tmp/evaluation-semantic.json
```

Lệnh đầu dùng database tạm, tắt LLM/vector; live chỉ nhận API loopback có provider none/ollama để tránh phí. Đúng status/source hoặc source_ids không chứng minh mọi nội dung LLM luôn đúng. Xem docs/validation.md cho kết quả và giới hạn đã đo.

`evaluation/library-conversation.json` bổ sung10 case về chào/cảm ơn, câu ngắn, điều hướng ngoài phạm vi, tin nhắn dài và kế thừa ngữ cảnh. Chạy bằng `scripts/evaluate.py --cases tests/evaluation/library-conversation.json --output tmp/library-conversation.json` (thêm base-url để kiểm API live). Không có corpus hội thoại kiến thức chung; các test mở rộng đó đã được thay thế theo chỉ đạo chỉ hỗ trợ thư viện. `test_llm_capacity.py` kiểm tra prompt toàn văn, Unicode/history budget, capacity và provider guards bằng mock; không tự gọi API tính phí.

## CI và chạy lại tại máy

Workflow `.github/workflows/verify.yml` chạy khi push, pull request hoặc chạy thủ công. Hai job độc lập dùng Ubuntu, Python 3.11 và Node 22; token chỉ có `contents: read`, checkout không lưu credential. CI không deploy/publish và không cần secret, tài khoản thư viện, Ollama hay Qdrant đang chạy. Cài dependency vẫn cần truy cập registry; kiểm thử tích hợp dùng mock, không gọi hệ thống thư viện hoặc nhà cung cấp AI thật.

Backend đặt `LLM_PROVIDER=none`, `ENABLE_VECTORS=false`, tạo virtual environment rồi chạy pytest, restore self-test và evaluation offline. Không chạy evaluation với `--base-url` hoặc bộ semantic trong CI. Frontend dùng `npm ci` theo lockfile, `npm test` và `npm run build`.

Để chuẩn bị backend và chạy cùng các kiểm tra trong PowerShell tại root:

```powershell
py -3.11 -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements-dev.txt
$env:LLM_PROVIDER = 'none'
$env:ENABLE_VECTORS = 'false'
backend/.venv/Scripts/python.exe -m pytest -q
backend/.venv/Scripts/python.exe scripts/restore.py --self-test
backend/.venv/Scripts/python.exe scripts/evaluate.py --output tmp/evaluation-offline.json
Push-Location frontend
npm ci
npm test
npm run build
Pop-Location
```

Workflow dùng major version được tài liệu chính thức minh họa: [checkout v7](https://github.com/actions/checkout), [setup-python v7](https://github.com/actions/setup-python), [setup-node v7](https://github.com/actions/setup-node). Chạy các lệnh local không xác nhận GitHub Actions đã chạy; cần kiểm tra kết quả từng job sau khi workflow được push.

## LLM/RAG integration regressions

`test_programming_topic_precision.py` có 16 ca bổ sung từ phản hồi người dùng:
chữ C trong điểm tuyến đường, mã thiết bị, vitamin, tên tác giả hay nhãn MARC
không chứng minh nội dung lập trình. Kiểm tra từ khóa/nhan đề/smart/chat và
candidate ngữ nghĩa, đồng thời giữ tra cứu Vitamin C, nhan đề đầy đủ và tác giả
tên C. Báo cáo reader-questions cũ chỉ kiểm tra ký hiệu đã được ghi chú giới hạn;
kết quả mới ở `docs/validation/2026-11-05-programming-topic-precision.json`.

`test_reader_question_matrix.py` bổ sung 40 ca kiểm tra C/C++/C# qua từ khóa,
nhan đề, chat, tóm tắt, đề xuất và kiểm chứng chủ đề từ model; thiếu ngôn ngữ
không được trả ngôn ngữ khác vì cùng có từ “lập trình”. Các ca khác kiểm tra
nhiều thuộc tính trong một câu, thông tin thiếu, ngày nguồn listing/MARC, đổi
nhan đề, lời sửa lại yêu cầu, phần lịch sự, phủ định và “không tìm thấy”.
Dataset dùng biểu ghi thử nghiệm, model/semantic candidate được kiểm soát;
không phải điểm chất lượng trên người dùng độc lập. Chạy riêng bằng
`backend/.venv/Scripts/python.exe -m pytest tests/test_reader_question_matrix.py -q`.

`test_conversation_memory.py` có 40 ca API dùng tài khoản và biểu ghi giả lập
trong database tạm. Các chuỗi hỏi chọn cuốn thứ hai rồi hỏi tác giả, năm, tóm
tắt, đối tượng đọc và ISBN qua cửa sổ 6 tin nhắn; kiểm tra cả lời cảm ơn, đại từ
“nó/cuốn ấy”, đổi nhan đề, ưu tiên hướng dẫn, sách bị rút, đăng nhập lại và
quyền sở hữu hội thoại. Thiếu dữ liệu phải giữ trạng thái chưa xác nhận; không
được chọn một cuốn khác để thay thế. Chạy bằng
`backend/.venv/Scripts/python.exe -m pytest tests/test_conversation_memory.py -q`.
Kiểm thử này không gọi model hoặc thư viện thật, không đo khả năng nhớ vô hạn.

Các ca `test_catalog.py` kiểm tra câu tóm tắt ghi rõ nhan đề, nhan đề trùng,
thiếu tóm tắt và biểu ghi bị rút. Nhánh tìm ngữ nghĩa chưa sẵn sàng phải trả
`needs_confirmation` và cho phép thử lại. Bộ đánh giá hỗ trợ `source_url`
để so sánh đúng toàn bộ URL, gồm ID biểu ghi và trang PDF. Trường `source`
cũ tiếp tục dùng cho những ca chỉ yêu cầu nguồn theo miền hoặc loại trang.
Ca khách hỏi tiếp sau câu tóm tắt kiểm tra đúng nhan đề mới thay vì cuốn trong
lượt tra cứu cũ. Các ca phân trang rút biểu ghi giữa hai lượt rồi kiểm tra
trang thực tế và kết quả rỗng. Bộ hội thoại offline hiện có 49 ca và smoke
trên danh mục UTH có 5 ca.

Sau khi nhập metadata và MARC UTH, có thể chạy bộ smoke sau trên API cục bộ.
Ca tóm tắt yêu cầu biểu ghi OPAC ID 100 có nội dung nguồn. Chạy bộ này không
ghi dữ liệu tài khoản. Kết quả dùng để phát hiện hồi quy theo nguồn, còn đánh
giá mức phù hợp của đề xuất sách cần người đọc và cán bộ gắn nhãn độc lập.

```powershell
backend/.venv/Scripts/python.exe scripts/evaluate.py --base-url http://127.0.0.1:8000 --cases tests/evaluation/live-opac-smoke.json --output tmp/live-opac-smoke.json
```

`test_dspace_collection.py`, `test_dspace_catalog.py` and `test_training_data.py` cover bounded public collection, snapshot integrity, import preservation and frozen grouped splits. `test_dspace_chat.py` checks digital lookup and full-title follow-ups without selecting a book from lossy keyword tokens; duplicate/partial titles still clarify. The separate live `evaluation/dspace.json` requires imported public metadata and is developer regression, not staff acceptance. Model training/export dependencies stay outside the backend environment.

`test_reader_quality_gaps.py` covers public-only textual book context without
saved IDs, edition ambiguity, complete topic/author/language matches, computer
procedure omissions under a partial model selection, safe support contacts,
privacy guidance and description-only summaries. Missing MARC retains
`needs_confirmation`; publication metadata is not a confirmed content summary.
Identical citations collapse, and the existing mixed-date provenance test keeps
different dates. These exposed-set cases are regression checks, not a new
independent accuracy estimate. Latest results and limits:
`docs/validation/2026-11-07-reader-quality-summary.json`.

`test_rag_index.py` uses real local Qdrant with a deterministic fake embedding: Unicode coverage, persisted restart reuse, incremental edits, partial write/delete recovery, stale hashes, namespace and catalog filtering. `test_retrieval_pipeline.py` checks lexical/hybrid evidence selection, outage fallback, unseen evidence and complete number/URL validation. `test_rag_operations.py` checks admin/CLI diagnostics without external inference; `frontend/src/rag.test.jsx` checks the admin UI. None of these mocked-provider tests proves real model quality. See docs/validation.md for separately recorded local inference and browser checks.

`test_book_answer_style.py` verifies that author/year share a readable answer,
the title is not repeated for each attribute, unknown fields share one warning,
and listing/MARC review dates are retained. The cross-source case in
`test_grounded_sentence_selection.py` keeps one copy of an identical selected
sentence while preserving both citations. Original source wording is not rewritten.
Actual desktop browser evidence and verification bounds:
`docs/validation/2026-11-07-answer-fluency-summary.json`.
