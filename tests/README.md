# Kiểm thử kỹ thuật

Tại root: `backend/.venv/Scripts/python.exe -m pytest -q`. Frontend: `cd frontend`, `npm test`, `npm run build`.

Test dùng database tạm, tài khoản/giao dịch giả lập; không dùng mật khẩu thư viện, gửi tin thật hay phát sinh phí. Bao gồm quyền sở hữu dữ liệu, CSRF/rate/body limits, nguồn/LLM lỗi, migration, crawler/OPAC parser, webhook signature/replay và idempotency/đối soát gia hạn.

`evaluation/questions.json` có 27 kịch bản phát triển, gồm câu hỏi trùng FAQ và câu tiếp nối. Đây không phải held-out hay bộ nghiệm thu của thư viện. `evaluation/semantic.json` cần embedding thật.

```powershell
backend/.venv/Scripts/python.exe scripts/evaluate.py --output tmp/evaluation-offline.json
backend/.venv/Scripts/python.exe scripts/evaluate.py --base-url http://127.0.0.1:8000 --output tmp/evaluation-api.json
backend/.venv/Scripts/python.exe scripts/evaluate.py --base-url http://127.0.0.1:8000 --cases tests/evaluation/semantic.json --output tmp/evaluation-semantic.json
```

Lệnh đầu dùng database tạm, tắt LLM/vector; live chỉ nhận API loopback có provider none/ollama để tránh phí. Đúng status/source hoặc source_ids không chứng minh mọi nội dung LLM luôn đúng. Xem docs/validation.md cho kết quả và giới hạn đã đo.
