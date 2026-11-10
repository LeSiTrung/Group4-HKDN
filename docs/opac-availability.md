# Tra cứu số bản rỗi từ OPAC

Cập nhật03/11/2026: API/crawler hiện dùng chung clock bền vững `DATA_DIR/opac-pacing.sqlite3` trong helper mạng, thay giới hạn chỉ theo process ở phần lịch sử dưới đây. Khoảng cách tối thiểu10giây và robots có khoảng lớn hơn được giữ cho cả hai; API chờ tối đa20giây, không lấy được lượt thì trả unknown. WorkerMARC đã được tiếp tục từ inventory cố định qua `--details-from-pack`. Phải dùng cùng DATA_DIR/filesystem; không suy ra giới hạn chung cho hai máy/volume độc lập. Xem [local-release.md](local-release.md).

Chatbot đọc trực tiếp phần “Số bản tài liệu rỗi” của trang chi tiết công khai khi câu hỏi yêu cầu tình trạng mượn. Trạng thái này khác metadata danh mục đã thu thập trước đó. Không dùng LLM để đoán số lượng, không tạo giao dịch và không đăng nhập thay bạn đọc.

## Luồng đã triển khai

Câu “vậy thư viện hiện tại có những sách python nào có thể đăng kí mượn và có thể hướng dẫn tôi quá trình đăng kí mượn được khongi” được nhận thành yêu cầu tìm chủ đề Python, kiểm tra số bản rỗi và hướng dẫn đăng ký. Câu có thêm phí, thời hạn hoặc chủ đề độc lập vẫn yêu cầu tách ý; không âm thầm bỏ điều kiện.

Danh mục địa phương trả tối đa5biểu ghi. Mỗi lượt chỉ kiểm tra tối đa2ứng viên loại books có URL chi tiết OPAC chuẩn. Bộ đọc kiểm tra ID và loại “Sách truyền thống” trên trang nguồn trước khi lấy bộ đếm; tài liệu số hoặc trang thiếu dữ liệu trả unknown. Không phải mọi tài liệu kind=books đều là sách in, nên nhãn nguồn thực tế mới quyết định việc đọc bộ đếm. Câu trả lời ghi rõ các biểu ghi khác chưa kiểm tra; không khẳng định đây là toàn bộ sách có thể mượn.

`available>0` được diễn đạt “OPAC hiển thị N/M bản rỗi”, kèm thời điểm theo Asia/Ho_Chi_Minh. `available=0` được phân biệt với không đọc được nguồn; lỗi401/403/5xx, timeout, thiếu nhãn hoặc sai ID không trở thành số0. Thông tin rỗi không đảm bảo còn lúc đến, đủ điều kiện mượn hoặc đã đặt thành công. Mọi kiểm tra chỉ GETẩn danh; không thực hiện nút đăng ký hay gửi mật khẩu.

Hướng dẫn trong câu trả lời: mở biểu ghi gốc, xem Thông tin xếp giá và nút Đăng ký mượn; đăng nhập trực tiếp trên OPAC nếu nguồn yêu cầu rồi làm theo màn hình và kiểm tra kết quả. Nếu không có nút hoặc gửi không được, liên hệ thư viện. Không sử dụng tài khoản mẫu từ tài liệu hướng dẫn.

## Giới hạn và vận hành

Chỉ URL HTTPSchuẩn `https://opacthuvien.ut.edu.vn/opac/ODetail.aspx?intItemId=<ID>` được đọc; không querykhác/redirect. Giữ HTTPS/TLS, IPcông khai, DNS-pinning, User-Agentvà1MiBgiới hạn của helper. Cache60giây, tối đa128biểu ghi, lưu thời điểm đọc gốc; mỗi request mới cách ít nhất10giây trong một process. Trạng thái trong lịch sử là snapshot tại thời điểm trả lời, không tự cập nhật khi mở lại hội thoại.

Pacing/cache hiện theo process; không chạy nhiều webworker hoặc crawlerMARCđộc lập đồng thời nếu chưa có bộ điều phối chung theo host. Lượt MARCđược tạm dừng để ưu tiên kiểm tra theo yêu cầu này; các file/checkpoint được giữ nguyên. Trước khi tiếp tục bulk harvest, cần phối hợp với các lượt tra cứu trực tiếp; không bật lại hai worker và gọi đó là giới hạn10giây toàn hệ thống. Đây là giới hạn vận hành còn mở, không phải nghiệm thu tải nhiều người dùng.

## Bằng chứng thực tế03/11

Đã gửi nguyên câu trong ảnh tới APIcục bộ. Trả `answered`,5thẻ sách và snapshot ID26521: “Giáo trình lập trình python”1/1bản rỗi lúc09:03:30ICT ngày03/11/2026, kèm nguồn và hướng dẫn. Kết quả này chỉ đúng thời điểm nguồn được đọc, không phải số lượng cố định. File kiểm chứng `docs/validation/2026-11-03-opac-availability.json`; bản thử APIgốc ở ignoredtmp.

Tests parser/network kiểm tra số0/sốdương/unknown, saiID/loại, trường lặp/mâu thuẫn, URL/DNS/redirect/HTTPdenial, cachehết hạn vàgiới hạn128. Tests hội thoại bao phủ nguyên câu, không dấu, hướng dẫn, thiếu nguồn, bảo vệphí/thời hạn vànhiềuchủđề. Toàn bộ dùng dữ liệu giả/tạm, không giả mạo dữ liệu vận hành. UIrecheck bị chặn do Worksettings tắt browserautomation; frontendtests/build vàAPIthật được chạy.

Kiểm chứng cuối:558backendtests/48frontendtests đạt; productionbuild42modules đạt. Dữ liệu nguồn và response của nguyên câu được giữ trong bằng chứngJSON; không đánh giá khả năng mượn của tài khoản cụ thể.
