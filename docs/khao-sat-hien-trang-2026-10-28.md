# Khảo sát hiện trạng Chatbot thư viện — 28/10/2026

Tài liệu ghi nhận kết quả đọc repo, kiểm tra công cụ và khảo sát web để chuẩn bị phát triển. Đây chưa phải thiết kế đã duyệt hoặc bằng chứng ứng dụng chạy thành công.

## 1. Phạm vi và quyết định của người dùng

- Dùng repo `D:/Github/Group4-HKDN` để phát triển đồ án HKDN Chatbot thư viện — Chatbot Thư viện UTH.
- Bốn nghiệp vụ: hỗ trợ tra cứu, giờ mở cửa, gia hạn tài liệu, hướng dẫn sử dụng cơ sở dữ liệu điện tử.
- Người dùng xác nhận ngày 28/10: ưu tiên gia hạn thật nếu có điều kiện tích hợp; bản đầu có thể hướng dẫn quy trình.
- Người dùng xác nhận ngày 28/10: chưa được cấp tài liệu nghiệp vụ, bản xuất danh mục hoặc API; hiện chỉ có thể tra cứu trên web thư viện.
- Kế hoạch trong repo ghi nhóm 4 người, hạn kết thúc 28/12/2026; chưa xác nhận lại lịch bảo vệ hoặc phân công cá nhân trong lượt khảo sát này.
- Nhà cung cấp LLM, ngân sách, nơi triển khai, quyền sử dụng dữ liệu và quy định lưu hội thoại vẫn chưa được chốt.

## 2. Căn cứ đã kiểm tra

- `README.md`, `docs/requirements.md`, `docs/api-design.md`, `docs/database-design.md`, toàn bộ kế hoạch Chatbot thư viện.
- Các điểm vào frontend/backend, thành phần chat, cấu hình và các service hiện có; tìm kiếm các nơi gọi chúng.
- Hai PDF gốc còn tồn tại ngoài repo: `D:/Download/De tai tong hop LIC UTH.pdf` (8 trang), `D:/Download/Huong dan thuc hien HKDN.pdf` (6 trang). Đã trích đọc trọn các trang liên quan: tài liệu đề tài trang PDF 2, 7–8; hướng dẫn HKDN trang 4–6.
- PDF đề tài xác nhận bốn nghiệp vụ Chatbot thư viện, gợi ý LLM và Zalo/Messenger/web; không bắt buộc đồng thời ba kênh. Đầu ra gồm mã nguồn, tài liệu kỹ thuật, hướng dẫn vận hành, báo cáo, demo và bảng đánh giá độ chính xác cho đề tài AI.
- PDF hướng dẫn xác nhận báo cáo 5 chương, báo cáo tiến độ theo tần suất Mentor quy định và yêu cầu bảo mật thông tin nội bộ.
- Đã đọc ghi chú biên tập báo cáo; chưa kiểm tra bố cục PDF báo cáo hoặc biên dịch lại LaTeX.

## 3. Hiện trạng mã nguồn

| Phần | Đã có | Chưa có / giới hạn |
| --- | --- | --- |
| Giao diện | React 19, Vite 6; `App.jsx` quản lý tin nhắn, trạng thái gửi và lỗi | Chưa hiển thị nguồn, chưa có ngữ cảnh hội thoại gửi lên API |
| Gọi API | `sendMessage` trong `frontend/src/services/chatApi.js` gọi `POST /api/chat` | Địa chỉ mặc định `http://127.0.0.1:8000`; lỗi đều hiện thông báo kiểm tra backend |
| Component riêng | Có `ChatInput`, `ChatMessage`, `ChatWindow` | Đều trả `null`, chưa được dùng; chưa có lý do phải tách giao diện ngay |
| Backend | FastAPI, `GET /health`, schema request/response | `POST /api/chat` chỉ trả câu nhắc lại câu hỏi |
| Truy xuất | Có `retrieve_context(question)` | Trả chuỗi rỗng, chưa được route gọi |
| LLM | Có `generate_answer(question, context)` | Ném `NotImplementedError`, chưa được route gọi |
| CSDL | Có `get_database_status()` | Chỉ trả `database_not_configured`, chưa có schema hoặc kết nối |
| Dữ liệu | Hai thư mục `data/faq`, `data/documents` | Chỉ có README, chưa có dữ liệu để truy xuất |
| Kiểm thử | Có thư mục `tests` | Chỉ có README, chưa có ca kiểm thử tự động |
| Tái lập môi trường | Có requirements và package manifest | Python chưa ghim phiên bản thư viện; chưa có lockfile frontend trong Git |

