# Tài liệu hướng dẫn, chính sách đính kèm LIC

`scripts/collect_lic_attachments.py` bổ sung phần PDF/DOCX mà collector HTML chủ động bỏ qua. Công cụ chỉ xét liên kết cùng host `lic.ut.edu.vn`, dưới `/wp-content/uploads/`, xuất hiện trong snapshot HTML thư viện có checksum hợp lệ và trạng thái `accepted`. Không theo query, trang đăng nhập, redirect ngoài phạm vi, ảnh hoặc liên kết của các trang đã quarantine. Không nhập tự động vào FAQ, database, chỉ mục hay tập huấn luyện.

## Thu thập và tiếp tục

```powershell
backend/.venv/Scripts/python scripts/collect_lic_attachments.py
```

Nguồn mặc định là `backend/runtime/lic-public/pages`, đích là `backend/runtime/lic-attachments`. Có thể chọn nguồn snapshot mới bằng `--pages backend/runtime/lic-recovered-20261101/pages`. `manifest.json` ghi URL gốc/cuối, trang HTML liên kết, thời điểm lấy, content type, dung lượng và SHA-256; tệp gốc nằm trong `files/`. Tất cả nằm trong vùng runtime bị Git bỏ qua.

Mỗi lần chạy đọc lại robots và xác minh hash tệp trước khi tái sử dụng. Tệp hỏng được tải lại. Chỉ một worker, khoảng cách tối thiểu một giây hoặc dài hơn theo robots, áp dụng cả redirect. Mọi hop giữ kiểm tra HTTPS/host/IP công khai/TLS của helper hiện có. Giới hạn 16 MiB chỉ áp dụng trong tiến trình công cụ tuần tự cho lần tải attachment; giới hạn 1 MiB của ứng dụng không thay đổi. Không chạy hàm collector bằng thread trong web app vì phạm vi giới hạn tải được thay tạm thời trong module rồi khôi phục bằng `finally`.

401/403/429 hoặc 5xx dừng ngay và giữ manifest để tiếp tục sau; không đổi danh tính bot, thử đăng nhập hoặc vượt chặn. Đây là chiến lược không thử lại trong cùng lần chạy. 404/410 được ghi nhận nhưng kiểm tra lại ở lần chạy sau. HTML giả PDF, content type không phù hợp hoặc chữ ký tệp sai được quarantine và không lưu dưới dạng PDF/DOCX hợp lệ. DOCX được kiểm tra cấu trúc ZIP cơ bản, không chạy macro hay nội dung tài liệu. Đường dẫn có dot segment, backslash/control sau giải mã hoặc mã hóa lặp bị từ chối trước HTTP normalization, kể cả redirect; quy tắc bảo thủ cũng loại tên còn dấu `%` sau giải mã.

## Trích xuất offline

Lệnh dưới cần `pypdf` trong môi trường công cụ riêng; không thêm thư viện này vào backend đang chạy:

```powershell
python scripts/collect_lic_attachments.py --extract-only --output backend/runtime/lic-attachments
```

Trong lần kiểm chứng 01/11/2026, dùng Python của dự án và thêm đường dẫn gói `pypdf 6.10.0` từ runtime PDF đi kèm Codex, không cài dependency hoặc gọi API trả phí. Trích xuất kiểm tra lại định danh và hash tệp, giữ số trang và provenance trong `text/*.json`, ghi tổng hợp `extraction.json`. PDF mã hóa được bỏ qua; không đoán mật khẩu. DOCX được lưu nếu có nhưng chưa trích xuất văn bản. Văn bản của toàn bộ trang có dấu hiệu ví dụ đăng nhập được giữ trống với trạng thái `withheld_login_example`; địa chỉ email trong văn bản còn lại được ẩn. Đây là lớp giảm rò rỉ, không phải chứng nhận mọi thông tin nhạy cảm đã được phát hiện. Bản PDF gốc vẫn chỉ ở staging nội bộ.

