# Trợ lý Thư viện UTH

Ứng dụng React + FastAPI có hỏi đáp kèm nguồn, truy xuất ngữ nghĩa tiếng Việt, danh mục sách có nguồn và ngày đối chiếu, tài khoản/lịch sử riêng, quản trị nội dung và lịch phục vụ, thu thập trang thành bản nháp, tra cứu OPAC và các bộ kết nối thư viện/Messenger/Zalo. SQLite lưu dữ liệu nghiệp vụ; FastEmbed + Qdrant lưu chỉ mục có thể tạo lại. Ollama chạy LLM cục bộ; có thể cấu hình nhà cung cấp tương thích OpenAI khi được phép.

Không có tài khoản quản trị mặc định. Giờ mở cửa, phí và quy định chưa được thư viện xác nhận vẫn hiển thị giới hạn. Bộ kết nối đã có không đồng nghĩa dịch vụ bên ngoài đã nghiệm thu. Xem [kết quả kiểm chứng](docs/validation.md) và [các giới hạn tích hợp](docs/integrations.md).

Mốc01/11/2026: Docker Engine đã kết nối, image Linux và HTTPS nội bộ qua Caddy đã kiểm chứng;405 test backend/45 frontend,86 tình huống chat qua API cho mỗi cấu hình Windows/Linux đạt. Runtime đã nhập các gói có31 FAQ/145 đoạn và5.569 bản ghi danh mục. [LIC collector](docs/lic-collection.md) rà141 URL phát hiện được, lưu staging có checksum; [OPAC](docs/opac-access-2026-11-01.md) vẫn cần export/API được cho phép để lấy toàn bộ danh mục. [Vận hành Docker](docs/docker-local-validation.md). Các số này không chứng minh độ chính xác AI tuyệt đối hoặc nghiệm thu production.

Bạn đọc tìm sách theo nhan đề, tác giả, chủ đề hoặc mô tả; xem chi tiết, nguồn gốc và tài liệu liên quan. Chat hỗ trợ một số câu hỏi tiếp nối về sách/cơ sở; khách gửi tối đa sáu lượt ngữ cảnh từ bộ nhớ giao diện, tài khoản dùng lịch sử riêng trên server. Quản trị có CRUD/nhập JSON danh mục và đối soát yêu cầu gia hạn chưa rõ kết quả. Danh mục là bản chụp metadata, không chứa số bản rỗi, vị trí kệ hoặc trạng thái mượn trực tiếp; ứng dụng chưa thay thế phần mềm quản lý lưu thông của thư viện.

## Chạy trên Windows

Cần Python 3.11, Node.js 22 và npm. Các lệnh dưới đây chạy từ repository; chỉ cài thư viện Python vào môi trường của dự án.

```powershell
py -3.11 -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements-dev.txt
if (-not (Test-Path -LiteralPath backend/.env)) { Copy-Item backend/.env.example backend/.env }
Push-Location frontend
npm ci
npm run build
Pop-Location
./run.ps1 -Check
./run.ps1
```

Không ghi đè `backend/.env` nếu đã cấu hình. Nếu môi trường ảo được tạo bằng uv không có pip, dùng `uv pip install --python backend/.venv/Scripts/python.exe -r backend/requirements-dev.txt`.

