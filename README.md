# D7 - Chatbot Thư viện UTH

Bộ khung ban đầu cho đề tài D7 – Chatbot thư viện. Đây là scaffold để nhóm phát triển tiếp, chưa phải sản phẩm hoàn chỉnh.

## Công nghệ dự kiến
- Frontend: React 
- Backend: Python + FastAPI
- AI: tích hợp LLM qua API ở giai đoạn tiếp theo
- Dữ liệu: PostgreSQL/pgvector có thể bổ sung sau

## Chạy backend
1. Cài Python 3.10+.
2. Mở terminal tại thư mục `backend`.
3. Tạo môi trường ảo:
   ```bash
   python -m venv .venv
   ```
4. Kích hoạt trên Windows:
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```
5. Cài thư viện:
   ```bash
   pip install -r requirements.txt
   ```
6. Chạy API:
   ```bash
   uvicorn app.main:app --reload
   ```
7. Mở http://127.0.0.1:8000/docs để xem API.

## Chạy frontend
Cần cài Node.js LTS trước. Mở terminal tại `frontend` rồi chạy:
```bash
npm install
npm run dev
```
Vite sẽ in địa chỉ website ra terminal.

## Cấu trúc
- `frontend/`: giao diện chat React.
- `backend/`: API FastAPI.
- `data/`: dữ liệu mẫu/ tài liệu thư viện (chỉ dùng tài liệu được phép).
- `docs/`: tài liệu yêu cầu và thiết kế.
- `tests/`: nơi đặt kiểm thử.

## Lưu ý
- Không đưa API key, mật khẩu hoặc dữ liệu cá nhân lên GitHub.
- Chưa tích hợp API AI, đăng nhập thư viện hoặc gia hạn sách thật.
