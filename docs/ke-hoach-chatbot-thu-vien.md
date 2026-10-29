# Kế hoạch Chatbot thư viện UTH

Ngày khảo sát: 27/10/2026. Trạng thái: đề xuất để trao đổi với Mentor, chưa triển khai code, chưa được đơn vị nghiệm thu.

## 1. Căn cứ và cách hiểu đề tài

Hai tài liệu do sinh viên cung cấp:

- **[T1] Đề tài tổng hợp LIC UTH**, `D:/Download/De tai tong hop LIC UTH.pdf`, 8 trang. Chatbot thư viện nằm ở trang PDF 7, số trang in 6. Mục 1.3 ở trang PDF 2 đề xuất nhóm 2-4 sinh viên, thời gian 12-15 tuần. Mục 5.2 ở trang PDF 8 yêu cầu mã nguồn, tài liệu kỹ thuật, hướng dẫn vận hành, báo cáo, demo; đề tài AI có thêm bảng đánh giá độ chính xác.
- **[T2] Hướng dẫn thực hiện HKDN**, `D:/Download/Huong dan thuc hien HKDN.pdf`, 6 trang. Trang 1-3 mô tả phân bổ và hướng dẫn; trang 4 quy định bảo mật, nội dung báo cáo tiến độ; trang 5-6 quy định đánh giá và báo cáo cuối kỳ 5 chương.

Yêu cầu trực tiếp của người dùng trong lần làm việc này: đọc tài liệu, tìm hiểu Chatbot thư viện, lập kế hoạch rõ ràng; **chưa viết code**. Các quy định trong PDF được dùng làm căn cứ lập kế hoạch học phần, không phải sự cho phép tự liên hệ Mentor, công bố dữ liệu, đăng ký tài khoản hay thao tác hệ thống trường.

Nội dung Chatbot thư viện trong T1: **“Hỗ trợ tra cứu, giờ mở cửa, gia hạn tài liệu, hướng dẫn sử dụng cơ sở dữ liệu điện tử”**. Cột công nghệ gợi ý LLM và tích hợp Zalo/Messenger/web. Đây là công nghệ gợi ý; tài liệu không nói phải triển khai đồng thời ba kênh và không ấn định nhà cung cấp AI.

Tên làm việc đề xuất: **Xây dựng chatbot hỗ trợ dịch vụ thư viện UTH dựa trên nguồn thông tin chính thức**.

Mục tiêu: người dùng hỏi bằng tiếng Việt, nhận câu trả lời đúng phạm vi, có dẫn nguồn, biết cách tìm tài liệu và sử dụng dịch vụ. Chatbot thư viện lấy hỗ trợ dịch vụ làm trọng tâm. Không chuyển phạm vi thành D1 (OPAC thông minh), D2 (gợi ý theo hồ sơ mượn), D4 (OCR) hoặc D5 (mượn trả tự phục vụ).

### Thông tin đã xác nhận và giả định để lập lịch

- Người dùng xác nhận nhóm có **4 thành viên**, lịch kết thúc **28/12/2026**.
- Lấy **27/10/2026** làm mốc lập kế hoạch phần việc còn lại đến hạn kết thúc: 9 khoảng làm việc, mỗi khoảng 7 ngày. Đây không phải xác nhận ngày bắt đầu HKDN chính thức; công việc đã làm trước mốc này cần được nhóm bổ sung vào nhật ký.
- Khung 12-15 tuần trong T1 là đề xuất chung của tài liệu. Lịch thực hiện còn lại bên dưới được điều chỉnh theo hạn người dùng cung cấp, cần thống nhất với Mentor.
- Thành viên: Lê Sĩ Trung (075205002473), Nguyễn Việt Dũng (070205005207), Hoàng Lê Ngọc Huy (075205014655), Hoàng Đặng Văn Kỳ (075205015362). Người hướng dẫn: TS. Đặng Nhân Cách.
- Chưa xác nhận phân công cá nhân, thời lượng làm việc mỗi tuần, ngân sách AI và máy triển khai.
- Bắt đầu từ kênh web; nhánh gia hạn thật và kênh bổ sung phải được chốt trong đặc tả với Mentor.
- Các chỉ tiêu chất lượng, số lượng dữ liệu và lịch báo cáo hàng tuần bên dưới là **đề xuất của kế hoạch**, không phải chỉ tiêu bắt buộc ghi trong PDF.

## 2. Khảo sát ban đầu và giới hạn bằng chứng

Nguồn công khai được tìm hiểu ngày 27/10/2026:

