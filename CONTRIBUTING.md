# Quy ước đóng góp

## Commit

Dùng Conventional Commits: `type(scope): mô tả ngắn`. Viết subject bằng tiếng Anh, dùng động từ chỉ hành động và giữ trong72 ký tự. Scope mô tả thành phần như `llm`, `catalog`, `crawler`, `rag`, `training`, `eval`, `docs`.

Ví dụ:

```text
feat(catalog): add title and author filters
fix(crawler): honor robots exclusions before crawl delays
test(rag): cover interrupted index rebuild recovery
docs(ops): record local Docker acceptance checks
```

Mỗi commit giải quyết một thay đổi có ý nghĩa, kèm caller, cấu hình và test cần thiết. Tách các chức năng độc lập; giữ cùng nhau những phần không thể hoạt động riêng. Không tạo commit rỗng hoặc đổi định dạng vô nghĩa để tăng số lượng. `feat` cho tính năng, `fix` cho sửa lỗi, `docs` cho tài liệu, `test` cho kiểm thử, `perf` cho cải thiện hiệu năng đã đo; chỉ dùng `refactor` khi hành vi được giữ nguyên.

## Kiểm tra trước khi push

```powershell
backend/.venv/Scripts/python.exe -m pytest
backend/.venv/Scripts/python.exe scripts/restore.py --self-test
backend/.venv/Scripts/python.exe scripts/evaluate.py --output tmp/evaluation-offline.json
Push-Location frontend
npm ci
npm test -- --run
npm run build
Pop-Location
git diff --check
git diff --cached --stat
```

Chạy kiểm tra phù hợp với thành phần thay đổi; chạy bộ hồi quy đầy đủ trước khi đẩy một đợt tích hợp. Dùng `git add -- đường-dẫn-cụ-thể` và đọc staged diff trước khi commit. Không đưa `.env`, token, tài khoản/lịch sử bạn đọc, SQLite, backup, runtime, model/checkpoint, venv hoặc file tạm vào Git. Chỉ đưa mã huấn luyện, dependency manifest và bằng chứng kỹ thuật đã loại thông tin nhạy cảm.

Push lên nhánh làm việc hiện tại bằng lệnh thông thường; không force-push hoặc tự gộp `main`. Điểm đánh giá tổng hợp và test đạt không thay thế nghiệm thu của thư viện/người dùng; ghi rõ nguồn, điều kiện đo và giới hạn trong bằng chứng kỹ thuật.
