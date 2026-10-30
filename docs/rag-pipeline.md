# Pipeline LLM / RAG thư viện

Hệ thống dùng React/FastAPI/SQLite, FastEmbed multilingual MiniLM, Qdrant và Ollama `qwen3:4b` đã có trong dự án. Không huấn luyện lại model nền, không cần dịch vụ LLM trả phí, không trả lời kiến thức chung ngoài thư viện.

## Luồng xử lý

1. Quản trị nhập nội dung, URL HTTPS và ngày đối chiếu trong **Kho tri thức**. Crawler chỉ tạo bản nháp; người quản trị đối chiếu và xuất bản. Nguồn hết hiệu lực hoặc bị thu hồi bị loại. Các mục `needs_confirmation` chỉ được trả với cảnh báo phù hợp, không được đưa vào phần sinh câu trả lời bằng model.
2. FAQ khớp mạnh giữ nguyên hướng dẫn đã duyệt. Sách đi qua truy vấn metadata; giờ, phí và thời hạn giữ các điều kiện xác minh nghiệp vụ. Không thấy sách trong bản chụp không có nghĩa thư viện không có sách.
3. Các câu khác dùng câu hỏi/từ khóa đã duyệt, tìm nội dung theo đoạn và vector. Khớp câu hỏi đã duyệt được ưu tiên hơn từ xuất hiện tình cờ trong phần thân. Khi có cả lexical và semantic, hợp nhất bằng reciprocal rank fusion, mẫu số60 + thứ hạng. Khớp mạnh không cần embedding hoặc LLM.
4. Đoạn tối đa384 byte UTF-8, chồng lấn tối đa48 byte, không cắt giữa byte của ký tự. Metadata được nhúng riêng. Mỗi đoạn có source ID, hash toàn bộ hàng và thứ tự trong payload Qdrant.
5. Cấp tối đa2 đoạn mỗi nguồn trong3 nguồn đứng đầu cho LLM. Chỉ chuỗi con của câu trả lời gốc làm bằng chứng; metadata có thể hỗ trợ xếp hạng. Model được thông báo đây là trích đoạn và không được suy đoán phần chưa thấy.
6. Chỉ nhận JSON có answer/source_ids hợp lệ. Số và URL phải xuất hiện trọn vẹn trong cả bằng chứng đã chọn và câu trả lời gốc được trích dẫn, tránh công nhận phần bị cắt ở biên đoạn. Sau khi model trả lời, đọc lại nguồn SQLite để phát hiện thay đổi/thu hồi trong lúc xử lý.
7. Lỗi embedding/model, prompt quá lớn hoặc output không hợp lệ dùng hướng dẫn có nguồn phù hợp hoặc nói rõ chưa đủ căn cứ. Không tạo sách, số bản rỗi, giao dịch hay chính sách mới.

Các kiểm tra nguồn/số/URL không phải kiểm chứng ngữ nghĩa hình thức: diễn giải vẫn cần đánh giá nghiệp vụ. Tập phát triển không đo đầy đủ hallucination rate, không thay thế nghiệm thu cán bộ thư viện.

## Chỉ mục và vận hành

Collection mới: `knowledge_chunks_v1_<model hash>`, `books_chunks_v1_<model hash>`. Collection cũ được giữ; không tự xóa collection hay dữ liệu nghiệp vụ. ID điểm ổn định theo nguồn/hash/thứ tự. Đồng bộ đọc payload đã lưu, nhúng/upsert phần mới trước, chờ hoàn tất rồi xóa điểm lỗi thời trong collection đang quản lý. Khởi động lại với nguồn không đổi không nhúng lại. Lỗi ghi không được đánh dấu sẵn sàng; lượt sau có thể tiếp tục.

Tìm kiếm đối chiếu payload hash với nguồn hiện tại. Chỉ mục sách chứa toàn bộ sách đã xuất bản, lọc loại bằng source ID trước giới hạn kết quả. Tra cứu sách một từ/mã dùng lexical/fuzzy; chỉ chuyển sang vector cho mô tả có ít nhất2 từ có nghĩa để tránh mã không tồn tại trở thành đề xuất không liên quan. Qdrant local dùng một tiến trình ứng dụng. Chỉ mục tái tạo được; SQLite vẫn là nguồn nghiệp vụ.

Vào **Quản trị → Hệ thống**:

- **Kiểm tra mô hình** hỏi catalog Ollama cục bộ, không tải model/sinh câu trả lời; không chứng minh chất lượng inference.
- **Kiểm tra truy xuất** hiển thị phương thức, điểm xếp hạng, trích đoạn, URL và ngày kiểm tra. Không gửi lịch sử riêng của bạn đọc vào phép thử. Điểm xếp hạng không phải xác suất đúng.
- **Cập nhật chỉ mục** đồng bộ FAQ; xem `vectors.namespaces.knowledge` để biết số nguồn/đoạn. Chỉ mục sách cập nhật khi cần tìm ngữ nghĩa.

CLI từ repository:

```powershell
Push-Location backend
./.venv/Scripts/python.exe -m app.cli ai-check
# Thoát0: model có trong catalog cục bộ; thoát1: chưa kiểm chứng.
# Dừng API trước index để tránh tranh khóa Qdrant local.
./.venv/Scripts/python.exe -m app.cli index
Pop-Location
```

`ai-check` không mở/tạo database, không gọi provider trả phí. Nếu model chưa có, chuẩn bị chủ động theo README; ứng dụng không tự pull. Lần đầu embedding có thể tải model nếu cache chưa có.

Giới hạn: body chat1MiB; câu hỏi/ngữ cảnh truy xuất16.000 ký tự; query embedding384 byte UTF-8 (quá giới hạn dùng toàn bộ câu hỏi qua lexical, không âm thầm cắt để nhúng); prompt model6.144 byte UTF-8; lịch sử6 lượt/tổng4.000 ký tự có đánh dấu; Ollama context8192/output1000 token; tối đa2 request model đồng thời trong một tiến trình. Không cam kết xử lý vô hạn hay độ trễ cố định.

API tham chiếu: [Qdrant Python client](https://github.com/qdrant/qdrant-client), [Ollama API](https://github.com/ollama/ollama/blob/main/docs/api.md). Đã đối chiếu Context7 và kiểm thử trên phiên bản cài trong dự án.
