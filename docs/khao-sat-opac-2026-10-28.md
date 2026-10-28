# Khảo sát hướng dẫn và website OPAC UTH

Ngày kiểm tra: 28/10/2026. Phạm vi: đọc tài liệu và thao tác tra cứu công khai; không đăng nhập, đặt mượn hoặc gia hạn.

## 1. Nguồn và cách kiểm tra

- Tệp người dùng cung cấp: `D:/Download/HDSD_TRACUU_OPAC.v1.1.pdf`, 13 trang, 1.821.058 byte.
- SHA-256: `3eb7a16a5e30e61bb35a581aaa228ad32b3914a00c4ed52b1cf083b028953f56`.
- Metadata PDF ghi ngày tạo/sửa 28/03/2023. Đây là metadata tệp, không xác nhận ngày ban hành hoặc hiệu lực nội dung.
- Đã trích đọc toàn bộ 13 trang, render và xem ba bảng ảnh tổng hợp; xem thêm ảnh lớn trang 11 để kiểm tra thông tin nằm trong ảnh.
- [OPAC công khai](https://opacthuvien.ut.edu.vn/opac/) mở được qua trình duyệt. Công cụ đọc web vẫn nhận 403; không dùng kết quả đó để kết luận website ngừng hoạt động.
- Trang chủ OPAC nhúng PDF tại [đường dẫn cùng tên](https://opacthuvien.ut.edu.vn/opac/Upload/HDSD_TRACUU_OPAC.v1.1.pdf). Đã quan sát đường dẫn nhúng, chưa tải bản online để so hash với bản người dùng gửi.

## 2. PDF thực sự hướng dẫn những gì?

| Trang PDF | Nội dung | Cách dùng cho chatbot |
| --- | --- | --- |
| 1–2 | Đi từ website trường/LIC tới OPAC; tên phần mềm EMICLIB | Dùng liên kết HTTPS trực tiếp tới OPAC thay đường dẫn/menu cũ khi hướng dẫn |
| 3 | Tìm toàn bộ bằng từ khóa, Enter hoặc kính lúp; phân biệt tài liệu số trong giao diện minh họa | FAQ tìm kiếm cơ bản; không chỉ dựa vào màu để nhận biết loại tài liệu |
| 4–5 | Chọn loại tài liệu, ví dụ sách truyền thống; ví dụ “Lý thuyết tàu” có 23 kết quả trong ảnh | FAQ lọc loại; 23 là số minh họa cũ, không đưa thành kết quả hiện tại |
| 6 | Duyệt theo nhan đề, tác giả, năm xuất bản, nhà xuất bản, từ khóa | FAQ chọn trường tra cứu, phân biệt với tìm toàn bộ |
| 7–10 | Đăng nhập, mở trang cá nhân, chọn sách, bấm “Đăng ký mượn” | Đây là đặt chỗ/đặt mượn, không phải gia hạn |
| 11 | Kiểm tra ấn phẩm đặt mượn và đang mượn, kho, ngày và hạn liên quan | FAQ xem trạng thái sau thao tác; không suy mã kho thành vị trí hiện hành khi chưa xác nhận |
| 12–13 | Xem thông tin sách đang mượn cho sinh viên và cán bộ/giảng viên | Hướng dẫn tự xem tài khoản trên OPAC; chatbot không nhận thông tin đăng nhập |

PDF không có mục hoặc chuỗi bước gia hạn tài liệu. Trang 7 ghi thời gian đặt chỗ hai ngày rồi tự xóa; chưa có tài khoản để kiểm tra quy định này còn áp dụng hay không. Không dùng thời hạn đặt chỗ làm thời hạn mượn hoặc gia hạn.

Trang 8, 12–13 mô tả mật khẩu ban đầu theo số thẻ. Chỉ coi đây là hướng dẫn trong tài liệu cũ: chưa kiểm tra chính sách tài khoản hiện nay, không thử thông tin ví dụ, không tạo FAQ khẳng định mọi tài khoản hiện vẫn có mật khẩu như vậy. Hướng dẫn người dùng dùng thông tin được cấp hoặc liên hệ thư viện khi không đăng nhập được.

Ảnh trang 11 có ví dụ thông tin tài khoản/ấn phẩm và ngày lịch sử. Không chép dữ liệu ví dụ đó vào kho FAQ hoặc bộ đánh giá.

## 3. Những gì đã kiểm tra trên website hiện tại

### 3.1. Giao diện tra cứu công khai

Quan sát được bộ chọn: Toàn bộ; Tài liệu số (Toàn văn); Sách truyền thống; Luận án, luận văn; Báo tạp chí; Khóa luận. Menu có Nhan đề, Tác giả, Năm xuất bản, Nhà xuất bản, Từ khóa, Danh mục và Tài liệu mới.

Tìm nâng cao tại [OSearchAdvanced.aspx](https://opacthuvien.ut.edu.vn/opac/OSearchAdvanced.aspx) có:

- Ba dòng điều kiện, kết hợp AND/OR/NOT.
- Chứa, Chính xác, Bắt đầu bằng, Kết thúc bằng.
- Trường tìm: Mọi trường, Nhan đề, Tác giả, Năm xuất bản, Nhà xuất bản, Từ khóa, Dạng tài liệu, Khổ.
- “Thêm giới hạn”: năm gần đây, từ năm/đến năm, sắp xếp và loại tài liệu.

Đã mở giao diện và phần giới hạn. Lượt thử gửi truy vấn nâng cao gặp timeout điều khiển trình duyệt, chưa xác nhận truy vấn thực thi hoặc kết quả; không ghi là kiểm thử thành công.

### 3.2. Tìm kiếm và chi tiết bản ghi

| Thao tác | Quan sát thực tế | Giới hạn kết luận |
| --- | --- | --- |
| Chọn Sách truyền thống, tìm “Lý thuyết tàu” qua kính lúp | Chuyển tới `Oshow.aspx?rdSearchOption=1&txtSearch=...`, hiển thị không có kết quả | Không còn khớp ví dụ 23 kết quả trong PDF; chưa xác định nguyên nhân, không kết luận thư viện không có sách chủ đề này |
| Tìm “tàu” ở Toàn bộ | Tới `Oshow.aspx?rdSearchOption=0&txtSearch=...`; trang hiển thị mục 1–20 của 4.365 kết quả | Số quan sát ngày 28/10, có thể thay đổi; kết quả khớp cả từ khóa chủ đề, không chỉ nhan đề |
| Mở nhan đề đầu tiên từ danh sách | Hộp chi tiết tải bản ghi `intItemId=1967`, có thông tin biên mục và xếp giá | Hộp chi tiết tải chậm; snapshot ngay sau click có lúc chưa chứa nội dung |
| Mở URL chi tiết đã quan sát ở tab khác | Đọc được bản ghi công khai mà không đăng nhập | Xác nhận liên kết chi tiết dùng được ở tab khác trong phiên này; chưa kiểm tra phiên trình duyệt độc lập |

Bản ghi minh họa: [10 năm Olympic cơ học toàn quốc 1989–1998](https://opacthuvien.ut.edu.vn/opac/ODetail.aspx?intItemId=1967&searchWord=T%C3%80U). Đọc được tác giả, DDC, thông tin xuất bản, mô tả vật lý, tóm tắt, từ khóa, dạng tài liệu và ngôn ngữ. Có các chế độ Đầy đủ/ISBD/MARC trên giao diện, chưa đối chiếu nội dung từng chế độ.

Phần xếp giá tại thời điểm xem ghi 2/2 bản rỗi, 0 được giữ chỗ; hiển thị ký hiệu đăng ký cá biệt và nút “Đăng ký mượn”. Đây là trạng thái tại thời điểm quan sát, không phải giá trị để cố định trong FAQ. Không bấm nút đặt mượn và chưa xác nhận quyền, điều kiện hoặc kết quả giao dịch.

URL trang kết quả và chi tiết là địa chỉ giao diện ASP.NET đã quan sát, không phải bằng chứng có REST API công khai hoặc hợp đồng tích hợp ổn định. Không tự suy ra endpoint giao dịch từ tên trang.

## 4. Tác động tới bản đầu FAQ + tìm từ khóa

Có đủ căn cứ để biên soạn nhóm FAQ OPAC cụ thể, dẫn PDF theo trang và dẫn trang OPAC hiện hành:

1. Vào OPAC ở đâu, có cần đăng nhập để tra cứu công khai không?
2. Tìm theo từ khóa và chọn sách truyền thống/tài liệu số thế nào?
3. Tìm theo nhan đề, tác giả, năm xuất bản hoặc nhà xuất bản thế nào?
4. Khi nào nên dùng tìm nâng cao và ý nghĩa AND/OR/NOT?
5. Không có kết quả thì thử từ khóa ngắn hơn/đổi trường hoặc loại tài liệu như thế nào, mà không khẳng định sách không tồn tại?
6. Xem tác giả, năm xuất bản, phân loại, ký hiệu và số bản rỗi ở đâu?
7. Tại sao có bản ghi tài liệu số không đồng nghĩa được tải toàn văn?
8. Đặt chỗ mượn khác gia hạn thế nào; xem ấn phẩm đã đặt/đang mượn ở đâu?
9. Quên thông tin đăng nhập hoặc cần xác nhận thời hạn đặt chỗ thì liên hệ ai?
10. Chatbot có tự đặt mượn/gia hạn được không?

Trả lời FAQ tra cứu khác với trả kết quả danh mục bên trong chatbot. Hướng dẫn thao tác đã có bằng chứng; tra cứu danh mục tự động vẫn cần thiết kế và kiểm thử riêng.

### Khả năng tích hợp theo mức độ

| Mức | Khả năng | Trạng thái |
| --- | --- | --- |
| 1 | FAQ hướng dẫn OPAC, dẫn PDF đúng trang và dẫn website | Đủ căn cứ cho các thao tác công khai đã đối chiếu; bước đăng nhập/đặt mượn vẫn phải ghi nguồn và giới hạn xác minh |
| 2 | Nút mở OPAC tìm theo từ khóa được mã hóa an toàn | Có URL kết quả từ giao diện thực tế; có thể đề xuất bổ sung, cần kiểm tra từ khóa có dấu/không dấu, ký tự đặc biệt, bộ lọc và phiên mới trước khi cam kết |
| 3 | Backend lấy, phân tích và hiển thị danh mục/trạng thái bản sách | Chưa có API được cấp; chưa đo tính ổn định, quyền sử dụng, tải và phân trang. Không tự triển khai crawler trong bản đầu |
| 4 | Tự đặt mượn hoặc gia hạn | Chưa có xác thực/tài khoản thử/API được cấp. PDF không đủ làm đặc tả gia hạn |

Khuyến nghị giữ mức 1 trong bản đầu đã chọn; mức 2 là cải tiến nhỏ có thể chốt riêng sau thử liên kết. Không cần chờ quyền API để hoàn thiện FAQ OPAC. Không dùng thành công đọc trang công khai để tuyên bố đã tích hợp hệ thống thư viện.

## 5. Các ca cần bổ sung vào kiểm thử và đánh giá

- “Hướng dẫn tra cứu OPAC” → có các bước và nguồn đúng trang 3–6.
- “Tìm sách của tác giả ...” → phân biệt hướng dẫn chọn Tác giả với câu trả kết quả thật.
- “Không tìm được Lý thuyết tàu” → hướng dẫn đổi truy vấn/trường/loại; không lặp con số 23 trong PDF như dữ liệu hiện tại.
- “Sách này còn không?” → không lấy số bản rỗi của bản ghi minh họa làm đáp án cho tài liệu khác hoặc thời điểm khác.
- “Đăng ký mượn có phải gia hạn không?” → phân biệt rõ; không tuyên bố đã gửi giao dịch.
- “Đặt chỗ được giữ bao lâu?” → dẫn trang 7 và nói rõ chưa xác nhận quy định hai ngày còn hiệu lực.
- “Mật khẩu OPAC là gì?” → dùng thông tin được cấp/liên hệ thư viện; không thử hoặc khẳng định mẫu mật khẩu cũ áp dụng cho mọi tài khoản.
- “Tài liệu số có tải được không?” → quyền tải phụ thuộc quyền truy cập, không suy từ màu hoặc nhãn loại tài liệu.

Chưa đăng nhập, xem dữ liệu cá nhân, kiểm tra mượn/gia hạn, tải toàn văn, xác nhận API hoặc thu thập toàn bộ danh mục. Không sửa mã ứng dụng trong lượt nghiên cứu này.
