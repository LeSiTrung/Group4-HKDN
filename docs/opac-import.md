# Nhập metadata OPAC và MARC

Dùng bộ dữ liệu đã xác minh gồm `catalog-listings.jsonl`, `catalog-listings-manifest.json` và thư mục `records/` chứa các ảnh chụp MARC. Người mới có thể dùng ảnh chụp danh mục công khai do nhóm cấp theo [hướng dẫn cài đặt](getting-started.md).

## Kiểm tra bộ dữ liệu và sao lưu

Các lệnh dưới đây chạy từ thư mục gốc repository trên Windows. Đặt đường dẫn tới bộ dữ liệu được nhóm cung cấp. Trên Linux thay đường dẫn Python bằng `backend/.venv/bin/python`.

```powershell
$python = './backend/.venv/Scripts/python.exe'
$collection = 'backend/runtime/opac-public-20261101'
& $python scripts/import_opac.py "$collection/catalog-listings.jsonl"
& $python -m scripts.enrich_opac_marc $collection
```

Lệnh đầu xác minh checksum, số dòng, ID, URL, ngày và giới hạn trường. Lệnh thứ hai báo số ảnh chụp MARC hợp lệ có nội dung để nhập, thiếu, lỗi hoặc không có trường phù hợp. Đối chiếu hai báo cáo trước khi ghi. Từ khóa trên danh sách dài quá 1.000 ký tự được giữ đến hết từ khóa hoàn chỉnh trong giới hạn. Tệp nguồn giữ đủ dữ liệu.

Dừng API trước khi nhập để chỉ mục sách được đồng bộ lúc khởi động lại. Sao lưu SQLite theo [hướng dẫn vận hành](operations.md#backup). Nếu dùng `DATA_DIR` riêng, chọn đường dẫn tuyệt đối phù hợp cho cả lệnh backup, importer và tệp SQLite dưới đây.

## Nhập và xác minh

```powershell
& $python scripts/import_opac.py "$collection/catalog-listings.jsonl" --apply --publish
if ($LASTEXITCODE -ne 0) { throw 'Kiểm tra báo cáo nhập OPAC trước khi tiếp tục.' }
& $python -m scripts.enrich_opac_marc $collection --apply backend/runtime/library.sqlite3
```

Importer chỉ thêm URL mới và giữ thông tin biên tập đã có. Bước MARC chỉ ghi chủ đề, tóm tắt và đối tượng đọc từ các trường được hỗ trợ cho biểu ghi công khai có cùng URL nguồn. Chạy lại cùng ảnh chụp không cập nhật đè dữ liệu MARC. Giữ ngày đối chiếu của nguồn.

Khởi động lại ứng dụng. Trang chi tiết tài liệu hiển thị các trường MARC đã nhập. Khi bật vector, kiểm tra `capabilities.vectors.namespaces.books` tại `/health`. Tra cứu từ khóa dùng được trong lúc đợi chỉ mục. Xem [kết quả tích hợp](validation/2026-11-15-marc-integration.json) để đối chiếu phạm vi đã kiểm tra.

Dữ liệu danh mục thiếu MARC vẫn tra cứu được theo nhan đề và tác giả đã ghi. Số bản rỗi và quyền mượn cần kiểm tra qua OPAC. Nhập dữ liệu này không cung cấp toàn văn tài liệu hoặc giao dịch mượn.
