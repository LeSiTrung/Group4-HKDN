# Kiểm thử biên và hồi quy

Phạm vi03/11/2026: tiếp tục cải thiện sản phẩm, kiểm tra nhiều nhóm tình huống có thể tái lập. Không khẳng định bao phủ mọi câu hỏi, mọi thiết bị hay mọi tổ hợp concurrency. Bộ benchmark/frozen training test không được sửa để làm đẹp chỉ số.

| Nhóm | Lỗi tái hiện và thay đổi | Cách kiểm chứng |
|---|---|---|
| Tìm tài liệu | Mất từ trong nhan đề như Quyền con người, Bạn đọc, Người Việt; không nhận02/100cuốn; ghépJava vàoPython |42ca catalog bổ sung; SQLite tạm và hồi quy tìm tác giả/chủ đề/typo/level |
| Hướng dẫn mượn | Câu hỏi OPAC nhận hướng dẫn tại quầy hoặc không thấy nguồn |Tách category hướng dẫn tại quầy và hướng dẫn đăng kýOPAC;19+ca assistant và31live cases |
| Thiếu/loại trừ | Yêu cầu không có chủ đề trả not_found; điều kiện “đừng lấy/không cần/bỏ qua” bị bỏ |Hỏi làm rõ, giữ tiêu chí chưa hỗ trợ; không trả sách như thể đã thỏa |
| Phí/chính sách | Khởi tạo vector trước khi kiểm tra thiếu căn cứ, gây chờ không cần thiết |Kiểm tra sensitive trước vector; livephí21.67ms sau sửa,23.88s ở lượt lạnh trước sửa. Đo đơn lẻ, không phải SLA |
| Biên API | ID lớn hơn signed64 gây lỗiSQLite; escapedUnicode lỗi làm validationresponsecrash; dữ liệu riêng có thể bị phản chiếu |Giới hạn ID ở11bề mặtSQL; handler422 chỉtype/loc/msg, khônginput/ctx/body;19live contract probes |
| Tài khoản | Cookie hỏng bị coi là khách, sai kỳ vọng lưu lịch sử |Có cookie không hợp lệ trả401và xóa cookie; khôngcookie vẫn là khách; đăng nhập lại giữ lịch sử |
| Phân quyền | Chủ sở hữu, export/delete/feedback, tài khoản đổi trạng thái trong lúc xử lý |66ca bảo mật bổ sung; kiểm tra SQLite tạm và syntheticaccounts trong Linuxcontainer |
| UI bất đồng bộ | Gửi lại nhân đôi lịch sử, kết quả cũ chen vào cuộc chat/người dùng mới, tìm kiếm/phân trang lệchtruyvấn |Chat/conversation/sessiongeneration, input giữ khi lỗi,36ca Reactfailureflow; diagnostics chỉadmin |
| Thao tác tài khoản | Xuất riêng tư tải xuống sauđổingười, callbackpassword/delete/login cũ thay phiên mới |Chặn continuation cũ khi unmount/đổiuser; resetform/passwordvàtrạngtháitheotàikhoản |
| MạngOPAC | Một ReadTimeout/ConnectError dừng cảMARC |ChỉGETlỗitransport retry tối đa3lượt, backoff30/60s và sharedclock; khôngretryHTTP401/403/429/5xx, POST/giaodịch, DNS/URL/phảnhồiquáhạn |

Các tests dùng dữ liệu giả hoặc tạm và không gọi provider có phí. Live matrix dùng Qwen/Ollama đã có, nguồn/catalognội bộ và APIloopback. Unit/integration tests không chứng minh hiệu lực chính sách, độ sẵn sàng giao dịch thư viện hay chất lượng được cán bộ duyệt.

## Kết quả hiện tại

- 783 kiểm thử backend, không fail/error/skip; 101 kiểm thử frontend và Vite build đạt. Image Linux `uth-library:2026-11-03-edge` được build và thử riêng với UID 10001.
- 31/31 tình huống hội thoại thật; 19/19 phép kiểm tra API gồm JSON, Unicode, ID, origin, dung lượng và phiên. Container Linux kiểm tra cookie hết hạn thật, đăng nhập lại và quyền xem lịch sử; tài khoản và lịch sử giả được xóa sau thử.
- 16 yêu cầu chào/FAQ với 4 luồng thành công. Burst riêng trả 200/429, không 500. Đây không phải benchmark LLM, sức tải duy trì, trình duyệt thật hoặc nghiệm thu production.
- MARC vẫn chạy tiếp từ inventory cố định 22.401 ID. Retry đã phục hồi một số lỗi GET tạm thời; số tệp đã lưu phải được kiểm tra hash/schema, khác counter phần đầu đã xử lý của lượt hiện tại. Chi tiết nằm trong bằng chứng JSON.

Lệnh lặp lại nằm trong [tests/README.md](../tests/README.md); số liệu/hash/thời điểm và phạm vi: [validation/2026-11-03-edge-cases.json](validation/2026-11-03-edge-cases.json).

## Giới hạn còn lại

Browser automation đang bị tắt trong Work settings nên kiểm tra React component/API/build không thay cho nghiệm thu trên trình duyệt và thiết bị thật. Các yêu cầu xác thực chồng nhau giữa nhiều tab có thể tạo thứ tự `Set-Cookie` ngoài quyền kiểm soát của JavaScript; chưa tuyên bố đã giải quyết giao thức này. Qdrant local khi tải lạnh vẫn có thể mất hàng chục giây. Bộ lọc semantic thận trọng có thể bỏ sót từ đồng nghĩa không có bằng chứng lexical/fuzzy. Cần nhãn độc lập từ bạn đọc/thủ thư và kiểm tra máy đích, domain, HTTPS, sức tải, restore trước khi công khai.
