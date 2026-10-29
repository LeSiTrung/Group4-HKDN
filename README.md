# Trợ lý Thư viện UTH

Ứng dụng React + FastAPI có hỏi đáp kèm nguồn, truy xuất ngữ nghĩa tiếng Việt, danh mục sách có nguồn và ngày đối chiếu, tài khoản/lịch sử riêng, quản trị nội dung và lịch phục vụ, thu thập trang thành bản nháp, tra cứu OPAC và các bộ kết nối thư viện/Messenger/Zalo. SQLite lưu dữ liệu nghiệp vụ; FastEmbed + Qdrant lưu chỉ mục có thể tạo lại. Ollama chạy LLM cục bộ; có thể cấu hình nhà cung cấp tương thích OpenAI khi được phép.

Không có tài khoản quản trị mặc định. Giờ mở cửa, phí và quy định chưa được thư viện xác nhận vẫn hiển thị giới hạn. Bộ kết nối đã có không đồng nghĩa dịch vụ bên ngoài đã nghiệm thu. Xem [kết quả kiểm chứng](docs/validation.md) và [các giới hạn tích hợp](docs/integrations.md).

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

Sau khi cài Ollama trên máy của nhóm, mở dịch vụ bằng `ollama serve` nếu chưa chạy, rồi tải mô hình bằng lệnh chủ động:

```powershell
ollama pull qwen3:4b
ollama list
# Dừng API trước khi CLI truy cập Qdrant local.
Push-Location backend
./.venv/Scripts/python.exe -m app.cli index
Pop-Location
```

Lần index đầu tải mô hình embedding `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` vào `backend/runtime/models`; cần mạng và dung lượng đĩa. CLI index tạo chỉ mục FAQ; chỉ mục sách được tạo khi tìm ngữ nghĩa lần đầu. Không chạy CLI index cùng API đang giữ Qdrant local: dùng nút tạo lại chỉ mục trong quản trị khi API đang chạy. `.env.example` dùng Ollama CPU (`LLM_NUM_GPU=0`) và timeout 60 giây, thấp hơn giới hạn chờ 90 giây của frontend. Chưa có mô hình/dịch vụ thì ứng dụng trả FAQ hoặc thông báo giới hạn; `/health` không chứng minh LLM đã sinh câu trả lời thành công. Muốn chạy chỉ FAQ và tìm metadata bằng từ khóa, đặt `LLM_PROVIDER=none`, `ENABLE_VECTORS=false`.

## Linux và HTTPS

Nhóm tự chuẩn bị máy chủ, DNS và TLS. [Hướng dẫn vận hành](docs/operations.md) có lệnh Linux, Docker Compose + Caddy, cấu hình origin/cookie, backup/restore và rollback. Không tự triển khai công khai hoặc gọi API tính phí trong quá trình phát triển.

## Kiểm thử

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