Luồng hiện có qua đọc mã: `App.handleSubmit → sendMessage → POST /api/chat → ChatResponse.answer → App`.

Các điểm cần đưa vào kiểm thử khi bắt đầu sửa:

- `ChatRequest` kiểm tra độ dài trước khi route gọi `.strip()`: chuỗi toàn khoảng trắng vẫn qua validation hiện tại. Frontend chặn trường hợp này, API chưa chặn.
- CORS chỉ cho phép origin `http://localhost:5173`; mở frontend bằng `127.0.0.1` hoặc cổng khác cần cấu hình tương ứng.
- `/health` hiện chỉ phản ánh backend phản hồi, chưa phản ánh dữ liệu/LLM/CSDL sẵn sàng.
- `.env.example` có tên biến nhưng backend chưa đọc cấu hình hoặc gọi dịch vụ tương ứng. Chưa có bằng chứng khóa AI/CSDL đã được cấu hình.

## 4. Công cụ và giới hạn kiểm tra môi trường

- Đã chạy: Node.js `v24.20.0`, npm `12.1.0`; Python `3.11.17` từ cài đặt do uv quản lý.
- Chưa có `backend/.venv` hoặc `frontend/node_modules` trong checkout lúc khảo sát.
- `uv python list --only-installed` cảnh báo một đường dẫn Python 3.13 cũ không tồn tại; Python 3.11.17 gọi trực tiếp thành công. Không sửa môi trường chung của máy.
- Chưa cài dependency, chạy server, build frontend hoặc chạy kiểm thử nghiệp vụ.
- Đối chiếu tài liệu qua Context7 MCP: FastAPI CORS và biến môi trường Vite 6. `VITE_` được đưa ra mã phía trình duyệt; khóa LLM phải ở backend.