Không có trang textless không đồng nghĩa đã lấy được toàn bộ nội dung hình ảnh. `pypdf` đọc lớp chữ, không OCR; ảnh chụp giao diện, sơ đồ hoặc thông tin nằm trong ảnh vẫn cần xem/OCR và kiểm chứng riêng. Xem [tài liệu trích xuất của pypdf](https://pypdf.readthedocs.io/en/stable/user/extract-text.html).

## Kết quả thực tế 01/11/2026

| Hạng mục | Đã đo |
|---|---:|
| PDF công khai có liên kết từ snapshot HTML được chấp nhận | 9 |
| DOCX phát hiện | 0 |
| Tệp tải thành công / lỗi / còn chờ | 9 / 0 / 0 |
| Tổng dung lượng gốc | 20.773.458 byte |
| Tái sử dụng ở lần chạy tiếp theo | 9 / 9 |
| PDF / trang trích xuất | 9 / 100 |
| Ký tự còn lại sau lọc | 29.028 |
| Trang ví dụ đăng nhập được giữ trống | 11 |
| PDF mã hóa / trang không có lớp chữ | 0 / 0 |

Chín tệp gồm hướng dẫn OPAC 2024 và 2022; hướng dẫn ebook UTH/NXB Xây dựng; STINET; CSDL công bố nhiệm vụ KH-CN Việt Nam; DSpace; tài liệu Viện KH-CN và GTVT; hướng dẫn chung năm 2024; chính sách mượn liên thư viện 2025. Nguồn snapshot HTML được tải mới trong `lic-recovered-20261101/pages` cho cùng chín URL attachment, không phát hiện thêm hoặc mất URL nào so với snapshot ban đầu. Toàn bộ chín hash tệp gốc và chín hash văn bản đã đối chiếu lại.

`complete: true` chỉ có nghĩa đã xử lý hết chín liên kết PDF/DOCX thuộc inventory này. Không bao gồm tài liệu không được liên kết, attachment chỉ nằm trong ảnh, trang chưa phát hiện/quarantine, ảnh, sách toàn văn có bản quyền, nguồn ngoài host hoặc nguồn cần đăng nhập. Việc tệp hướng dẫn được tải công khai không xác nhận quyền tải toàn văn các sách được hướng dẫn nhắc đến, quyền tái xuất bản hay quyền đưa mọi nội dung vào huấn luyện.

## Nguồn mới cần duyệt đúng phạm vi

[Chính sách mượn liên thư viện UTH – Đại học Bách khoa, ĐHQG-HCM](https://lic.ut.edu.vn/wp-content/uploads/2025/08/2025.07.08_Chinhsachmuonlienthuvien.pdf) có hai trang; đã trích xuất và render xem cả hai trang. Trang 2 ghi áp dụng từ 01/07/2025. Trang 1 nêu thời hạn 30 ngày, gia hạn 7 ngày bằng email hoặc trực tiếp khi không có bạn đọc đặt trước, tối đa 5 cuốn/lần; miễn phí mượn, người mượn trả vận chuyển và có các mức xử lý vi phạm riêng.

Đây là chính sách **mượn liên thư viện giữa hai đơn vị**, không phải quy định mượn sách nội bộ UTH. Chưa tự đưa các số này vào câu trả lời hiện hành hoặc giải quyết mâu thuẫn của các nguồn nội bộ. Giữ ngày áp dụng, đối tượng, điều kiện và nguồn trước khi duyệt. Bằng chứng render nội bộ: `tmp/lic-interlibrary-policy-20261101-1.png` và `-2.png`.

## Kiểm chứng

```powershell
backend/.venv/Scripts/python -m pytest tests/test_lic_attachments.py tests/test_lic_collection.py tests/test_integrations.py tests/test_dspace_collection.py -q
```

Các test attachment kiểm tra nguồn snapshot và URL, hash/resume/tệp hỏng, dừng khi nguồn từ chối/bận, robots và redirect, pacing, giới hạn tải được khôi phục, HTML giả PDF, thiếu thư mục nguồn, trích xuất theo số trang, lọc ví dụ đăng nhập và từ chối tệp bị sửa. Không cần chạy frontend/build vì không thay đổi ứng dụng hoặc dependency sản phẩm.
