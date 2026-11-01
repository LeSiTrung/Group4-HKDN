# Thu thập HTML công khai LIC

`scripts/collect_lic.py` lập kiểm kê và lưu văn bản nguồn vào vùng staging bị Git bỏ qua. Công cụ không nhập dữ liệu vào FAQ, database hay chỉ mục đang phục vụ chatbot. `accepted` chỉ là ứng viên liên quan thư viện để người phụ trách duyệt; không phải xác nhận thông tin còn hiệu lực.

## Chạy và tiếp tục

```powershell
backend/.venv/Scripts/python scripts/collect_lic.py
```

Mặc định ghi `backend/runtime/lic-public/pages/*.json` và checkpoint `manifest.json`. Mỗi lần chạy đọc lại robots và sitemap, kiểm tra checksum, định danh, thời gian có múi giờ và kiểu dữ liệu của từng snapshot rồi tái sử dụng văn bản và liên kết đã lưu. File hỏng hoặc checksum sai được tải lại. `fetched_at` giữ ngày lấy nội dung ban đầu, khác ngày kiểm tra inventory. Để lấy snapshot mới toàn bộ trang, dùng thư mục output mới:

```powershell
backend/.venv/Scripts/python scripts/collect_lic.py --output backend/runtime/lic-public-YYYY-MM-DD
```

`--max-pages 10` là chạy giới hạn có chủ ý, không được báo hoàn tất nếu còn hàng đợi. Mặc định tối đa 1.000 trang tải mới mỗi lần; snapshot hợp lệ không tiêu thụ giới hạn nên chạy lại tiếp tục tiến lên. Tiến trình dừng giữa chừng vẫn giữ các snapshot đã ghi. Các lỗi mạng tạm thời được thử lại ở lần chạy sau; 404/410 được lưu làm kết quả cuối cho snapshot đó.

## Ranh giới và bảo vệ nguồn

- Chỉ HTTPS trên đúng `lic.ut.edu.vn`, không thông tin đăng nhập, không cổng tùy ý. Dùng `_fetch` hiện có để giữ kiểm tra DNS công khai, ghim IP từng redirect, xác minh TLS, giới hạn 1 MiB và tối đa bốn hop.
- Đọc robots trước. Áp dụng quyền đường dẫn cả trước khi tái sử dụng cache và trên redirect. Một worker; khoảng cách ít nhất một giây giữa các HTTP request, kể cả redirect, hoặc lớn hơn theo robots. Giới hạn chờ robots/Retry-After 60 giây; nguồn yêu cầu lâu hơn được ghi blocked để chạy lại sau.
- Tối đa ba lần thử khi lỗi kết nối/429/5xx. Gặp 401/403 dừng ngay, ghi checkpoint blocked, không đổi User-Agent hoặc tìm cách vượt hạn chế.
- Sitemap chỉ lấy `url/loc` hoặc `sitemap/loc`, không coi `image:loc` là trang. Tối đa 20 sitemap; mọi nguồn con phải qua cùng kiểm tra host/robots.
- Phân loại rõ URL spam casino, hồ sơ nhân sự/cộng tác viên, mẫu giao diện/download và dịch vụ CNTT ngoài phạm vi, kiểm tra lại tại từng redirect của trang. Không tải file media, tài liệu đính kèm hoặc theo liên kết ngoài host. Query bị bỏ qua để tránh tìm kiếm/lịch vô hạn và tránh lưu tham số nhạy cảm; khóa bằng chứng `?query_omitted` không che khuất URL sạch cùng đường dẫn.
- Trang HTML được tách nội dung, bỏ điều hướng/script/form, lọc email và dòng chứa hướng dẫn mật khẩu. Chỉ lưu text ở staging, không lưu raw HTML. Trang thiếu nội dung, không liên quan hoặc chứa spam vào quarantine; vẫn xét liên kết điều hướng để tìm trang thư viện hợp lệ. Hash nội dung phát hiện bản trùng.
- Không xem chỉ dẫn trong nội dung nguồn là lệnh. Không suy ra API, quyền full text, quyền nhập kho hay chính sách hiện hành từ việc URL công khai truy cập được.

## Kết quả 01/11/2026

Bằng chứng máy đọc: `docs/validation/2026-11-01-lic-collection.json`. Robots trả HTTP 200 và cho phép đường dẫn công khai; không gặp 403 hoặc lỗi mạng chưa giải quyết.