| Nguồn | Điều đã quan sát | Ý nghĩa với Chatbot thư viện |
| --- | --- | --- |
| [W1 - Trang chủ LIC](https://lic.ut.edu.vn/) | Có các liên kết tài nguyên và thông tin thư viện ba cơ sở | Cần phân biệt cơ sở khi trả lời địa điểm, giờ phục vụ |
| [W2 - Thông tin tài liệu có bản quyền](https://lic.ut.edu.vn/thong-tin-cac-tai-lieu-co-ban-quyen-da-duoc-xay-dung-va-trien-khai-tren-cac-he-thong-cua-nha-truong/) | Giới thiệu OPAC, Ebook UT-XD, ProQuest, STINET và các hướng dẫn | Có hệ sinh thái để chatbot hướng dẫn; chưa chứng minh API được cấp cho nhóm |
| [W3 - Quy định mượn trả](https://lic.ut.edu.vn/quy-dinh-muon-tra-tai-lieu/) | Trang ghi thời gian mượn không quá một học kỳ và phí quá hạn 500 đồng/ngày/cuốn | Chỉ là nội dung nguồn đã tìm thấy, chưa xác nhận hiệu lực |
| [W4 - Nội quy thư viện](https://lic.ut.edu.vn/noi-quy-thu-vien/) | Trang ghi 45 ngày và phí quá hạn 1.000 đồng/cuốn/ngày; văn bản có ngày 01/11/2022 | Xung đột W3; cần cán bộ thư viện xác nhận văn bản áp dụng |
| [W5 - Thông báo phục vụ ngoài giờ](https://lic.ut.edu.vn/thong-bao-ve-viec-mo-cua-phuc-vu-ban-doc-ngoai-gio/) | Thông báo ngày 29/06/2022 về phục vụ ngoài giờ | Không dùng làm lịch hiện hành năm 2026 khi chưa xác nhận |
| [W6 - Hướng dẫn sử dụng thư viện và CSDL](https://lic.ut.edu.vn/wp-content/uploads/2022/10/1.-HD-su-dung-thu-vien-va-khai-thac-hieu-qua-cac-CSDL-tai-nguyen-thong-tin-thu-vien.pdf) | Kết quả tìm kiếm hiển thị lịch phục vụ riêng từng cơ sở | Cần lịch đang hiệu lực và lịch nghỉ/lễ để trả lời câu hỏi “hôm nay” |
| [W7 - Hướng dẫn DSpace 2024](https://lic.ut.edu.vn/wp-content/uploads/2024/04/2024-Huong-dan-su-dung-Thu-vien-so-DSPACE.pdf) | Chỉ tới `thuvienso.ut.edu.vn/home`, hướng dẫn đăng ký bằng email trường | Cần hướng dẫn đúng hệ thống; không tự suy ra chính sách tài khoản hiện nay |
| [W8 - Thư viện số UTH](https://thuvienso.ut.edu.vn/home) | Đọc được trang công khai, có tìm kiếm và các nhóm giáo trình, khóa luận, luận văn, luận án... | Có đích tra cứu công khai; xem được metadata không đồng nghĩa được xử lý toàn văn |
| [W9 - Hỗ trợ nhanh](https://lic.ut.edu.vn/dich-vu-thu-vien/ho-tro-nhanh/) | Có liên kết hỗ trợ trực tuyến và thông tin liên hệ | Cần cán bộ xác nhận đầu mối chuyển tiếp và địa chỉ hiện hành |

**Giới hạn khảo sát:** công cụ đọc web trực tiếp nhận HTTP 403 ở nhiều trang LIC, OPAC và hai PDF hướng dẫn trên web. Nội dung các nguồn đó được đọc qua bản lập chỉ mục tìm kiếm, có thể cũ. Trang W8 đọc trực tiếp được. Chưa đăng nhập, chưa thử mượn/gia hạn, chưa khảo sát API và chưa xác minh giờ mở cửa hiện hành. HTTP 403 không chứng minh người dùng không thể truy cập trang hoặc hệ thống không có API.

**Phát hiện cần xử lý trước:** W3 và W4 không thống nhất thời hạn mượn, mức phí. Một số thông tin địa điểm ở nội dung trang hỗ trợ và chân trang cũng không đồng nhất. Không tự lấy ngày crawl của công cụ tìm kiếm làm ngày có hiệu lực. Cần một danh sách nguồn được Mentor/cán bộ nghiệp vụ xác nhận, kèm ngày áp dụng và nguồn bị thay thế.

Khảo sát OPAC trước đây chỉ được dùng để nhắc về ranh giới quyền dữ liệu; không tái sử dụng số kết quả tìm kiếm cũ hay kiến trúc D1 như kết luận hiện tại của Chatbot thư viện.

## 3. Hiện trạng repo và hướng tận dụng

Đã đọc README, tài liệu yêu cầu/API/CSDL và các điểm xử lý chính, chưa chạy ứng dụng:

- Frontend React có giao diện chat và hàm gửi tin nhắn.
- Backend FastAPI có `POST /api/chat`, hiện trả lời mẫu.
- `retrieve_context` trả chuỗi rỗng; `generate_answer` chưa được triển khai.
- CSDL chưa cấu hình; tài liệu API chưa có phần dẫn nguồn.

Đây là bộ khung, chưa phải chatbot trả lời nghiệp vụ. Giữ cấu trúc này nếu Mentor không yêu cầu công nghệ khác. Khi bắt đầu triển khai sau này, phạm vi thay đổi sẽ đi qua: nạp nguồn được duyệt → truy xuất → sinh câu trả lời → cấu trúc phản hồi API → hiển thị nguồn ở giao diện → kiểm thử và tài liệu. Không cần dựng lại repo.

## 4. Phạm vi chức năng và tiêu chí chấp nhận

| Mã | Nghiệp vụ Chatbot thư viện | Phiên bản đề xuất | Cách kiểm tra |
| --- | --- | --- | --- |
| F1 | Hỗ trợ tra cứu | Hướng dẫn OPAC/thư viện số; tìm theo tên, tác giả, chủ đề trên dữ liệu mẫu được cấp hoặc API đọc được phép; hiển thị bản ghi và liên kết gốc | Kết quả tồn tại trong dữ liệu, đúng trường thông tin; không bịa sách hoặc tình trạng còn sách |
| F2 | Giờ mở cửa | Trả lời theo cơ sở, ngày và lịch được duyệt; hỏi lại khi thiếu cơ sở; ưu tiên thông báo ngoại lệ còn hiệu lực | Đúng cơ sở, đúng khoảng ngày; không suy lịch lễ từ lịch tuần |
| F3 | Gia hạn tài liệu | Hướng dẫn theo quy trình được thư viện xác nhận; nói rõ đây là hướng dẫn | Không tuyên bố đã gia hạn khi chưa có giao dịch thành công |
| F4 | Sử dụng CSDL điện tử | Hướng dẫn từng bước cho một số nguồn được chọn, dự kiến OPAC, thư viện số, Ebook UT-XD, ProQuest/STINET tùy dữ liệu | Link đúng, điều kiện truy cập đúng tài liệu hiện hành, không tự tạo tài khoản/mật khẩu |
| F5 | Trả lời có căn cứ | Câu trả lời nghiệp vụ kèm tên nguồn, link và vị trí mục/trang khi có; hỏi lại hoặc chuyển hỗ trợ khi thiếu căn cứ | Người kiểm tra mở được nguồn và tìm được nội dung hỗ trợ câu trả lời |

F5 là yêu cầu chất lượng do kế hoạch đề xuất để bốn nghiệp vụ Chatbot thư viện đáng tin cậy.

**Gia hạn thật là nhánh cần chốt, không tự bỏ khỏi đề tài:** nếu Mentor yêu cầu, bổ sung xác thực tài khoản qua cơ chế được cấp, kiểm tra điều kiện bằng hệ thống thư viện, cho người dùng xem tài liệu và xác nhận, gửi yêu cầu, hiển thị hạn trả mới từ kết quả chính thức, lưu dấu vết tối thiểu. LLM không được tự quyết điều kiện hoặc thời hạn. Cần kiểm tra không đủ quyền, quá hạn, có người đặt trước, gửi trùng, timeout sau khi gửi và đối chiếu trạng thái trước khi thử lại.

Nếu chưa có API: đề nghị Mentor chấp thuận F3 ở mức hướng dẫn và/hoặc mô phỏng có nhãn rõ. Nếu tiêu chí yêu cầu gia hạn thật thì phần này vẫn là phụ thuộc chưa hoàn thành; demo mô phỏng không thay thế nghiệm thu giao dịch thật.

**Kênh triển khai:** chọn web cho bản đầu. Chỉ thêm Zalo hoặc Messenger nếu được chỉ định, đã có tài khoản/kênh thuộc đơn vị, quyền kết nối và thời gian kiểm thử. Không lập kế hoạch làm cả ba kênh cùng lúc mặc định.

**Chưa đưa vào bản đầu:** hỏi đáp toàn văn sách có bản quyền, huấn luyện LLM riêng, gợi ý theo lịch sử mượn, giọng nói, ứng dụng di động riêng, agent tự thao tác nhiều hệ thống. Nếu phát sinh yêu cầu phải đổi phạm vi/lịch với Mentor.

## 5. Dữ liệu cần chuẩn bị

Mục tiêu ban đầu để ước lượng công sức: khoảng 10-20 nguồn nghiệp vụ đã duyệt, 30-50 FAQ làm hạt giống, 100-300 bản ghi thư mục nếu được cấp. Có thể giảm/tăng sau khảo sát; không cần gom toàn bộ thư viện mới bắt đầu được.

| Nhóm dữ liệu | Cần xin/xác nhận | Quy tắc sử dụng |
| --- | --- | --- |
| Lịch phục vụ | Lịch từng cơ sở, ngày bắt đầu/kết thúc, ngày nghỉ, thông báo thay đổi | Thông tin có cấu trúc, kiểm tra hiệu lực theo ngày |
| Mượn/gia hạn | Văn bản hiện hành, đối tượng, số lần gia hạn, điều kiện, kênh thao tác | Tạm loại các nguồn xung đột khỏi câu trả lời khẳng định cho đến khi được xác nhận |
| Hướng dẫn CSDL | PDF/website chính thức, URL còn dùng, điều kiện truy cập trong/ngoài trường | Kiểm tra theo từng nguồn, không khái quát chính sách của một CSDL sang nguồn khác |
| Thư mục | Bản xuất CSV/JSON hoặc API đọc được phép; mã bản ghi, nhan đề, tác giả, năm, chủ đề, URL | Tìm trong phạm vi được cấp; nếu là bản chụp phải hiển thị thời điểm cập nhật |
| Tài khoản/giao dịch | Chỉ cần khi gia hạn thật; tài khoản thử và môi trường thử do đơn vị cấp | Không lấy mật khẩu qua ô chat; không đưa danh tính/lịch sử mượn vào kho tri thức |
| Câu hỏi thực tế | Câu hỏi phổ biến do cán bộ tổng hợp, đã bỏ thông tin cá nhân | Không dùng lịch sử hội thoại cá nhân khi chưa có cơ sở và quy định lưu trữ được duyệt |

Mỗi nguồn lưu tối thiểu: mã nguồn, tên, URL/tệp gốc, đơn vị sở hữu, quyền được sử dụng, cơ sở/đối tượng áp dụng, phiên bản/ngày hiệu lực, ngày kiểm tra, mục/trang, người duyệt. Khi cập nhật phải đánh dấu bản cũ ngừng dùng; kiểm tra lại một nhóm câu hỏi liên quan.

FAQ được biên soạn để tổ chức tri thức, không phải toàn bộ là bộ kiểm thử. Câu kiểm thử cuối phải được giữ riêng với câu dùng để chỉnh hệ thống.

## 6. Giải pháp dự kiến, chưa chốt công nghệ chi tiết

Luồng trả lời đề xuất:

1. Nhận câu hỏi và ngữ cảnh hội thoại cần thiết; xác định còn thiếu cơ sở, tên sách hay CSDL nào.
2. Với lịch phục vụ: dùng dữ liệu lịch có cấu trúc đã duyệt. Với tra cứu sách: lấy bản ghi từ nguồn thư mục được cấp. Với quy định/hướng dẫn: truy xuất đoạn liên quan trong kho nguồn được phép.
3. Kiểm tra quyền, hiệu lực và xung đột nguồn trước khi chuyển ngữ cảnh cho LLM.
4. LLM diễn đạt câu trả lời từ bằng chứng; không đủ căn cứ thì hỏi lại, nêu giới hạn hoặc chuyển tới hỗ trợ.
5. Trả lời kèm nguồn và thời điểm dữ liệu khi cần. Giao dịch gia hạn, nếu có, đi qua xử lý nghiệp vụ và xác thực riêng.

RAG là cách tìm nội dung liên quan trước rồi đưa cho LLM dùng làm căn cứ, phù hợp với kho hướng dẫn thay đổi theo thời gian. Tuy vậy, RAG không tự bảo đảm đúng; vẫn phải đo truy xuất, câu trả lời và dẫn nguồn. Tham khảo [Microsoft - RAG overview](https://learn.microsoft.com/en-us/azure/search/retrieval-augmented-generation-overview), chỉ để hiểu phương pháp, không phải đề xuất bắt buộc dùng Azure.

Giữ React + FastAPI đang có. Chưa thêm framework điều phối, dịch vụ đám mây hay CSDL thứ hai. Khởi đầu bằng tìm kiếm từ khóa/FAQ để có mốc so sánh; bổ sung truy xuất ngữ nghĩa nếu bộ câu hỏi cho thấy cần. PostgreSQL/pgvector là phương án đã nêu trong repo, chỉ chốt sau khi biết dữ liệu và môi trường vận hành. Chưa chọn model hoặc nhà cung cấp API khi chưa có yêu cầu dữ liệu, phần cứng và ngân sách; không cần fine-tune trong bản đầu.

Khi thử AI phải ghi chi phí trên lượt hỏi, thời gian phản hồi, chất lượng tiếng Việt và điều kiện dữ liệu được gửi ra ngoài. Nếu chưa được phép dùng API ngoài, giữ tiến độ ở dữ liệu/FAQ/thiết kế hoặc thử môi trường nội bộ được chấp thuận; không tự tải dữ liệu nội bộ lên dịch vụ.

Nội dung truy xuất là dữ liệu, không được có quyền thay đổi quy tắc chatbot hoặc gọi giao dịch. Kiểm tra prompt injection trực tiếp và qua tài liệu, tránh hiển thị HTML/script từ câu trả lời, giữ khóa API ở backend, giới hạn kích thước/yêu cầu, không ghi bí mật vào log. Căn cứ rủi ro: [OWASP - Prompt Injection](https://genai.owasp.org/llmrisk/llm01-prompt-injection/).

## 7. Kế hoạch còn lại đến 28/12/2026 và phân công 4 thành viên

Các tuần dưới đây là khoảng quản lý công việc tính từ 27/10, không phải tuần học chính thức. Các bước phát triển là kế hoạch tương lai; lần làm việc hiện tại chỉ cập nhật tài liệu, chưa bắt đầu code.

| Tuần / thời gian năm 2026 | Công việc | Đầu ra và điều kiện chuyển bước |
| --- | --- | --- |
| 1: 27/10-02/11 | Xác nhận Mentor, nhiệm vụ và thời lượng làm việc; khảo sát; xin nguồn/API; chốt bốn nghiệp vụ, gia hạn mức nào, kênh web; phác thảo hội thoại/giao diện và thiết kế bộ đánh giá | **M1 - 02/11:** đặc tả, phân công, nguồn mẫu được duyệt, tiêu chí nghiệm thu. Có quyết định về dữ liệu tra cứu và nhánh gia hạn; chỉ chuyển sang phát triển sau khi phạm vi được thống nhất và người dùng cho bắt đầu code |
| 2: 03/11-09/11 | Chuẩn hóa nguồn/FAQ/lịch; dựng mốc tìm kiếm từ khóa; hoàn thiện luồng web-API có hiển thị nguồn | F2 và FAQ chạy trên nguồn được duyệt; baseline, ca thiếu cơ sở/nguồn và lỗi dịch vụ được ghi nhận |
| 3: 10/11-16/11 | Truy xuất hướng dẫn và LLM nếu điều kiện sử dụng đã rõ; xử lý thiếu căn cứ/xung đột; bổ sung hướng dẫn CSDL | F4 và câu trả lời có dẫn nguồn được kiểm tra; không suy diễn điều kiện truy cập; có bản nháp Chương 1-2 |
| 4: 17/11-23/11 | Tra cứu tài liệu qua bản xuất hoặc API đọc được cấp; tích hợp kết quả vào hội thoại | F1 trả bản ghi thật, link gốc và thời điểm dữ liệu; không bịa sách hoặc tình trạng sẵn có |
| 5: 24/11-30/11 | Hoàn thiện gia hạn ở mức đã duyệt; nếu có giao dịch thật thì kiểm tra xác thực, điều kiện, gửi trùng và timeout | F3 được cán bộ kiểm tra; chỉ báo thành công từ phản hồi chính thức; ghi kết quả và giới hạn vào Chương 3 |
| 6: 01/12-07/12 | Tích hợp toàn bộ bốn nghiệp vụ; sửa lỗi hội thoại/giao diện; kiểm tra quyền dữ liệu, chi phí và môi trường bàn giao | Bản dùng thử đủ luồng đã cam kết; rà tiến độ và bỏ các tính năng mở rộng chưa cần thiết |
| 7: 08/12-14/12 | Kiểm tra nội bộ, cài thử; hoàn thiện hướng dẫn vận hành và kịch bản demo; chuẩn bị thử với cán bộ | **M2 - 14/12:** chốt tính năng, ghi rõ phần chưa đạt; bộ kiểm thử cuối sẵn sàng, báo cáo có bản nháp đầy đủ |
| 8: 15/12-21/12 | Cán bộ/người dùng thử; chấm bộ kiểm thử cuối; sửa lỗi và kiểm tra lại phần thay đổi | **M3 - 21/12:** bảng đánh giá AI/nghiệp vụ, phản hồi người dùng, nghiệm thu thử; báo cáo và tài liệu bàn giao gần hoàn chỉnh |
| 9: 22/12-28/12 | Xử lý lỗi còn lại, kiểm tra bàn giao, hoàn thiện báo cáo/slide, tập huấn và demo; tiếp nhận đánh giá đơn vị | Hồ sơ và bản bàn giao sẵn sàng **25/12** để có thời gian dự phòng; **M4 - chậm nhất 28/12:** hoàn tất theo lịch đơn vị xác nhận |

**Mốc xử lý phụ thuộc:** đến 02/11 cần biết nguồn nào được dùng, ai cấp dữ liệu tra cứu/API gia hạn và ngày cấp dự kiến. Nếu không có cam kết cấp kịp, báo Mentor để chốt bản xuất thư mục được phép và gia hạn mức hướng dẫn/mô phỏng. Nếu Mentor vẫn yêu cầu API/giao dịch thật, giữ phần đó là rủi ro chưa giải quyết, xác định người phụ trách và lịch cấp cụ thể; không tự hạ tiêu chí hoặc chờ đến tháng 12 mới báo.

Ưu tiên web và đủ bốn nghiệp vụ ở mức được thống nhất. Zalo/Messenger chỉ bổ sung khi Mentor bắt buộc và kế hoạch vẫn giữ được hai tuần cuối cho đánh giá/bàn giao. Không cắt kiểm thử để bù tính năng mở rộng. Thời hạn 28/12 là ngày kết thúc do người dùng cung cấp; ngày bảo vệ, hạn nộp từng loại hồ sơ và lịch cán bộ tham gia cần xác nhận riêng.

### Phân công đề xuất

Dùng ký hiệu TV1-TV4 cho đến khi có tên và năng lực từng người; đây là đề xuất phân công, chưa phải nhiệm vụ đã giao chính thức.

| Thành viên | Phụ trách chính | Đầu ra chịu trách nhiệm | Phối hợp |
| --- | --- | --- | --- |
| TV1 | Điều phối nghiệp vụ và dữ liệu | Biên bản yêu cầu; nguồn được duyệt; FAQ/lịch/hướng dẫn CSDL; theo dõi phụ thuộc; tổng hợp báo cáo tiến độ | Cán bộ/Mentor xác nhận nghiệp vụ; TV2 dùng dữ liệu; TV4 chuẩn bị đáp án kiểm thử |
| TV2 | Backend, truy xuất và AI | API chat; tìm kiếm; câu trả lời có nguồn; kết nối tra cứu/gia hạn nếu được cấp; đo chi phí và độ trễ | TV1 kiểm tra căn cứ; TV3 tích hợp; TV4 kiểm thử giao dịch/lỗi |
| TV3 | Giao diện và tích hợp web | Luồng hội thoại; hiển thị nguồn/kết quả; trạng thái tải/lỗi; khả năng dùng trên điện thoại; tích hợp API và tài liệu người dùng | Chốt định dạng phản hồi với TV2 ngay tuần 1; dùng phản hồi thử nghiệm của TV4 |
| TV4 | Kiểm thử, môi trường và hồ sơ bàn giao | Bộ ca và kết quả kiểm thử; cài thử; hướng dẫn vận hành; tổng hợp báo cáo/slide và kịch bản demo | TV1 duyệt đáp án với cán bộ; TV2/TV3 sửa lỗi và viết tài liệu phần mình |

Tất cả thành viên tự viết phần việc mình thực hiện, cập nhật nhật ký và kiểm tra chéo ít nhất một phần liên quan. TV4 tổng hợp tài liệu, không phải làm thay báo cáo của ba người còn lại. Nếu TV2 quá tải do gia hạn thật hoặc tích hợp phức tạp, TV4 hỗ trợ API/kiểm thử tích hợp sau khi bộ kiểm thử đã chuẩn bị; cân lại đầu việc trước khi nhận thêm tính năng.

Trong tuần đầu: TV1 chốt khảo sát và nguồn; TV2 đánh giá khả năng kết nối từ tài liệu/API được cấp; TV3 phác thảo giao diện/hội thoại; TV4 chuẩn bị khung kiểm thử, mẫu báo cáo và nhật ký. Chỉ nghiên cứu và thiết kế ở giai đoạn chưa được yêu cầu bắt đầu code.

## 8. Đánh giá và nghiệm thu đề xuất

Chuẩn bị khoảng **100 tình huống độc lập**: 20 để thử/chỉnh, 80 giữ riêng để đánh giá cuối. Trong 80 tình huống cuối dự kiến: 20 FAQ/lịch, 15 tra cứu, 15 hướng dẫn CSDL, 10 gia hạn, 20 thiếu thông tin/ngoài phạm vi/xung đột nguồn/an toàn. Cần có cách diễn đạt khác, câu không dấu và lỗi gõ. Cán bộ xác nhận đáp án, nguồn đúng và hành vi mong đợi trước khi chấm. Nếu phạm vi API thay đổi, cập nhật bộ kiểm thử trước khi đóng băng đánh giá.

| Chỉ tiêu | Cách đo | Mục tiêu đề xuất |
| --- | --- | --- |
| Đúng nghiệp vụ | Số câu đúng và đủ bước / số câu có đáp án; cán bộ chấm, không chỉ LLM tự chấm | Từ 85%; báo cáo riêng từng nhóm, tử số/mẫu số |
| Nguồn hỗ trợ câu trả lời | Số khẳng định kiểm chứng được và thực sự được nguồn hỗ trợ / tổng khẳng định cần dẫn nguồn | Từ 95%; link tồn tại chưa đủ để tính đúng |
| Tìm đúng tài liệu | Tỷ lệ truy vấn có ít nhất một tài liệu liên quan trong 5 kết quả đầu, trên bộ truy vấn có tài liệu liên quan đã gán nhãn | Hit@5 từ 80%; so baseline từ khóa với giải pháp sau cùng |
| Thiếu/xung đột/ngoài phạm vi | Hỏi lại hoặc nêu giới hạn đúng thay vì bịa đáp án | Ít nhất 18/20 tình huống cuối có hành vi đúng |
| Hiệu năng | Độ trễ p50/p95 và lỗi trên môi trường được ghi cấu hình, ít nhất 100 lượt hỏi ở tải 5 người đồng thời | Đề xuất p95 không quá 10 giây; hiệu chỉnh trước nghiệm thu theo môi trường/API được duyệt |
| Chi phí | Token/lượt, tiền/lượt theo giá thực trả, tổng ngân sách thử nghiệm | Có ngân sách Mentor/nhóm chốt trước gọi dịch vụ trả phí; không cam kết miễn phí |
| An toàn/giao dịch | Bộ ca truy cập chéo tài khoản, lộ khóa, giả thành công, gửi trùng và timeout nếu có gia hạn thật | Không có lỗi nghiêm trọng trong bộ ca đã chạy; không coi đây là bằng chứng an toàn tuyệt đối |

Điều kiện chặn nghiệm thu: bịa giao dịch thành công, lộ bí mật/dữ liệu người khác, dùng quy định chưa được xác nhận để khẳng định quyền lợi, hoặc thiếu nghiệp vụ mà đặc tả đã cam kết. Không lấy điểm trung bình cao để bỏ qua các lỗi này.

Ghi rõ tập dữ liệu/phiên bản nguồn, cấu hình, thời điểm đo, cách chấm và giới hạn mẫu thử. Lưu câu trả lời sai và cách xử lý để đưa vào Chương 3. Demo tốt không thay cho bảng đánh giá AI mà T1 yêu cầu.

## 9. Thực hiện đúng quy trình HKDN

Theo T2, cần kiểm tra tình trạng: đăng ký nguyện vọng → được trường phân bổ → nhận Mentor/giảng viên đầu mối → nhận nhiệm vụ. Việc chọn Chatbot thư viện để chuẩn bị không tự xác nhận đã được phân bổ.

Đề xuất báo cáo mỗi tuần một lần, **tần suất chính thức do Mentor quy định**. Mỗi báo cáo có: công việc đã làm; kết quả và link minh chứng được phép; khó khăn; việc đang làm; kế hoạch tiếp theo. Thêm ngày/người phụ trách/phản hồi và cách xử lý để theo dõi được trách nhiệm.

Không tự công bố dữ liệu, mã nguồn, tài liệu nội bộ; đây là yêu cầu trực tiếp của T2 mục 7. Xác nhận quyền đưa từng loại nội dung vào repo và phụ lục. Việc bàn giao mã nguồn cho đơn vị không đồng nghĩa được đẩy lên GitHub công khai. Lần khảo sát này chưa commit, push, xuất bản hay liên hệ bên ngoài.

Đánh giá HKDN không chỉ là điểm chatbot: đơn vị đánh giá tác phong, kỷ luật, trách nhiệm, chuyên môn, giải quyết vấn đề, làm việc nhóm/giao tiếp và chất lượng công việc theo mẫu trường (T2 mục 9).

### Dàn ý báo cáo cuối kỳ theo đúng T2

| Chương | Nội dung bắt buộc theo hướng dẫn | Minh chứng Chatbot thư viện nên thu thập |
| --- | --- | --- |
| 1. Giới thiệu doanh nghiệp và vị trí thực hiện | Giới thiệu, lĩnh vực, bộ phận, vai trò sinh viên, Mentor/nhóm | Thông tin LIC được xác nhận, phân công và đóng góp cá nhân |
| 2. Tổng quan dự án/công việc | Bối cảnh, mục tiêu, vấn đề, phạm vi, yêu cầu, công nghệ/công cụ | Khảo sát, đặc tả được duyệt, lý do chọn giải pháp |
| 3. Nội dung thực hiện | Phân tích, phương pháp, triển khai, kết quả, kiểm thử, vấn đề/cách giải quyết | Sơ đồ, phiên bản dữ liệu, ảnh demo, bảng đo, ca lỗi và cách khắc phục |
| 4. Kết quả và kinh nghiệm | Kết quả, kiến thức, kỹ năng chuyên môn/nhóm/giao tiếp, khó khăn/bài học, cải thiện | So mục tiêu với kết quả thực tế, phản hồi Mentor, giới hạn còn lại |
| 5. Kết luận | Kết quả chính, mức hoàn thành, kinh nghiệm, hướng phát triển chuyên môn | Kết luận đúng mức đã thực hiện và được nghiệm thu |

Phụ lục: nhật ký, ảnh quá trình, sơ đồ/thiết kế, kiểm thử, minh chứng sản phẩm và tài liệu khác **được đơn vị cho phép**. Hai PDF chưa cung cấp đầy đủ biểu mẫu báo cáo/đánh giá, định dạng trang hay hạn nộp; cần xin mẫu chính thức, không tự thay bằng mẫu “thực tập tốt nghiệp” cũ trên web.

Hồ sơ bàn giao dự kiến: mã nguồn và hướng dẫn cài đặt theo phiên bản; danh sách nguồn/quyền/phiên bản; cấu hình mẫu không có bí mật; bảng kiểm thử AI/nghiệp vụ; hướng dẫn bạn đọc; hướng dẫn cán bộ cập nhật dữ liệu và vận hành; báo cáo, slide/demo; danh sách giới hạn và biên bản bàn giao/đánh giá theo mẫu đơn vị.

## 10. Việc cần chốt trước khi viết code

1. Nhóm đã xác nhận 4 người và kết thúc 28/12/2026; cần bổ sung tên/năng lực, thời lượng mỗi tuần, việc đã làm, ngày bắt đầu chính thức và hạn nộp/bảo vệ cụ thể.
2. Chatbot thư viện đã được phân bổ chưa; ai là Mentor, giảng viên đầu mối và người xác nhận nghiệp vụ?
3. Web có đủ yêu cầu kênh không; có bắt buộc Zalo/Messenger không?
4. Gia hạn cần hướng dẫn hay thực hiện thật; nếu thật, ai cung cấp API/tài khoản thử và cơ chế xác thực?
5. Văn bản nào đang hiệu lực về mượn, gia hạn, phí, lịch phục vụ và địa điểm? Nguồn nào thay thế nguồn nào?
6. Được cấp dữ liệu thư mục/bản xuất hoặc API nào; dữ liệu được dùng, gửi cho AI và đưa vào repo/báo cáo đến mức nào?
7. Máy chủ, ngân sách AI, chính sách lưu hội thoại và người chịu trách nhiệm cập nhật nguồn sau bàn giao?
8. Mẫu báo cáo, mẫu đánh giá, hạn nộp và tiêu chí nghiệm thu cuối cùng của đơn vị?

Việc có thể làm ngay trong giai đoạn chưa code: mang kế hoạch này trao đổi với Mentor; hoàn thiện câu hỏi khảo sát và danh mục nguồn; lập đặc tả bốn nghiệp vụ, phác thảo hội thoại/giao diện và bộ ca kiểm thử. Sản phẩm cần có trước khi chuyển sang phát triển là **đặc tả đã thống nhất + nguồn được duyệt + tiêu chí nghiệm thu + lịch/phân công**.

## 11. Rủi ro và phương án xử lý

| Rủi ro | Hành động khi xảy ra |
| --- | --- |
| Nguồn cũ hoặc mâu thuẫn | Dừng khẳng định nội dung đó, xin nguồn hiện hành; lưu lịch sử duyệt |
| Chưa cấp dữ liệu tra cứu/API gia hạn | Báo và chốt hướng xử lý từ mốc 02/11; đề nghị bản xuất được phép hoặc điều chỉnh phạm vi có xác nhận, không ghi phần chưa làm là hoàn thành |
| API AI tốn phí/chậm hoặc không được phép gửi dữ liệu | Đo trên dữ liệu công khai/được phép, giới hạn thử nghiệm theo ngân sách; đổi phương án sau khi có điều kiện rõ |
| Thời gian/nhân lực ít hơn dự kiến | Bỏ kênh và chức năng mở rộng, giảm số nguồn; giữ nghiệp vụ đã chốt, đánh giá và hồ sơ HKDN |
| Cán bộ không có thời gian chấm | Chốt sớm lịch duyệt đáp án và thử nghiệm; ưu tiên bộ mẫu nhỏ có nhãn chất lượng, báo rõ giới hạn đánh giá |

Kế hoạch này hoàn tất bước nghiên cứu sơ bộ và chuẩn bị triển khai. Chưa xác nhận hiệu lực quy định, quyền dữ liệu, tính khả dụng API hoặc khả năng gia hạn thật. Các việc đó là đầu vào phải chốt với đơn vị, không thể suy ra chỉ từ PDF và website công khai.
