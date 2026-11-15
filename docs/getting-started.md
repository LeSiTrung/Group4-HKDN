# Chạy Trợ lý Thư viện UTH

Cài Git, Python 3.11, Node.js 22 và npm. Chạy các lệnh dưới đây từ thư mục gốc của bản clone, trừ khi lệnh chuyển thư mục. Thành viên cần được cấp quyền truy cập kho GitHub.

```sh
git clone https://github.com/LeSiTrung/Group4-HKDN.git
cd Group4-HKDN
```

## Windows

Mở PowerShell tại thư mục dự án.

```powershell
py -3.11 -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements-dev.txt
if (-not (Test-Path backend/.env)) { Copy-Item backend/.env.example backend/.env }

Push-Location frontend
npm.cmd ci
npm.cmd run build
Pop-Location

$env:LLM_PROVIDER = 'none'
$env:ENABLE_VECTORS = 'false'
./run.ps1 -Check
./run.ps1
```

Nếu `py -3.11` không tìm thấy Python và bạn dùng uv, thay hai lệnh đầu bằng
`uv venv --python 3.11 backend/.venv` và
`uv pip install --python backend/.venv/Scripts/python.exe -r backend/requirements-dev.txt`.
Nếu cổng 8000 đang được dùng, dừng bản chạy cũ trước khi mở bản mới.

## Linux

```bash
python3.11 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements-dev.txt
test -f backend/.env || cp backend/.env.example backend/.env

(cd frontend && npm ci && npm run build)
(cd backend && LLM_PROVIDER=none ENABLE_VECTORS=false .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 --no-proxy-headers --no-access-log)
```

Mở [ứng dụng](http://127.0.0.1:8000), [trạng thái sẵn sàng](http://127.0.0.1:8000/ready) và [API](http://127.0.0.1:8000/docs). Thử hỏi “Làm thế nào để tra cứu sách tại thư viện?” hoặc tìm “10 năm Olympic cơ học” trong danh mục. Bạn có thể đăng ký tài khoản bạn đọc trên giao diện. Dừng dịch vụ bằng Ctrl+C.

## Docker cục bộ

Cần Docker Engine hoặc Docker Desktop đã khởi động. Lệnh chạy một container cục bộ với dữ liệu mẫu. Docker giữ SQLite trong volume `uth-library-dev-data`.

```sh
docker build -t uth-library:dev .
docker run --rm --name uth-library-dev -p 127.0.0.1:8000:8000 -e LLM_PROVIDER=none -e ENABLE_VECTORS=false -v uth-library-dev-data:/var/lib/library uth-library:dev
```

Dừng ứng dụng native trước khi chạy Docker trên cùng cổng. Xem [vận hành](operations.md) để cấu hình Compose, tên miền và HTTPS.

## Cập nhật dữ liệu và bật AI

**FAQ công khai.** Để bổ sung các gói đã rà soát trong Git, dừng API và chạy các lệnh PowerShell bên dưới. Chạy lại sẽ bỏ qua các mục đã nhập. Trên Linux dùng `.venv/bin/python`.

```powershell
Push-Location backend
./.venv/Scripts/python.exe -m app.cli import-knowledge ../data/faq/public-library-2026-10-31.json
./.venv/Scripts/python.exe -m app.cli import-knowledge ../data/faq/public-library-2026-11-01.json
./.venv/Scripts/python.exe -m app.cli import-knowledge ../data/faq/public-library-2026-11-12.json
Pop-Location
```

**Danh mục đầy đủ.** Xin nhóm cấp ảnh chụp chỉ chứa dữ liệu công khai hoặc bộ JSONL, manifest và thư mục `records/` đã xác minh để [nhập OPAC và MARC](opac-import.md). Nếu cấp ảnh chụp SQLite, đặt `DATA_DIR` thành đường dẫn tuyệt đối tới thư mục riêng chứa `library.sqlite3` trước khi khởi động. Người cung cấp có thể dùng `scripts/prepare_candidate.py` để tạo ảnh chụp nội dung công khai. Không dùng database có tài khoản hoặc lịch sử của bạn đọc để chia sẻ.

**Ollama và Qdrant.** Cài Ollama, khởi động bằng `ollama serve` nếu dịch vụ chưa chạy và tải mô hình bằng `ollama pull qwen3:1.7b`. Đặt `LLM_PROVIDER=ollama`, `LLM_MODEL=qwen3:1.7b` và `ENABLE_VECTORS=true` trong `backend/.env`. Khởi động từ terminal mới để các biến dành cho chế độ FAQ ở trên không ghi đè tệp cấu hình. API xây chỉ mục ở nền. Lần đầu cần tải model embedding. Xem `capabilities.vectors.namespaces` trong [health](http://127.0.0.1:8000/health) để biết khi nào nạp xong. Với Qdrant cục bộ, dùng một tiến trình backend cho mỗi `DATA_DIR`.

**Tài khoản quản trị.** Từ thư mục `backend`, chạy lệnh dưới đây, thay email bằng email của bạn và nhập mật khẩu ít nhất 12 ký tự khi được hỏi.

```powershell
./.venv/Scripts/python.exe -m app.cli create-admin --email admin@example.org --name "Quản trị viên"
```

**Thư viện mẫu.** Dùng một `DATA_DIR` riêng, đặt `ENABLE_DEMO_RESERVATIONS=true` rồi khởi động lại. Mở mục **Thư viện mẫu** sau khi đăng nhập để thử đăng ký, nhận, gia hạn và trả sách.

## Phát triển và kiểm thử

API chính chạy cổng 8000. Để có hot reload cho React, chạy `npm run dev` từ `frontend` và mở [Vite](http://localhost:5173). Vite chuyển yêu cầu API đến backend.

```powershell
backend/.venv/Scripts/python.exe -m pytest -q
backend/.venv/Scripts/python.exe scripts/restore.py --self-test
backend/.venv/Scripts/python.exe scripts/evaluate.py --output tmp/evaluation-offline.json
Push-Location frontend
npm.cmd test
npm.cmd run build
Pop-Location
```

`backend/.env`, SQLite, chỉ mục Qdrant, model và backup thuộc máy chạy. Giữ các tệp này ngoài Git. Xem [quy ước commit](../CONTRIBUTING.md) và [kết quả kiểm thử](validation.md).