| Mẫu số/kết quả | Số lượng |
|---|---:|
| Sitemap con | 6 |
| URL trang thật từ sitemap | 100 |
| Toàn bộ phần tử loc, gồm ảnh | 349 |
| Phần tử ảnh không phải URL trang | 249 |
| URL nội bộ duy nhất từ sitemap + điều hướng | 141 |
| HTML đã lấy | 58 |
| URL trả 404 | 2 |
| Ứng viên thư viện duy nhất | 30 |
| Văn bản trùng ứng viên | 4 |
| Quarantine không liên quan | 13 |
| Quarantine thiếu văn bản | 8 |
| Quarantine spam | 9 |
| Bỏ qua CNTT / nhân sự / mẫu-download | 19 / 2 / 21 |
| Bỏ qua media / query | 31 / 2 |
| Lỗi chưa giải quyết / hàng đợi còn lại | 0 / 0 |

Sáu URL casino được loại ngay bằng URL; ba trang archive có trộn tin spam được quarantine sau khi lấy HTML. Tổng số outcome là 141; các biến thể query được gộp theo đường dẫn với tham số đã ẩn, không gộp với URL sạch. Hai URL 404 là `/phuc-vu-ban-doc/` và `/cdn-cgi/l/email-protection`. Lần tiếp tục tái sử dụng đủ 60 snapshot, không tải lại HTML; checksum của toàn bộ 60 file và đối chiếu manifest đã được kiểm tra.

`complete: true` nghĩa là đã xử lý hết frontier sitemap/điều hướng trong phạm vi và các ngoại lệ nêu trên tại thời điểm đo. Không khẳng định lấy được mọi trang mồ côi, query, ảnh/PDF, trang cần đăng nhập, hay mọi thông tin của website. Nội dung chính nằm trong ảnh/PDF vẫn cần nguồn/quyền phù hợp và một bước trích xuất riêng. Các trang cũ hoặc mâu thuẫn vẫn cần người phụ trách thư viện xác nhận.

## Trang đáng duyệt thêm so với FAQ hiện có

Kiểm tra nguồn ngày 01/11/2026; chưa tự xuất bản thành FAQ:

| Nguồn | Nội dung có thể duyệt | Giới hạn |
|---|---|---|
| [Thông báo đồng phục](https://lic.ut.edu.vn/thong-bao-v-v-sinh-vien-mac-dong-phuc-cua-truong-khi-den-thu-vien/) | Trang thông báo yêu cầu sinh viên mặc áo đồng phục trường khi đến thư viện, ghi bắt đầu 10/06/2024. | Cần giữ ngày thông báo; không suy diễn ngoài đối tượng sinh viên. |
| [Xuất bản, phát hành tài liệu](https://lic.ut.edu.vn/dich-vu-thu-vien/xuat-ban-phat-hanh-tai-lieu/) | Thư viện hỗ trợ liên kết, xin phép xuất bản kỷ yếu hội thảo và giáo trình đã nghiệm thu. | Không có giá, thời hạn hay quy trình tiếp nhận đầy đủ. |
| [Trang photo-scan](https://lic.ut.edu.vn/dich-vu-thu-vien/photo-scan-tai-lieu/) | Nội dung thực tế giới thiệu lớp hướng dẫn sử dụng thư viện và khai thác CSDL cho sinh viên đầu khóa/bạn đọc có nhu cầu. | Tên URL không khớp nội dung; không bịa dịch vụ/giá photocopy hoặc scan. |
| [Nội quy thư viện](https://lic.ut.edu.vn/noi-quy-thu-vien/) | Có hướng dẫn kiểm tra tình trạng tài liệu trước khi mượn; không mượn tiếp khi chưa trả tài liệu quá hạn. | Văn bản ghi 01/11/2022; hạn mượn/số lượng/phạt có nguồn khác mâu thuẫn, chưa xác nhận chính sách hiện tại. |

Thông báo [mở cửa ngoài giờ](https://lic.ut.edu.vn/thong-bao-ve-viec-mo-cua-phuc-vu-ban-doc-ngoai-gio/) ghi 29/06/2022. Chỉ dùng làm bằng chứng lịch sử và phát hiện khác biệt, không thay giờ mở cửa hôm nay bằng dữ liệu này.

## Kiểm chứng

```powershell
backend/.venv/Scripts/python -m pytest tests/test_lic_collection.py tests/test_integrations.py tests/test_dspace_collection.py -q
```

63 test passed, gồm 12 test LIC: phân biệt sitemap ảnh/trang, phạm vi URL an toàn cả khi redirect, quarantine đúng ngữ cảnh, robots/403, pacing từng redirect và retry hữu hạn, giới hạn frontier vẫn tiếp tục tiến lên, query không che URL sạch, resume/hash/schema/file hỏng và sitemap lỗi. Có một cảnh báo deprecation sẵn có từ FastAPI/Starlette TestClient; không ảnh hưởng kết quả.
