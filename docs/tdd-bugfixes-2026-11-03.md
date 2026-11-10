# Sửa lỗi theo TDD ngày 03/11/2026

Mỗi bản sửa dưới đây bắt đầu từ test tái hiện lỗi, được chạy và quan sát thất bại đúng nguyên nhân trước khi sửa mã sản phẩm. Các test dùng SQLite tạm, React component thật và chỉ thay thế biên mạng/model bên ngoài. Không gọi giao dịch hoặc gửi tin thật tới thư viện.

| Lỗi tái hiện | Trước sửa — RED | Sau sửa |
|---|---|---|
| Phiên bị thu hồi/hết hạn trong lúc xử lý vẫn được lưu chat hoặc đọc/sửa dữ liệu riêng | 18 ca trả 200 thay vì 401 | Kiểm tra lại đúng phiên đã xác thực trong transaction; không dựa riêng vào trạng thái tài khoản. 20 ca phiên gồm kiểm tra phiên khác và không lộ bằng chứng xác thực |
| API khoản mượn trả dữ liệu sau khi phiên hết hạn | 4 ca nhận dữ liệu riêng hoặc gọi bridge khi đã hết quyền | Kiểm tra phiên trước và sau lời gọi bridge |
| Mất kết quả của yêu cầu gia hạn đã gửi khi người dùng đăng xuất | 6 ca để ledger ở pending thay vì giữ kết quả thành công/không rõ/thất bại | Ghi nhận kết quả của yêu cầu đã được phép trước, sau đó kiểm tra phiên trước khi trả thông tin riêng |
| Kết quả cũ có thể cập nhật khoản mượn của tài khoản mới dùng lại ID và khóa | 1 ca ghi đè bản ghi pending của tài khoản thay thế | Giữ kiểm tra danh tính tài khoản gốc trong transaction ghi biên nhận; vẫn cho phép ghi biên nhận nếu chỉ phiên cũ đã kết thúc |
| LLM trả chuỗi Unicode không thể mã hóa | 2 ca chấp nhận câu trả lời lỗi | Từ chối đầu ra không phải UTF-8 hợp lệ để dùng fallback; tiếng Việt và emoji hợp lệ vẫn giữ nguyên |
| Webhook có chữ ký hợp lệ nhưng trường dữ liệu chứa surrogate lỗi | 6 ca gây lỗi máy chủ hoặc xử lý nội dung sai | Kiểm tra UTF-8 trước khi claim sự kiện; tiếng Việt/emoji hợp lệ vẫn được xử lý và chống gửi lặp |
| Trả khoản mượn/kết quả gia hạn thuộc mã truy cập cũ, hoặc gửi trùng | 5 ca đầu và 3 ca bổ sung thất bại | Gắn kết quả với phiên bản mã truy cập, xóa xác nhận cũ, bỏ phản hồi trễ và khóa gửi đồng bộ |
| Gửi hai thao tác quản trị trước khi React cập nhật busy | 1 ca tạo hai POST thay vì một | Chặn tại hàm mutation chung, giữ nguyên payload và cơ chế phân quyền |

## Kiểm chứng cuối

- Toàn bộ backend: **825 passed**, không failure/error/skip. Vẫn có một cảnh báo deprecation đã tồn tại của Starlette TestClient khi dùng httpx; không che hoặc xóa test để giấu cảnh báo.
- Toàn bộ frontend: **110 passed**, 11 file; Vite production build 42 module đạt.
- `git diff --check` đạt. Image Linux `uth-library:2026-11-03-tdd` build thành công với bản mã cuối.
- API đang phục vụ được khởi động lại. Kiểm tra biên API và hai câu chat thật đạt; container riêng kiểm tra phiên hết hạn, đăng nhập lại, phân tách lịch sử, nguồn Qwen thật và giới hạn tốc độ. Dữ liệu giả được xóa, container kiểm thử được dọn sau kiểm chứng.
- MARC tiếp tục trên worker riêng, không bị khởi động trùng hoặc sửa snapshot trong lượt tìm lỗi này. Số lượng đã xác minh và thời điểm nằm trong bằng chứng JSON.

Bằng chứng, hash mã và phạm vi: [validation/2026-11-03-tdd-bugfixes.json](validation/2026-11-03-tdd-bugfixes.json).

## Lặp lại

Chạy tại thư mục repository bằng môi trường dự án:

```powershell
backend/.venv/Scripts/python -m pytest
cd frontend
npm test
npm run build
```

Các test mới: `test_session_revocation.py`, `test_loans_session.py`, `test_renewal_receipt_session.py`, `test_model_output_contract.py`, `test_webhook_text_validation.py` và `frontend/src/dialogRegression.test.jsx`.

## Giới hạn

Test giao dịch/webhook dùng bridge và provider giả lập, chưa chứng minh tích hợp thư viện hoặc kênh tin nhắn thật. Browser automation chưa khả dụng trong Work settings; chưa kiểm tra lại thiết bị hoặc trình duyệt thật. Bộ test không bao phủ mọi đầu vào, thứ tự cookie giữa nhiều tab, chất lượng semantic độc lập hay tải production. Các phép đo FAQ/container cục bộ không thay thế nghiệm thu máy đích, domain, HTTPS, restore và sức tải.
