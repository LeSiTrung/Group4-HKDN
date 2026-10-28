# Thiết kế bản đầu: FAQ và tìm kiếm từ khóa D7

Ngày: 28/10/2026. Trạng thái: chờ người dùng duyệt trước khi lập kế hoạch triển khai.

## 1. Mục đích và căn cứ

Biến bộ khung React + FastAPI hiện có thành chatbot hướng dẫn dịch vụ Thư viện UTH chạy được tại máy phát triển, có câu trả lời từ FAQ biên soạn theo nguồn công khai, dẫn nguồn và giới hạn rõ ràng. Đây là mốc tìm kiếm từ khóa để so sánh với RAG/LLM về sau.

Người dùng đã chọn FAQ + tìm kiếm từ khóa và yêu cầu làm chỉn chu. Chưa được cấp dữ liệu hoặc API thư viện. Gia hạn thật được mong muốn khi có điều kiện tích hợp; bản đầu hướng dẫn quy trình trong phạm vi nguồn xác minh được.

Hiện `POST /api/chat` trả lời mẫu, frontend chỉ đọc `answer`; các service RAG/LLM/CSDL chưa hoạt động. Xem thêm `docs/khao-sat-hien-trang-2026-10-28.md`.

## 2. Các phương án đã cân nhắc

| Phương án | Đánh đổi | Kết luận |
| --- | --- | --- |
| FAQ biên soạn + tìm từ khóa, không gọi AI | Dễ kiểm chứng, không cần khóa API; hạn chế với câu hỏi diễn đạt rất khác hoặc nhiều ý | Người dùng chọn ngày 28/10/2026 |
| RAG/LLM ngay | Diễn đạt linh hoạt hơn; phải chọn model/dịch vụ, chi phí và đo đồng thời chất lượng nguồn lẫn sinh câu trả lời | Để giai đoạn tiếp theo |

Không dựng lại frontend/backend hoặc thêm framework điều phối. Cách lưu JSON, quy tắc tìm kiếm và định dạng API bên dưới là đề xuất kỹ thuật của người viết, chưa phải lựa chọn riêng do người dùng nêu.

## 3. Mục tiêu và ngoài phạm vi

### Mục tiêu

- Hỏi bằng tiếng Việt có dấu/không dấu; nhận câu trả lời FAQ có căn cứ hoặc lời đề nghị làm rõ.
- Bốn nhóm nội dung: tra cứu tài liệu; giờ phục vụ; gia hạn/mượn trả; hướng dẫn tài nguyên điện tử.
- Có đường dẫn nguồn và ngày kiểm tra, phân biệt nguồn công khai đã đọc với nội dung đã được thư viện xác nhận.
- FAQ phục vụ hướng dẫn: tra cứu sách dẫn tới OPAC/thư viện số; không trả danh mục sách bịa hoặc tình trạng còn sách.
- Giao diện chat dùng được trên máy tính/điện thoại, bằng bàn phím; có gợi ý ban đầu, trạng thái gửi, lỗi dễ hiểu, xem nguồn và bắt đầu lại hội thoại.
- Có bộ kiểm thử API/tìm kiếm, bộ câu hỏi đánh giá riêng và hướng dẫn vận hành/cập nhật FAQ.

### Ngoài phạm vi bản đầu

- LLM, embedding, vector database; đăng nhập, lưu lịch sử phía máy chủ, quản trị dữ liệu qua web; crawler tự động.
- Tự truy vấn danh mục trực tiếp, gia hạn giao dịch thật, Zalo/Messenger, giọng nói.
- Cam kết giờ mở cửa hôm nay, phí hoặc thời hạn hiện hành khi chưa có căn cứ đủ tin cậy.

Các giới hạn này không loại bỏ hướng tích hợp thật sau khi thư viện cấp điều kiện cần thiết. Không tạo nút gia hạn giả hoặc thông báo hoàn tất giao dịch.

## 4. Nguồn dữ liệu và cách biên soạn

Dùng một bộ JSON nhỏ trong `data/faq/`, được quản lý cùng mã nguồn; không cần CSDL. Nạp và kiểm tra dữ liệu lúc khởi động, không gọi web theo từng câu hỏi. Cập nhật bằng sửa tệp, chạy kiểm tra và khởi động lại backend.

