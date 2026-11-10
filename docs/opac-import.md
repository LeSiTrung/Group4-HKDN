# Nhập metadata danh mục OPAC

Tích hợp thực tế03/11: backup riêng trước nhập;22.395thêm mới,1nguồn đã có giữ nguyên,5quarantine. Tổng catalog27.964; lặp nhập0/skipped22.396. Tất cả dòng cũ và số lượng bảng riêng tư giữ nguyên, SQLite quick_check đạt.466testbackend/45testfrontend/build và14kiểm tra API/model thật đạt. UI tìmPython trả9biểu ghi có nguồn. Không nhập thẳng5hàng quá giới hạn, không cắt từ khóa.

Chỉ mục sách ngữ nghĩa đang được chuẩn bị riêng trênCPU. Để tra cứu không chờ đợt embedding lớn, APIcục bộ hiện tạm tắt vector theo biến môi trường tiến trình, vẫn giữ keyword/FAQvàOllama. Không sửa.env. Supervisor tạm `tmp/supervise-opac-app-20261103.ps1` đọc kết quả index27964vàreadytrước khi chuyển APIcủa chính nó sang vector; thao tác chuyển sau hoàn tất vẫn cần kiểm chứng. Trạng thái ở `tmp/opac-app-process.json`, `tmp/opac-index.stdout.log`, `tmp/opac-index.stderr.log`; xem thêm lỗi supervisor nếu có. Không mở đồng thời hai process vào cùng localQdrant. Hệ thống không được ghi nhận production-readytừ việc nhập dữ liệu này.

`scripts/import_opac.py` đưa metadata trên thẻ kết quả công khai vào catalog sẵn có, không chờ toàn bộ MARC và không thay schema/dependency. Nguồn là `catalog-listings.jsonl` cùng `catalog-listings-manifest.json` trong vùng runtime. Bộ đang kiểm chứng có22.401ID,18.721.845byte, SHA-256 `99b543d717c846b6bebab9c5d37087df9c563419f5ad164ad038f0b21f53752a`.

## Kiểm tra trước khi ghi

```powershell
backend/.venv/Scripts/python scripts/import_opac.py backend/runtime/opac-public-20261101/catalog-listings.jsonl --publish
```

Mặc định chỉ staging: không tạo database, không ghi dữ liệu. Kiểm tra toàn bộ checksum, byte/count manifest, giới hạn64MiB/tệp,64KiB/dòng, manifest16KiB và tối đa100.000dòng; kiểm tra ID ASCII, URL OPAC chính xác, ngày có timezone/không ở tương lai, nhóm nguồn và cấu trúc fields. Bộ bị sửa, sai nguồn, trùng ID, sai count hoặc lỗi cấu trúc bất kỳ dòng nào làm dừng cả lượt trước khi mở database.

Các bản ghi hợp lệ về cấu trúc nhưng vượt giới hạn trường của `BookInput` được đưa vào `rejected` trong báo cáo, không cắt cụt dữ liệu. JSONL gốc vẫn giữ mọi trường và nguyên nội dung để xử lý riêng. Dry-run22.401dòng chấp nhận22.396, loại5ID do từ khóa quá1.000ký tự:18560,20921,24199,9566,13971. CLI trả mã1khi có quarantine để người chạy thấy phần chưa được nhập; không có nghĩa các dòng khác bị hỏng.

## Áp dụng sau backup

Sao lưu SQLite bằng công cụ backup hiện có trước khi ghi. Chọn đúng database bằng `DATA_DIR` tuyệt đối nếu không dùng runtime mặc định. Sau khi xem báo cáo:

```powershell
backend/.venv/Scripts/python scripts/import_opac.py backend/runtime/opac-public-20261101/catalog-listings.jsonl --publish --apply
```

`--apply` nhập các dòng đã qua staging trong một transaction; lỗi ghi làm rollback toàn bộ transaction. `--publish` chỉ công bố những dòng được thêm mới, mặc định không công bố. Lặp lại bỏ qua mọi `source_url` đã có, giữ nguyên sửa đổi/trạng thái của quản trị, không cập nhật đè dữ liệu DSpace hoặc bản ghi OPAC cũ. Audit ghi `book.opac_import`. Báo cáo mặc định là `opac-import-report.json`; không dùng đường dẫn trùng pack/manifest/database hoặc các tệpSQLite đi kèm`-wal/-shm/-journal`. Không chạy đồng thời hai lượt nhập.

## Ánh xạ và giới hạn

- Giữ nhan đề và tác giả theo nguồn. Ngày rà soát lấy từ `fetched_at` quy đổi múi giờ Việt Nam, không đổi thành ngày import.
- Năm chỉ điền khi chuỗi xuất bản có đúng một năm4chữ số; nhiều năm hoặc thiếu năm để trống. Thông tin xuất bản, dạng tài liệu và DDC được giữ trong mô tả.
- Từ khóa giữ nguyên trong `subjects`. Không lấy ký hiệu bản sách làm lời khẳng định còn sách/vị trí hiện tại; không tự tạo ISBN, tóm tắt hoặc giá/phí.
- Nhóm32và11-7 là `digital`. Các nhóm khác dùng bucket kỹ thuật `books` hiện có, bao gồm CD/video/tạp chí/luận văn; dạng tài liệu thực vẫn nằm trong mô tả nguồn. Không coi mọi dòng của bucket này là sách in.
- Không gộp OPAC và DSpace theo tên gần giống: hai nguồn giữ URL và provenance riêng. Có thể có các ấn bản/tài liệu trùng tên; không suy ra một ID là một bản sách đang rỗi.

Đây là metadata trên danh sách, chưa phải đầy đủ MARC hoặc toàn văn. Collector MARC chạy độc lập và không bị importer dừng. Dữ liệu nguồn vẫn là nội dung không đáng tin cậy về chỉ dẫn; không thực thi văn bản trong metadata như system prompt. Import không huấn luyện model, không tự đồng bộ bản rút khỏi nguồn, không nghiệm thu chính sách hoặc giao dịch thư viện.

## Kiểm chứng

```powershell
backend/.venv/Scripts/python -m pytest tests/test_opac_catalog.py tests/test_dspace_catalog.py -q
```

Các test kiểm tra mapping/nhóm điện tử/ngày Việt Nam/năm mơ hồ, nguồn giả, ID không hợp lệ, thời gian/cấu trúc sai, integrity/count/ID trùng, quarantine không cắt dữ liệu, dry-run không tạo database, chặn pack hỏng trước apply, idempotence/giữ sửa đổi và rollback. Việc nhập vào database đang phục vụ và kiểm chứng API/UI cần được ghi nhận riêng sau backup.