Mở [ứng dụng cục bộ](http://127.0.0.1:8000), [API](http://127.0.0.1:8000/docs) hoặc [health](http://127.0.0.1:8000/health). `run.ps1` kiểm tra dependency/build và chạy một tiến trình trên loopback; dừng bằng Ctrl+C. Dữ liệu giữ trong `backend/runtime`. Khi phát triển giao diện, chạy thêm `npm run dev` tại `frontend`; Vite chuyển `/api` và `/health` về cổng 8000.

Tạo quản trị viên bằng mật khẩu nhập kín (ít nhất 12 ký tự):

```powershell
Push-Location backend
./.venv/Scripts/python.exe -m app.cli create-admin --email admin@example.org --name "Quản trị viên"
Pop-Location
```

Thay email bằng email của nhóm. Lệnh không nâng quyền hay đổi mật khẩu tài khoản đã tồn tại.

## Chuẩn bị AI cục bộ

Pipeline chia đoạn, hybrid retrieval, đồng bộ chỉ mục tăng dần và công cụ quản trị đã tích hợp: xem [LLM/RAG](docs/rag-pipeline.md). Chạy `python -m app.cli ai-check` trong venv tại `backend`, hoặc vào **Quản trị → Hệ thống → Kiểm tra mô hình**. **Kiểm tra truy xuất** cho xem bằng chứng trước khi sinh câu trả lời; kiểm tra catalog model không đồng nghĩa inference đã nghiệm thu.

Sau khi cài Ollama trên máy của nhóm, mở dịch vụ bằng `ollama serve` nếu chưa chạy, rồi tải mô hình bằng lệnh chủ động:

```powershell
ollama pull qwen3:1.7b
ollama list
# Dừng API trước khi CLI truy cập Qdrant local.
Push-Location backend
./.venv/Scripts/python.exe -m app.cli import-knowledge ../data/faq/public-library-2026-10-31.json
./.venv/Scripts/python.exe -m app.cli index
Pop-Location
```

Model mặc định là `qwen3:1.7b`. Với `.env` có sẵn, đặt `LLM_MODEL=qwen3:1.7b` rồi khởi động lại API. Máy có GPU có thể đặt `LLM_NUM_GPU=-1` để Ollama tự cân đối bộ nhớ; `0` chạy CPU. Đổi LLM không cần tạo lại vector vì model embedding vẫn giữ nguyên.

Gói dữ liệu công khai bổ sung10 FAQ đã rà soát nguồn, gồm lịch thường lệ trong tài liệu LIC trang12, phòng đọc, máy tính, thủ tục mượn và tài nguyên mở. `import-knowledge` kiểm tra toàn bộ JSON trước khi ghi, bỏ qua cặp câu hỏi/URL đã tồn tại và giữ chỉnh sửa/trạng thái công bố của quản trị; không cập nhật đè. Lịch thường lệ có nguồn nhưng chưa được xác nhận hiệu lực hiện hành, nên không được dùng để khẳng định đang mở hôm nay hoặc đóng Chủ nhật/ngày lễ. [Phạm vi nguồn và giới hạn](data/documents/lic-source-manifest-2026-10-31.json):30 trang LIC đọc được,2 trang rỗng; OPAC chặn crawler bằng robots.txt. Đây không phải toàn bộ danh mục sách. Không nhập nguyên trang crawl, mật khẩu mẫu cũ hoặc nội dung ngoài thư viện vào kho trả lời.

Lần index đầu tải mô hình embedding `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` vào `backend/runtime/models`; cần mạng và dung lượng đĩa. CLI index tạo chỉ mục FAQ; chỉ mục sách được tạo khi tìm ngữ nghĩa lần đầu. Không chạy CLI index cùng API đang giữ Qdrant local: dùng nút tạo lại chỉ mục trong quản trị khi API đang chạy. `.env.example` dùng Ollama CPU (`LLM_NUM_GPU=0`) và timeout 60 giây, thấp hơn giới hạn chờ 90 giây của frontend. Chưa có mô hình/dịch vụ thì ứng dụng trả FAQ hoặc thông báo giới hạn; `/health` không chứng minh LLM đã sinh câu trả lời thành công. Muốn chạy chỉ FAQ và tìm metadata bằng từ khóa, đặt `LLM_PROVIDER=none`, `ENABLE_VECTORS=false`.

## Model embedding thử nghiệm đã tích hợp

Checkpoint đã chạy qua FastEmbed/Qdrant thật trong môi trường riêng, có kiểm tra hash model/tokenizer và tải ONNX ngoại tuyến. Trên 354 truy vấn tổng hợp cố định, nDCG@5 tăng 0,464 lên 0,624; 7 truy vấn giảm chất lượng được giữ để rà soát. Đây không phải độ chính xác trả lời người dùng thật. Main vẫn dùng embedding gốc đến khi có nghiệm thu phù hợp. Xem [cách chạy thử an toàn](docs/candidate-runtime.md) và [bằng chứng kiểm thử](docs/validation/2026-10-31-candidate-integration.json).

## Danh mục số UTH và huấn luyện embedding

Trang tra cứu có lựa chọn **Tất cả nội dung / Nhan đề / Tác giả**. Hai trường riêng tìm cụm từ không phân biệt dấu trong metadata tương ứng; chọn Tất cả nội dung để tìm rộng hoặc gần đúng. Chat hiểu “Tìm tài liệu của Nguyễn Đại Dương” và giữ ý định tác giả khi hỏi tiếp. Những tên gần giống, nhan đề trùng hoặc cách hiểu nhan đề/tác giả có thể cần làm rõ; kết quả có nguồn không xác nhận số bản đang rỗi.

[Bộ đo truy xuất cố định](docs/validation/2026-10-31-retrieval-quality.json) ghi kết quả trước/sau trên cùng danh mục; đây là kiểm tra theo metadata, không phải tỷ lệ trả lời đúng của người dùng thật. [Checkpoint đã xuất ONNX và kiểm tra FastEmbed](docs/embedding-export.md) vẫn tách riêng với model đang phục vụ; không cần cài PyTorch vào backend.

Đã thu thập5.569 metadata công khai từ5.578 mục trong sitemap thư viện số;9 mục yêu cầu xác thực được bỏ qua. Có5.568 biểu ghi hợp lệ nhập vào ứng dụng, một mục thiếu nhan đề được cách ly. Đây là tài liệu số, không phải toàn bộ sách in hoặc nội dung PDF. Dữ liệu và checkpoint nằm trong thư mục runtime cục bộ, không đi kèm bản clone Git.

Xem [thu thập/nhập dữ liệu](docs/dspace-import.md), [phạm vi truy cập](docs/catalog-data-access.md) và [huấn luyện/đo embedding](docs/embedding-training.md). Có thể chuẩn bị trước chỉ mục sách bằng `python -m app.cli index --namespace books` tại `backend` khi API đã dừng, để tránh chờ tạo chỉ mục ở lần tìm ngữ nghĩa đầu. Lệnh `index` mặc định vẫn dành cho FAQ.

Checkpoint embedding thử nghiệm đã train300 bước trên GPU cục bộ; nDCG@5 tăng0,4478→0,6297 trên354 câu kiểm thử sinh từ metadata. Chưa thay thế embedding phục vụ người dùng: cần kiểm chứng export, pipeline và câu hỏi do thư viện rà soát. Qwen3-1.7B tiếp tục là LLM sinh câu trả lời có nguồn.

## Linux và HTTPS

Nhóm tự chuẩn bị máy chủ, DNS và TLS. [Hướng dẫn vận hành](docs/operations.md) có lệnh Linux, Docker Compose + Caddy, cấu hình origin/cookie, backup/restore và rollback. Không tự triển khai công khai hoặc gọi API tính phí trong quá trình phát triển.

## Hỏi đáp và phản hồi

Chatbot chỉ hỗ trợ thư viện UTH. Bạn có thể nhắn tự nhiên, chào hỏi, tìm tài liệu và hỏi tiếp về dịch vụ; câu ngoài phạm vi được hướng lại về thư viện. Không có chế độ kiến thức chung.

Ô nhập và nhận dạng giọng nói không còn cắt ở2.000 ký tự. Server nhận tối đa1MiB tổng body cho một lượt chat và lưu nguyên văn tin nhắn đã chấp nhận vào lịch sử tài khoản. Nếu nội dung/ngữ cảnh tra cứu vượt16.000 ký tự thì chatbot yêu cầu chia phần. Ngân sách prompt LLM còn nhỏ hơn và phụ thuộc nguồn/lịch sử; khi không phù hợp, chatbot dùng câu trả lời từ nguồn đã rà soát thay vì cắt câu hỏi hoặc chờ model quá lâu. Đây không phải xử lý văn bản vô hạn.

Trang quản trị có mục **Phản hồi chatbot** để xem lượt bạn đọc đã chủ động đánh giá, lọc hữu ích/chưa hữu ích và phân trang. Chỉ câu trả lời được đánh giá, câu hỏi liền trước, nhận xét và nguồn được đưa vào mục này; không kèm email, tên tài khoản hoặc toàn bộ hội thoại. Giao diện thông báo phạm vi chia sẻ trước nút đánh giá.

Chat nhận thêm cách hỏi tự nhiên như “Có sách … không?”, “Tra cứu sách …” và câu hỏi tiếp về tác giả/năm xuất bản. Thiếu ISBN, vị trí kệ hoặc trạng thái còn sách thì giữ biểu ghi/nguồn và yêu cầu xác nhận. Điều kiện loại trừ, nhiều yêu cầu độc lập hoặc ngày phục vụ chưa hỗ trợ được hỏi rõ lại.

## Kiểm thử

Workflow `.github/workflows/verify.yml` chạy test/build khi push, pull request hoặc thủ công. CI không gọi LLM/dịch vụ tính phí, không triển khai. Kết quả local không chứng minh workflow đã chạy trên GitHub.

```powershell
backend/.venv/Scripts/python.exe -m pytest -q
backend/.venv/Scripts/python.exe scripts/restore.py --self-test
Push-Location frontend
npm test
npm run build
Pop-Location
./run.ps1 -Check
```

[Yêu cầu và giới hạn](docs/requirements.md), [thiết kế API](docs/api-design.md), [schema dữ liệu](docs/database-design.md), [vận hành](docs/operations.md), [kiểm chứng](docs/validation.md) và [hợp đồng tích hợp](docs/integrations.md) là tài liệu kỹ thuật. Tài liệu học kỳ đã có trong `docs/` được giữ nguyên; phạm vi phát triển hiện tại tập trung vào phần mềm. Kết quả test cục bộ không thay thế nghiệm thu thư viện, giao dịch thật, kênh nhắn tin hoặc triển khai HTTPS trên máy chủ đích.
