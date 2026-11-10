# Hướng dẫn tra cứu và yêu cầu tìm sách

## Lỗi và cách sửa

Câu trên nút gợi ý “Làm thế nào để tra cứu sách tại thư viện?” từng đi vào nhánh catalog vì bộ nhận diện thấy cụm “tra cứu sách” ở giữa câu. API trước sửa tái hiện đúng lỗi: mode `catalog`, không có nguồn hướng dẫn và có sách không liên quan. Các bài kiểm thử trước đó chưa bao phủ câu thật trên nút này.

`catalog.search_guidance` phân biệt cấu trúc hỏi cách thực hiện với yêu cầu tìm một nhan đề. Assistant dùng câu FAQ chuẩn tương ứng để chọn **nguồn đang công bố và còn hiệu lực**, giữ nguyên nội dung câu hỏi trong hội thoại. Các nhóm hướng dẫn gồm tra cứu chung, sách in, tài liệu điện tử, trường tác giả/nhan đề, tìm kiếm nâng cao và không có kết quả. Không đưa cả câu hướng dẫn vào truy vấn sách hoặc kế thừa chủ đề sách từ lượt trước.

Nội dung hướng dẫn trả trực tiếp từ FAQ đã rà soát, không sinh lại các bước bằng LLM. Nếu hướng dẫn bị rút công bố thì báo chưa tìm được nguồn, không chọn một FAQ khác chỉ vì trùng từ. Kiểm tra nguồn cuối lượt vẫn được giữ. Không có câu trả lời hoặc dữ liệu tài khoản được mã hóa cứng trong bộ nhận diện.

Từ trong nhan đề đặt trong ngoặc kép không được dùng để phân loại nghiệp vụ hoặc tách yêu cầu. Ví dụ `Tìm sách “Học Python như thế nào?”` vẫn là tìm nhan đề; `Làm thế nào để tìm sách “Python nâng cao”?` là hướng dẫn tra cứu chung. Câu có hai yêu cầu độc lập như tìm sách và hỏi hướng dẫn được yêu cầu tách rõ, không âm thầm bỏ một ý.

Câu “Đặt chỗ mượn sách khác gia hạn thế nào?” cũng được sửa để dùng nguồn nghiệp vụ trang 7. Không thực hiện đặt chỗ/gia hạn từ câu hỏi này.

## Kiểm chứng

- TDD: viết và quan sát ca thất bại trước sửa, gồm lỗi gốc, framing “phải làm gì”, lịch sử, tài liệu điện tử, nhan đề có từ hướng dẫn/ngoặc kép, nhiều ý và rút nguồn. `tests/test_search_guidance.py` có 65 ca.
- Bộ live `tests/evaluation/search-guidance-2026-11-03.json` có 33 ca, gồm nguyên văn bốn nút gợi ý. Kiểm status, nội dung, nguồn và không có book cards sai; có ca tìm Python thật để bảo vệ nhánh catalog.
- Bộ cũ `tests/evaluation/questions.json` được giữ nguyên. Lần kiểm mở rộng đầu phát hiện `reserve-vs-renew` sai tuyến, cùng `availability-followup` và `initial-availability` phụ thuộc kết quả OPAC thật. Đã sửa câu nghiệp vụ và cô lập fetch/cache trong **harness offline**, sau đó đạt 45/45. Đây không phải sửa kỳ vọng để hợp thức hóa kết quả.
- `scripts/evaluate.py` khi chạy offline dùng tình trạng chưa xác nhận, không đọc số bản rỗi trên mạng hay từ cache cũ. Live vẫn sử dụng nguồn thật. Một regression chạy harness thật và chặn transport để phát hiện tái diễn.

Kết quả cuối cùng và giới hạn: [bằng chứng kỹ thuật](validation/2026-11-03-search-guidance.json).

```powershell
backend/.venv/Scripts/python.exe -m pytest
backend/.venv/Scripts/python.exe scripts/evaluate.py --output tmp/guidance-existing-evaluation.json
backend/.venv/Scripts/python.exe scripts/evaluate.py --base-url http://127.0.0.1:8000 --cases tests/evaluation/search-guidance-2026-11-03.json --output tmp/guidance-live.json
```

## Giới hạn

Các ca phát triển không chứng minh độ chính xác 100% cho mọi câu tiếng Việt. Cần câu hỏi và đánh giá độc lập từ bạn đọc/thư viện, nhất là câu nhiều ý hoặc mơ hồ. Câu cần giờ, phí, quyền truy cập hoặc trạng thái hiện tại vẫn phải có căn cứ tương ứng. Chưa kiểm lại hình ảnh trình duyệt vì tính năng tự động hóa trình duyệt đang tắt. Bản sửa đã nạp vào API cục bộ; chưa triển khai công khai hoặc xây lại image Docker cho mốc này.
