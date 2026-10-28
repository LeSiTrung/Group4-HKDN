# Thiết kế bản đầu: FAQ và tìm kiếm từ khóa D7

Ngày: 28/10/2026. Cập nhật phạm vi: bản đầu và điều kiện đưa cho người dùng thật. Trạng thái: chờ người dùng duyệt trước khi lập kế hoạch triển khai.

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

## 11. Bổ sung nguồn OPAC sau khảo sát

Người dùng cung cấp `D:/Download/HDSD_TRACUU_OPAC.v1.1.pdf` và yêu cầu tìm hiểu thêm OPAC. Kết quả đối chiếu tài liệu 13 trang và website hiện hành nằm trong `docs/khao-sat-opac-2026-10-28.md`.

- Bổ sung FAQ có dẫn trang về tìm toàn bộ, lọc loại, tìm theo trường, đọc chi tiết/xếp giá, xem ấn phẩm đặt/đang mượn. Tìm nâng cao có giao diện AND/OR/NOT được quan sát trực tiếp; chưa xác nhận lượt thử truy vấn nâng cao thành công.
- PDF hướng dẫn đặt chỗ và kiểm tra sách mượn, không có quy trình gia hạn. Không dùng nút “Đăng ký mượn” để thay cho gia hạn hoặc suy ra thao tác gia hạn.
- Thời hạn đặt chỗ hai ngày và mô tả mật khẩu ban đầu trong PDF chưa được xác nhận hiện hành; không biến thành lời khẳng định trong FAQ. Không chép dữ liệu tài khoản ví dụ từ ảnh.
- Đã thử tìm kiếm công khai và mở bản ghi chi tiết; dữ liệu bản rỗi chỉ là trạng thái tại lúc xem. Không cố định con số kết quả/bản rỗi vào câu trả lời FAQ.
- Có URL kết quả và chi tiết được sinh từ giao diện thực tế. Liên kết mở truy vấn là phương án có thể bổ sung sau kiểm chứng, chưa tự mở rộng phạm vi thành backend tự lấy danh mục hoặc API giao dịch.

Phạm vi bản đầu vẫn là FAQ + tìm từ khóa trên bộ nguồn đã rà soát; trạng thái thiết kế vẫn chờ duyệt.

## 12. Yêu cầu bổ sung: sản phẩm đồ án phục vụ người dùng thật

Người dùng yêu cầu làm đầy đủ, chi tiết, có thể hoạt động với người dùng thật và xác nhận nhóm sẽ tự chuẩn bị toàn bộ hạ tầng. Các tiêu chí bên dưới mở rộng phần bàn giao/vận hành; không biến các nghiệp vụ chưa có API thành tính năng giả hoặc tự thêm giao dịch ngoài phạm vi đã thống nhất.

FAQ + tìm từ khóa là mốc triển khai đầu tiên, không được lấy việc chạy được bản đầu để tuyên bố toàn bộ đồ án hoặc quá trình triển khai thực tế đã hoàn thành. Tên học phần trong repo hiện là HKDN; người dùng gọi đây là đồ án tốt nghiệp. Chưa tự đổi tên báo cáo hoặc mẫu trường khi chưa xác nhận, việc này không cản phát triển sản phẩm.

### 12.1. Bốn nghiệp vụ phải có luồng sử dụng hoàn chỉnh

| Nghiệp vụ | Bản đầu có thể thực hiện với đầu vào hiện có | Điều kiện để mở rộng |
| --- | --- | --- |
| Tra cứu | Hướng dẫn theo loại/trường, giải thích kết quả, dẫn OPAC/PDF đúng mục; kiểm thử liên kết mở truy vấn trước khi bổ sung nút tìm theo từ khóa | Trả danh mục bên trong chatbot chỉ khi có nguồn/API hoặc cơ chế đọc được phép, kiểm thử cập nhật và xử lý lỗi |
| Giờ phục vụ | Phân biệt cơ sở, hỏi rõ khi thiếu thông tin; nếu chưa có lịch hiện hành thì nêu giới hạn và dẫn kênh xác nhận | Lịch hiện hành, ngày hiệu lực và ngoại lệ nghỉ/lễ được thư viện xác nhận trước khi trả lời thời gian cụ thể |
| Gia hạn | Giải thích khác biệt giữa đặt chỗ và gia hạn; hướng dẫn các bước có nguồn, chuyển tới thư viện khi chưa đủ quy trình | Cơ chế được cấp phép, xác thực, môi trường/tài khoản thử và kiểm thử kết quả, gửi trùng, timeout trước giao dịch thật |
| CSDL điện tử | Hướng dẫn chọn nguồn, thao tác tra cứu và điều kiện truy cập có căn cứ; dẫn trang chính thức | Xác nhận chính sách tài khoản/quyền truy cập hiện hành trước khi khẳng định có thể đọc hoặc tải toàn văn |