Tài liệu chính thức: [FastAPI CORS](https://fastapi.tiangolo.com/tutorial/cors/), [Vite 6 env](https://v6.vite.dev/guide/env-and-mode).

## 5. Khảo sát web ngày 28/10

| Nguồn | Kết quả công cụ trong lượt này | Cách dùng trước mắt |
| --- | --- | --- |
| [Trang LIC](https://lic.ut.edu.vn/) | Mở trực tiếp nhận 403; đọc được nội dung lập chỉ mục tìm kiếm | Đầu mối tìm nguồn; cần kiểm tra nội dung gốc trước khi đưa vào kho dùng chính thức |
| [Thư viện số](https://thuvienso.ut.edu.vn/home) | Đọc trực tiếp được; có ô tìm kiếm và danh mục tài nguyên | Đích hướng dẫn tra cứu; chưa kiểm tra tìm kiếm tự động hoặc API |
| [OPAC](https://opacthuvien.ut.edu.vn/opac/) | Công cụ mở trực tiếp nhận 403 | Chưa kết luận khả năng tích hợp; chưa đăng nhập hoặc thử giao dịch |
| [Danh sách tài nguyên](https://lic.ut.edu.vn/thong-tin-cac-tai-lieu-co-ban-quyen-da-duoc-xay-dung-va-trien-khai-tren-cac-he-thong-cua-nha-truong/) | Đọc được qua kết quả tìm kiếm | Nguồn ứng viên để hướng dẫn OPAC, ebook và CSDL; chưa kiểm tra quyền truy cập hiện hành |
| [Thông báo ngoài giờ](https://lic.ut.edu.vn/thong-bao-ve-viec-mo-cua-phuc-vu-ban-doc-ngoai-gio/) | Nội dung tìm kiếm ghi thông báo tháng 6/2022 | Không coi là lịch phục vụ hiện hành năm 2026 |
| [Quy định mượn trả](https://lic.ut.edu.vn/quy-dinh-muon-tra-tai-lieu/), [Nội quy](https://lic.ut.edu.vn/noi-quy-thu-vien/) | Kết quả tìm kiếm tồn tại; mở trực tiếp cả hai nhận 403 | Kế hoạch cũ ghi có xung đột; lượt này chưa đọc đủ hai văn bản để xác nhận lại chi tiết |

403 là kết quả truy cập của công cụ, không chứng minh website không dùng được trong trình duyệt hoặc hệ thống không có API. Bản lập chỉ mục có thể cũ. Chưa xác minh được quy trình gia hạn hiện hành; không tự soạn điều kiện, số lần gia hạn, phí hoặc hạn trả.

Hiện có thể chuẩn bị danh mục nguồn công khai và câu hỏi cần trả lời. Chưa có căn cứ tuyên bố đã tra cứu được sách qua API hoặc đã gia hạn thật. Không lấy toàn văn sách có bản quyền hoặc dữ liệu tài khoản làm dữ liệu thử.

## 6. Phạm vi thay đổi khi bắt đầu phát triển

Giữ React + FastAPI hiện có. Các vị trí phải đi cùng nhau khi bổ sung trả lời có nguồn:

1. Nguồn và metadata trong `data/` → có URL gốc, ngày kiểm tra, tình trạng hiệu lực/xác minh.
2. `rag_service.py` → truy xuất bằng chứng thay cho chuỗi rỗng.
3. `llm_service.py` → chỉ tích hợp sau khi chọn dịch vụ và điều kiện gửi dữ liệu.
4. `api/chat.py` → validation, phản hồi có nguồn và hành vi thiếu căn cứ; cập nhật `docs/api-design.md` tương ứng.
5. `chatApi.js`, `App.jsx` → thống nhất cấu trúc phản hồi, hiển thị dẫn nguồn và trạng thái lỗi.
6. `tests/` → kiểm tra câu hỏi hợp lệ, chỉ khoảng trắng, quá dài, thiếu nguồn, nguồn xung đột và lỗi dịch vụ; tách câu thử/chỉnh khỏi bộ đánh giá cuối.
7. Cấu hình mẫu và README → chỉ thêm cấu hình thực sự được dùng, có hướng dẫn chạy và kiểm chứng.

Đây là bản đồ phạm vi, chưa chốt giải pháp triển khai. Chưa cần thêm framework điều phối, vector database, đăng nhập hoặc kênh Zalo/Messenger chỉ để hoàn thiện khung.

## 7. Bước tiếp theo và cách kiểm chứng đề xuất

1. Chốt cách khởi đầu: nguồn web được rà soát + FAQ/tìm từ khóa làm mốc so sánh, hoặc triển khai RAG ngay. Cần cân nhắc dữ liệu còn ít và chưa chọn dịch vụ AI.
2. Chuẩn bị bộ nguồn nhỏ và các trường hợp hỏi thật → từng đáp án truy về được nguồn; nội dung cũ/xung đột được đánh dấu và không dùng làm kết luận hiện hành.
3. Thống nhất thiết kế bản đầu trước khi viết mã → ghi rõ tra cứu ở mức hướng dẫn hay tìm kết quả trong chatbot, cách dẫn nguồn, xử lý thiếu thông tin và phạm vi gia hạn.
4. Sau khi thiết kế được duyệt, lập kế hoạch thực hiện → cài môi trường riêng, kiểm chứng khung chat, sửa các lỗi đã tái hiện và làm một luồng trả lời có nguồn từ đầu đến cuối.
5. Đánh giá trên bộ câu hỏi độc lập trước khi mở rộng → không đánh đồng chạy được demo với đúng nghiệp vụ thư viện.

Gia hạn thật là bước tích hợp có điều kiện, chưa bị loại khỏi hướng phát triển. Để thực hiện cần có cơ chế được cấp phép, xác thực, tài khoản thử và xác nhận kết quả từ hệ thống thư viện; không nhận mật khẩu thư viện trong ô chat hoặc báo thành công bằng câu trả lời do LLM tạo.

## 8. Cập nhật sau khi người dùng chọn hướng triển khai

- Người dùng đã chọn FAQ + tìm kiếm từ khóa trên nguồn đã rà soát; yêu cầu làm chỉn chu.
- Đã đọc trực tiếp bằng trình duyệt trang chủ LIC, Quy định mượn trả, Nội quy và Hỗ trợ nhanh. Lỗi 403 của công cụ đọc web không ngăn việc đọc các trang công khai này bằng trình duyệt.
- Xác nhận lại xung đột: Quy định mượn trả ghi không quá một học kỳ, 500đ/ngày/cuốn; Nội quy ghi 45 ngày, 1.000đ/cuốn/ngày. Chưa xác định văn bản nào đang áp dụng hoặc thay thế văn bản nào.
- Trang Hỗ trợ nhanh có email `lic@ut.edu.vn` và liên kết `https://support.ut.edu.vn/`. Số điện thoại, phòng và một số địa chỉ trong nội dung khác thông tin trang chủ; chưa tự hợp nhất thành một đáp án hiện hành.
- Thiết kế đề xuất nằm tại `docs/superpowers/specs/2026-10-28-faq-keyword-design.md`; được rà soát độc lập về khả năng lập kế hoạch, chưa có câu hỏi quan trọng còn thiếu. Trạng thái vẫn chờ người dùng duyệt trước khi triển khai.