Mỗi FAQ có: `id`, `category`, `question`, `aliases`, `keywords`, `answer`, `status`, `sources`. Mỗi nguồn có tên, URL HTTPS, mục liên quan khi có, ngày đọc và cách đọc. Có thể lặp metadata trong FAQ để không cần thêm lớp quản lý nguồn ở bản nhỏ này. `status` là `reviewed_public` hoặc `needs_confirmation`; ngày đọc không phải ngày văn bản có hiệu lực hoặc ngày Mentor duyệt.

Chỉ nhận liên kết đã rà soát thuộc website thư viện hoặc dịch vụ được LIC dẫn tới. Kiểm tra URL HTTP(S) an toàn ở ranh giới dữ liệu; không cho `javascript:`/HTML đi vào liên kết. Tên nguồn và câu trả lời là văn bản, React tự escape; không dùng HTML thô.

Biên soạn khoảng 15–25 FAQ độc lập nếu nguồn đủ; không thêm câu gần trùng chỉ để đạt số lượng. Nhóm thông tin chưa chắc chắn được biên soạn thành câu trả lời thận trọng, không đưa quy định chưa xác minh vào lời khẳng định. Không sao chép toàn văn sách hoặc thu thập tài khoản/người mượn.

### Bằng chứng đọc trực tiếp ngày 28/10/2026

Trình duyệt đọc được các trang bên dưới, dù công cụ đọc web có thể trả 403. Đây là bằng chứng nội dung trang công khai, không xác nhận hiệu lực nghiệp vụ:

- [Trang chủ LIC](https://lic.ut.edu.vn/): đầu mối dịch vụ, danh sách cơ sở và kênh hỗ trợ.
- [Quy định mượn trả](https://lic.ut.edu.vn/quy-dinh-muon-tra-tai-lieu/): mục 3 ghi không quá một học kỳ; mục 4.1 ghi 500đ/ngày/cuốn.
- [Nội quy](https://lic.ut.edu.vn/noi-quy-thu-vien/): điều 3 ghi 45 ngày; điều 7 ghi 1.000đ/cuốn/ngày; văn bản ghi 01/11/2022. Chưa xác định văn bản nào thay thế văn bản nào.
- [Hỗ trợ nhanh](https://lic.ut.edu.vn/dich-vu-thu-vien/ho-tro-nhanh/): có email `lic@ut.edu.vn`, liên kết `https://support.ut.edu.vn/`. Vị trí phòng và số điện thoại ở nội dung khác một số thông tin trang chủ; không tự hợp nhất.

Các nguồn OPAC, thư viện số và hướng dẫn CSDL sẽ được mở đọc trước khi biên soạn FAQ tương ứng. Nguồn chỉ đọc qua chỉ mục tìm kiếm được ghi nhận riêng, chưa đủ để khẳng định chính sách hiện hành.

### Hành vi bắt buộc với nghiệp vụ chưa rõ

- Hỏi giờ phục vụ: giải thích cần cơ sở và lịch hiện hành; chưa có lịch xác nhận thì dẫn trang thông báo/liên hệ, không lấy lịch cũ làm lịch hôm nay.
- Hỏi phí/thời hạn mượn: nêu có nguồn chính thức không thống nhất, dẫn hai trang và đề nghị xác nhận; không tính tiền phạt.
- Hỏi gia hạn: chỉ hướng dẫn các bước có trong nguồn đã đọc. Nếu chưa có quy trình, hướng dẫn liên hệ thư viện để xác nhận điều kiện/kênh thực hiện, nói rõ chưa thể gia hạn qua chatbot; không bịa nút thao tác hoặc số lần được gia hạn.
- Hỏi địa chỉ/phòng đang xung đột: nêu giới hạn và dẫn nguồn; không trộn thông tin thành địa chỉ mới.

## 5. Tìm kiếm và lựa chọn phản hồi

Tìm kiếm dùng Python chuẩn, không thêm thư viện NLP. Chuẩn hóa chữ thường, Unicode, bỏ dấu tiếng Việt, đổi `đ` thành `d`, bỏ dấu câu và gộp khoảng trắng. Chuẩn hóa cả câu hỏi lẫn các trường tìm kiếm.

- Ưu tiên trùng câu hỏi hoặc cách hỏi thay thế sau chuẩn hóa.
- Nếu không trùng, xếp hạng theo cụm từ/từ khóa đặc trưng và độ phủ các từ có nghĩa trong câu hỏi; từ chung như “thư viện”, “cho”, “hỏi” không được tự tạo một kết quả chắc chắn.
- Chỉ trả một đáp án khi có bằng chứng khớp đủ rõ; nếu các kết quả khác chủ đề gần nhau hoặc câu hỏi gồm nhiều ý thì đưa tối đa 3 câu hỏi gợi ý để người dùng chọn.
- Không khớp thì trả lời chưa tìm được thông tin và gợi ý các nhóm hỗ trợ. Không rút một câu trả lời ngẫu nhiên từ kết quả có điểm thấp.
- Với FAQ cần xác nhận, giữ nguyên cảnh báo và dẫn nguồn bất kể mức độ khớp.
- Bản đầu xử lý từng câu độc lập. Câu ngắn như “cơ sở 1” khi không đủ chủ đề cần được hỏi lại; chưa giả lập trí nhớ hội thoại.

Công thức điểm, danh sách từ phổ biến và ngưỡng cụ thể do người triển khai chọn ở mức đơn giản nhất, ghi lại trong tài liệu và kiểm tra bằng các ca âm tính/diễn đạt khác. Không hiển thị điểm như xác suất đúng. Không dùng bộ đánh giá cuối để chỉnh ngưỡng.

## 6. Hợp đồng API và lỗi

Giữ `POST /api/chat` và request `{ "message": "..." }`. Giữ `answer` để tương thích caller hiện tại; bổ sung:

- `status`: `answered`, `needs_confirmation`, `clarify`, `not_found`.
- `sources`: mảng nguồn đã chọn với `title`, `url`, `checked_at`.
- `suggestions`: mảng chuỗi câu hỏi gợi ý, tối đa 3.

Chỉ `answered`/`needs_confirmation` có nguồn căn cứ cho đáp án. `clarify`/`not_found` không gắn nguồn không hỗ trợ câu trả lời. Thông tin liên hệ chung nếu xuất hiện phải có nguồn hỗ trợ riêng, hoặc chỉ được nêu trong FAQ tương ứng.

Validation chạy ở backend: chỉ nhận chuỗi, tối đa 2.000 ký tự đầu vào; loại chuỗi rỗng/toàn khoảng trắng. Lỗi đầu vào trả 422. Dữ liệu FAQ sai schema/ID trùng/nguồn không hợp lệ phải báo rõ khi khởi động, không biến lỗi hệ thống thành “không tìm thấy”. Không ghi nội dung câu hỏi vào log ứng dụng hoặc lưu hội thoại.

`GET /health` tiếp tục cho biết API hoạt động; bổ sung trạng thái FAQ và số bản ghi hợp lệ nếu cần phân biệt với bản khung. Không báo LLM/CSDL sẵn sàng.

Chỉ mở CORS cho địa chỉ phát triển đã ghi trong README (`localhost:5173`, `127.0.0.1:5173`); không mở wildcard để né cấu hình. Chuẩn hóa lỗi mạng/validation phía frontend thành lời hướng dẫn cho người dùng, không chỉ hiện URL kỹ thuật.

## 7. Giao diện và quyền riêng tư

Giữ bố cục chat và phong cách hiện tại; không thay thương hiệu hoặc tạo trang quản trị. Dùng các component chat hiện có nếu việc tách thực sự giúp hiển thị tin nhắn/nguồn/gợi ý rõ hơn; không tách chỉ để lấp placeholder.

Hiển thị rõ đây là trợ lý FAQ, câu trả lời theo bộ nguồn đã rà soát. Mỗi phản hồi có nguồn mở trong tab mới an toàn, ngày kiểm tra và cảnh báo khi cần xác nhận. Các câu hỏi gợi ý là nút có tên rõ; có thể gửi bằng bàn phím. Trạng thái gửi/lỗi được thông báo cho trình đọc màn hình; chỉ cho một yêu cầu gửi tại một thời điểm.

“Bắt đầu lại” chỉ xóa tin nhắn khỏi trạng thái trang. Khóa thao tác này khi đang gửi để tránh phản hồi cũ xuất hiện trong hội thoại mới. Tải lại trang cũng xóa hội thoại; không dùng localStorage hoặc cookie để giữ nội dung chat. Giữ cuộn tin nhắn và ô nhập dùng được trên màn hình hẹp; không che nội dung bằng footer hoặc bàn phím.

## 8. Phạm vi tệp và trách nhiệm

- Dữ liệu, hướng dẫn cập nhật: `data/faq/`.
- Tìm kiếm: tận dụng `backend/app/services/rag_service.py` hoặc tên service phù hợp, cập nhật docstring để không gọi nhầm tìm từ khóa là RAG/LLM.
- Tích hợp: `backend/app/api/chat.py`, `backend/app/main.py`; không sửa service LLM/CSDL ngoài phần tài liệu cần thiết.
- Giao diện: `frontend/src/App.jsx`, `frontend/src/style.css`, `frontend/src/services/chatApi.js` và component chat được dùng.
- Kiểm thử: `tests/`, dependency phục vụ kiểm thử, tập câu hỏi thử/chỉnh và tập đánh giá riêng có nguồn/đáp án mong đợi.
- Tái lập: môi trường Python riêng; package lock frontend; phiên bản dependency đã chạy được; README và `docs/api-design.md`, `docs/requirements.md` theo hành vi thật.
- Chưa deploy hoặc push dữ liệu lên dịch vụ ngoài trong bước này.

## 9. Kiểm chứng và điều kiện hoàn thành bản đầu

1. Kiểm tra dữ liệu: schema, ID duy nhất, nguồn đầy đủ, URL an toàn, không có FAQ khẳng định quy định đang xung đột.
2. Kiểm thử tìm kiếm: có/không dấu, chữ hoa, dấu câu, cách hỏi khác, câu chỉ có từ chung, chủ đề gần nhau, nhiều ý, ngoài phạm vi. Các ca tương đương Unicode phải cho hành vi nhất quán.
3. Kiểm thử API: request đúng, rỗng, khoảng trắng, quá dài, sai kiểu, trạng thái phản hồi/nguồn, CORS hai địa chỉ phát triển; không có khóa hoặc HTML thực thi trong phản hồi.
4. Bộ đánh giá riêng tối thiểu 30 câu biên soạn độc lập với aliases: báo cáo đúng FAQ/hành vi, đúng nguồn, xử lý chưa rõ; có tử số/mẫu số và lỗi còn lại. Đây là kiểm tra nội bộ, chưa phải đánh giá có cán bộ thư viện xác nhận hoặc bảng nghiệm thu AI cuối kỳ.
5. `npm run build` thành công; thử trình duyệt trên desktop và màn hình hẹp: gửi câu hỏi, mở nguồn, chọn gợi ý, ngoài phạm vi, backend mất kết nối, bắt đầu lại, dùng bàn phím. Kiểm tra console và lỗi cuộn/layout.
6. Chạy lại từ hướng dẫn README trên môi trường riêng; API phản hồi dữ liệu thật của bộ FAQ, không còn câu trả lời mẫu. Lưu lệnh, cấu hình và kết quả kiểm tra.

Không gọi bản đầu hoàn chỉnh nếu không có kiểm tra luồng web → API → nguồn, hoặc nếu trả lời chắc chắn về quy định chưa xác minh. Không dùng tỷ lệ trung bình để bỏ qua bịa giao dịch gia hạn.

## 10. Quyết định giao cho người triển khai và giới hạn

Người triển khai quyết định số FAQ thực tế theo nguồn đủ căn cứ; công thức điểm/ngưỡng; cách tổ chức component; cấu hình kiểm thử và những chi tiết trình bày nhỏ. Không được tự mở rộng thành LLM, crawler, tài khoản hoặc giao dịch thật.

Giới hạn đã biết: từ khóa không hiểu ngữ nghĩa sâu; bản chụp FAQ cần cập nhật thủ công; rà soát website không thay thế xác nhận nghiệp vụ của thư viện. Khi bộ câu hỏi cho thấy truy xuất từ khóa không đủ, dùng kết quả bản đầu để quyết định bổ sung RAG sau.