Một luồng thiếu đầu vào phải có câu trả lời hữu ích và chỉ rõ bước tiếp theo. Không dùng “chưa cấu hình” hoặc câu trả lời mẫu làm kết quả cho bạn đọc.

### 12.2. Đóng gói để nhóm tự triển khai

Đề xuất kỹ thuật của người viết: giữ React + FastAPI, đóng gói ứng dụng bằng Docker; build frontend thành tệp tĩnh và phục vụ cùng origin với API. Dùng reverse proxy hỗ trợ HTTPS trước ứng dụng. Không bắt buộc thêm CSDL khi chưa có nhu cầu lưu dữ liệu giao dịch; FAQ và mã cấu hình triển khai được quản lý theo phiên bản.

- Phát triển tại Windows như hiện tại; gói bàn giao chạy trên một máy chủ Linux do nhóm chọn sau. Không mua máy chủ/tên miền hoặc mở dịch vụ công khai trong bước thiết kế/phát triển.
- Bản phát hành có lệnh build/chạy/dừng, cấu hình mẫu, kiểm tra sức khỏe, phiên bản ứng dụng và phiên bản dữ liệu. Không lệ thuộc đường dẫn trên máy cá nhân.
- Cấu hình production theo domain thực tế; chỉ mở HTTP(S) qua proxy, API không có cổng công khai riêng. Chuyển hướng HTTPS, giới hạn kích thước request, số yêu cầu và thời gian chờ ở một nơi phù hợp để tránh hai lớp cấu hình lệch nhau.
- Chạy ứng dụng bằng tài khoản không có quyền root khi khả thi với image đã chọn. Không đưa bí mật vào Git hoặc frontend; chỉ cần bí mật khi thực sự tích hợp dịch vụ tương ứng.
- Tự khởi động lại khi tiến trình lỗi, có health check và cách xem log. Log vận hành không chứa nội dung chat, mật khẩu hoặc toàn bộ request body.
- Sao lưu dữ liệu FAQ/cấu hình cần thiết và thử khôi phục; giữ được bản phát hành trước để quay lại khi cập nhật lỗi. Có phương án lưu trữ an toàn riêng cho bí mật nếu sau này phát sinh.
- Chỉ coi phần triển khai thực tế hoàn thành sau khi kiểm tra bằng domain HTTPS thật từ mạng ngoài máy chủ; build container hoặc localhost không thay cho bằng chứng này.

Docker/reverse proxy là cách đóng gói đề xuất, không phải lựa chọn hạ tầng người dùng đã chỉ định. Công cụ proxy, image/version, chi phí và cấu hình máy cụ thể được chốt theo môi trường thực tế; chưa cần chọn dịch vụ trả phí để viết bản đầu.

### 12.3. Cập nhật dữ liệu và trách nhiệm vận hành

- Nhóm chỉ định người phụ trách cập nhật nguồn trước khi mời người dùng thử. Quy trình bản đầu: sửa JSON → kiểm tra dữ liệu và bộ ca liên quan → xem thay đổi nguồn/đáp án → phát hành phiên bản mới; không cần trang quản trị chỉ để thay tệp.
- Mỗi FAQ có nguồn và ngày rà soát; lịch/phí/thời hạn chưa được xác nhận phải giữ trạng thái cần xác nhận. Nguồn bị thay thế được ngừng dùng, không xóa dấu vết phiên bản cũ.
- Hướng dẫn cán bộ/nhóm nhận biết link hỏng, nguồn xung đột và cách rút FAQ sai khỏi phiên bản đang dùng. Khi không có người duy trì phải nêu rõ giới hạn cập nhật cho người dùng.
- Hội thoại chỉ ở bộ nhớ trang của người dùng như mục 7; không thêm tài khoản hoặc lưu lịch sử chỉ để tạo cảm giác đầy đủ. Kiểm tra thực tế cấu hình proxy/app để bảo đảm không ghi nội dung chat.

### 12.4. Chất lượng và bằng chứng nghiệm thu

Ngoài kiểm tra bản đầu ở mục 9, cần đủ các nhóm bằng chứng sau cho mốc dùng thật:

1. **Nghiệp vụ và nguồn:** đủ bốn nhóm câu hỏi với đáp án hoặc hành vi chuyển tiếp đúng; tất cả câu trả lời nghiệp vụ có căn cứ hỗ trợ, không chỉ link tồn tại. Các ca bịa gia hạn, khẳng định phí/lịch chưa xác minh hoặc sai quyền truy cập là lỗi chặn phát hành.
2. **Đánh giá độc lập:** dùng tập phát triển riêng với tập chấm cuối theo kế hoạch D7; ghi câu hỏi, đáp án mong đợi, nguồn/phiên bản, kết quả và lỗi. Ngưỡng trong kế hoạch là đề xuất; cần xác nhận với người đánh giá trước nghiệm thu. Không tự báo đạt khi chưa chạy/chấm.
3. **Độ ổn định:** kiểm tra tải, timeout và lỗi trên cấu hình máy được ghi rõ. Mốc kỹ thuật tạm để kiểm tra bản FAQ: 5 phiên đồng thời, ít nhất 100 request có trộn câu hợp lệ/không tìm thấy; đo p50/p95, lỗi bất thường và mức dùng tài nguyên. Đề xuất p95 API không quá 2 giây trên môi trường bàn giao cho xử lý FAQ không gọi web/LLM; đây là mục tiêu cần đo, chưa phải cam kết đã đạt.
4. **Trình duyệt và khả năng tiếp cận:** luồng chính trên Chrome/Edge máy tính và điện thoại hoặc thiết bị thật có thể bố trí; kiểm tra bàn phím, focus, đọc trạng thái, tương phản, màn hình nhỏ, mạng chậm và mất backend. Giả lập kích thước màn hình không thay cho kiểm tra thiết bị thật.
5. **Triển khai:** dựng lại từ bản checkout/gói bàn giao sạch, kiểm tra domain/HTTPS, khởi động lại máy/tiến trình, cập nhật và quay về phiên bản trước, khôi phục dữ liệu. Không để hệ thống chỉ chạy được trên máy người phát triển.
6. **Thử với người dùng thật:** chuẩn bị kịch bản hỏi đáp cho sinh viên và người kiểm tra nghiệp vụ; nhóm mời và lấy phản hồi qua kênh được phép. Ghi số người tham gia, tác vụ hoàn thành, lỗi, phản hồi và cách sửa; không tạo người dùng/nhận xét hoặc kết quả khảo sát giả. Mức thử và người chấm được thống nhất với Mentor; chưa có thử nghiệm thì để hạng mục này chưa hoàn thành.
7. **Hồ sơ:** hướng dẫn bạn đọc, hướng dẫn cập nhật/vận hành, sơ đồ hệ thống, đặc tả API/dữ liệu, bảng đánh giá, hạn chế, báo cáo/slide và kịch bản demo dựa trên phiên bản đã kiểm tra. Hình minh họa, số đo và kết luận phải khớp sản phẩm thật.

### 12.5. Thứ tự thực hiện và điều kiện chuyển mốc

- **Mốc A — nền tảng chạy được:** nguồn FAQ đã rà soát, tìm kiếm và UI/API hoàn chỉnh, test và build qua. Dừng gọi đây là bản khung trả lời mẫu.
- **Mốc B — sẵn sàng triển khai:** gói phát hành tái lập, kiểm tra bảo mật cơ bản/độ ổn định, cập nhật nguồn và khôi phục chạy được. Vẫn chưa tuyên bố đã có người dùng thật.
- **Mốc C — thử nghiệm thực tế:** nhóm chuẩn bị máy chủ/domain, triển khai HTTPS, thử từ mạng ngoài, mời người dùng và người kiểm tra nghiệp vụ, sửa lỗi từ phản hồi.
- **Mốc D — bàn giao đồ án:** bộ đánh giá và hồ sơ phản ánh đúng những mốc đã đạt; công bố rõ phần phụ thuộc chưa được cấp. Nếu tích hợp RAG/LLM hoặc API thư viện sau này thì bổ sung thiết kế, điều kiện dữ liệu và kiểm thử tương ứng trước khi đưa vào bản đang phục vụ.

Những phần có thể làm và kiểm chứng tại máy phát triển phải được hoàn thành trước khi yêu cầu cấp hạ tầng hoặc xin duyệt thao tác triển khai. Thiếu domain/API chỉ chặn các mốc cần chúng, không chặn hoàn thiện nền tảng.
