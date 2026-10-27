# D7 - Chatbot Thư viện UTH

Bộ khung ban đầu cho đề tài D7 – Chatbot thư viện. Đây là scaffold để nhóm phát triển tiếp, chưa phải sản phẩm hoàn chỉnh.

## Công nghệ dự kiến
- Frontend: React + HTML + CSS
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

## Tài liệu Học kỳ doanh nghiệp

- [Kế hoạch thực hiện đề tài](docs/ke-hoach-d7-chatbot-thu-vien.md): phạm vi, lịch đến 28/12/2026 và tiêu chí đánh giá.
- [Nguồn báo cáo LaTeX](docs/bao-cao-hkdn/main.tex): hiện có Chương 1, danh sách nhóm và tài liệu tham khảo.
- [Bản PDF bàn giao](output/pdf/chuong-1-gioi-thieu-don-vi.pdf).

Tài liệu báo cáo được soạn bằng LaTeX. Cần XeLaTeX hoặc Tectonic và phông Times New Roman. Từ thư mục `docs/bao-cao-hkdn`, chạy:

```powershell
tectonic main.tex
```

Nếu dùng XeLaTeX, chạy hai lần để cập nhật mục lục và trích dẫn:

```powershell
xelatex -interaction=nonstopmode -halt-on-error main.tex
xelatex -interaction=nonstopmode -halt-on-error main.tex
```

Sau khi kiểm tra bố cục, cập nhật PDF trong `output/pdf/` từ bản `main.pdf` vừa biên dịch. Tệp build và ảnh kiểm tra tạm không đưa vào Git.

Hình thức tham khảo mẫu TTTN do LIC công bố năm 2022; bố cục nội dung theo hướng dẫn HKDN nhóm được cung cấp. Lớp của các thành viên và các thông tin chưa xác nhận cần được hoàn thiện trước khi nộp. Ghi chú nguồn và biên tập nằm trong `docs/bao-cao-hkdn/ghi-chu-bien-tap.tex`, không đưa vào bản PDF nộp.

## Lưu ý
- Không đưa API key, mật khẩu hoặc dữ liệu cá nhân lên GitHub.
- Chưa tích hợp API AI, đăng nhập thư viện hoặc gia hạn sách thật.
