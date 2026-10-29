# Kiểm thử kỹ thuật

Tại root: `backend/.venv/Scripts/python.exe -m pytest -q`. Frontend: `cd frontend`, `npm test`, `npm run build`.

Test dùng database tạm, tài khoản/giao dịch giả lập; không dùng mật khẩu thư viện, gửi tin thật hay phát sinh phí. Bao gồm quyền sở hữu dữ liệu, CSRF/rate/body limits, nguồn/LLM lỗi, migration, crawler/OPAC parser, webhook signature/replay và idempotency/đối soát gia hạn.

`evaluation/questions.json` có 45 kịch bản phát triển, gồm câu hỏi trùng FAQ, cách hỏi tự nhiên, tiếp nối/đổi chủ đề, thiếu metadata, ngày/cơ sở mơ hồ và yêu cầu nhiều ý. Đây không phải held-out hay bộ nghiệm thu của thư viện. `evaluation/semantic.json` cần embedding thật.

```powershell
backend/.venv/Scripts/python.exe scripts/evaluate.py --output tmp/evaluation-offline.json
backend/.venv/Scripts/python.exe scripts/evaluate.py --base-url http://127.0.0.1:8000 --output tmp/evaluation-api.json
backend/.venv/Scripts/python.exe scripts/evaluate.py --base-url http://127.0.0.1:8000 --cases tests/evaluation/semantic.json --output tmp/evaluation-semantic.json
```

Lệnh đầu dùng database tạm, tắt LLM/vector; live chỉ nhận API loopback có provider none/ollama để tránh phí. Đúng status/source hoặc source_ids không chứng minh mọi nội dung LLM luôn đúng. Xem docs/validation.md cho kết quả và giới hạn đã đo.

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
