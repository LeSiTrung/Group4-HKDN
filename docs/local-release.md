# Gói chạy và triển khai

Đợt kiểm thử biên ngày 03/11/2026 dùng image `uth-library:2026-11-03-edge` và dữ liệu riêng. Image `uth-library:2026-11-03` bên dưới là mốc trước của cùng ngày. [Kết quả kiểm thử biên](validation/2026-11-03-edge-cases.json)

MARC hiện có retry cho lỗi transport của GET đọc metadata: tối đa3lượt, chờ30/60giây và vẫn qua clock chung. HTTP401/403/429/5xx, POST/giao dịch, URL/DNS và lỗi giới hạn phản hồi không được thử lại. Retry không thay thế checkpoint hoặc xác nhận quyền thu thập.

Ngày03/11/2026, nhóm xác nhận chưa có máy chủ/tên miền. Gói hiện tại phục vụ kiểm thử cục bộ và chuẩn bị triển khai; không mở cổng ra Internet hoặc thay đổi máy production.

## Gói đã tạo

- Docker image: `uth-library:2026-11-03`, chứa backend, frontend build, FAQ khởi tạo, công cụ restore và collector OPAC.
- Image không chứa `.env`, tài khoản, lịch sử, database thực, snapshot, model weights hoặc giấy phép toàn văn. Chuyển dữ liệu bằng backup/restore đã kiểm tra, không đóng gói thư mục runtime đang mở.
- Chạy UID10001, một worker; cấu hình [compose.yaml](../compose.yaml) giữ API/Ollama trong mạng nội bộ và đặt Caddy ở biên HTTPS. App chờ Ollama healthy; Ollama dùng tag0.40.13. Model được tải rõ ràng bằng lệnh vận hành, không tự phát sinh phí API.
- `/ready` yêu cầu ít nhất một mục tri thức đã công bố và còn hiệu lực. Với Ollama, endpoint cũng kiểm tra model đã cấu hình có sẵn. Endpoint trả `200` hoặc `503` kèm cờ kiểm tra. `LLM_PROVIDER=none` cho phép chạy FAQ độc lập. Kiểm tra riêng chất lượng câu trả lời, chỉ mục vector và tích hợp ngoài khi nghiệm thu.
- `/health` vẫn cung cấp trạng thái vận hành. Nhật ký/chẩn đoán quản trị được giữ để xử lý lỗi; giao diện bạn đọc không hiển thị phiên bản, nhãn FAQ/RAG hay định tuyến AI nội bộ.

## Dùng tại máy phát triển

Ứng dụng chính vẫn chạy tại `http://127.0.0.1:8000`. Docker Desktop Engine được khởi động lại và build Linux đã thành công. Các container kiểm thử dùng dữ liệu riêng, kết nối Ollama của host và chỉ bind loopback; không sao chép tài khoản hay lịch sử thật.

Để tái tạo image từ repository:

```powershell
# Nếu Docker credential helper chưa có trong PATH của terminal này:
$dockerBin = Split-Path -Parent (Get-Command docker.exe).Source
$env:PATH = $dockerBin + ';' + $env:PATH
docker build -t uth-library:2026-11-03 .
```

Không đổi Docker credential configuration. Hướng dẫn native: `run.ps1`. Các bước tạo quản trị, backup/restore, tải model và triển khai domain nằm trong [operations.md](operations.md). Chỉ chạy sau khi thay hostname và bảo đảm DNS/cổng/quyền máy đích.

## Thu thập MARC tiếp tục

Hồ sơ chi tiết đang tiếp tục từ **inventory cố định22.401ID**. Ngày03/11, mở lại danh mục trực tiếp phát hiện inventory khác snapshot cũ và dừng; snapshot cũ được giữ, không ghi đè hoặc tự nhập inventory mới.

Chạy tại thư mục repository, chỉ khi chưa có worker cùng output:

```powershell
backend/.venv/Scripts/python scripts/collect_opac.py --output backend/runtime/opac-public-20261101 --details-from-pack backend/runtime/opac-public-20261101/catalog-listings.jsonl --acknowledge-robots-disallow
```

`stage_pack` kiểm tra hash/bytes/count/schema toàn gói trước HTTP; cả5ID có trường quá dài cho catalog vẫn được lấy MARC. Các MARC hợp lệ có sẵn được tái sử dụng. Chế độ này không refresh listing, không khẳng định22.401là tổng hiện tại của website và không tải sách toàn văn. `frozen_inventory` trong manifest ghi hash/count/phạm vi; `complete` chỉ nói về bộ ID đó.

API và collector dùng chung `DATA_DIR/opac-pacing.sqlite3`, cách lượt tối thiểu10giây hoặc khoảng cao hơn đã quan sát từ robots. Chờ nhường lượt không giữ transaction. API chờ hữu hạn20giây rồi trả trạng thái chưa xác nhận; collector chờ slot và nhường cho cửa sổ ưu tiên của bạn đọc đang chờ. Nhiều bạn đọc đồng thời vẫn có thể hết thời gian chờ. Các lỗi pacing/disk/HTTP từ chối dừng hoặc trả unknown, không gửi request vượt giới hạn. Thời gian chờ slot được tách khỏi ngân sách đọc phản hồi nguồn.

Đây là điều phối trên cùng filesystem/volume và cùng DATA_DIR. Hai máy hoặc hai volume độc lập không có giới hạn chung; không chạy đồng thời các nguồn OPAC như vậy. Collector giữ khóa output suốt lượt chạy và hệ điều hành nhả khóa khi process kết thúc. Không xóa file khóa hoặc clock để chạy nhanh hơn.

MARC ở staging, chưa tự sửa các thông tin đã biên tập trong catalog. Đồng bộ/enrichment vào dữ liệu phục vụ cần kiểm tra field mapping, provenance và thay đổi metadata riêng. Ở10giây/lượt, khoảng22nghìn hồ sơ còn lại cần tối thiểu khoảng61giờ không gián đoạn; tra cứu theo yêu cầu, lỗi mạng và thời gian phản hồi làm lâu hơn. Tiến độ chính xác phải đọc snapshot/process hiện tại.

## Kiểm chứng và bước còn lại

Bằng chứng mới: [validation/2026-11-03-production-preparation.json](validation/2026-11-03-production-preparation.json). Test trong Linux đã xác nhận UID10001, chat có nguồn, sinh bằng Qwen thực, readiness200/thiếu-model503, điều phối clock qua hai process và CLI collector được đóng gói.

Trước khi công khai cần máy đích/domain, DNS/ACME, backup và diễn tập restore tại đích, tải đồng thời/cold-vector latency, dữ liệu/chính sách được thư viện xác nhận và nghiệm thu bạn đọc. Test Linux dùng Ollama của host; toàn bộ Compose với Ollama volume riêng vẫn cần chạy ở máy đích. Bỏ nhãn debug không thay thế các kiểm tra này.
