# Hình minh họa hướng dẫn OPAC trong chat

Chat hiển thị hình từ các trang đã rà soát của `HDSD_TRACUU_OPAC.v1.1.pdf`: trang3 tìm kiếm chung, trang4 chọn loại tài liệu, trang6 tìm theo nhan đề/tác giả. Hình nằm dưới câu trả lời, có mô tả thay thế, chú thích, nút phóng to, liên kết mở ảnh kích thước gốc và liên kết tới đúng trang PDF.

Ảnh chỉ xuất hiện khi câu trả lời FAQ thành công có nguồn khớp chính xác với một trong ba trang này. Không gắn ảnh vào yêu cầu tìm danh mục, câu cần làm rõ, người dùng, nguồn giả mạo hoặc trang khác. Lịch sử sử dụng lại URL nguồn đã lưu để hiển thị hình; không thêm cột hoặc sửa dữ liệu hội thoại. Nếu ảnh lỗi, nội dung chữ và nguồn PDF vẫn được giữ.

`GuideImage.jsx` chọn ảnh WebP đóng gói cùng frontend từ URL nguồn đã duyệt. Ảnh tải lười, có kích thước khai báo để hạn chế dịch chuyển bố cục. Vite thêm hash tên file. Máy chủ đăng ký `image/webp` khi phục vụ frontend để liên kết ảnh gốc mở được cả trên Windows. Bản build mới đang chạy tại cổng 8000.

## Nguồn và tái tạo

- URL: https://opacthuvien.ut.edu.vn/opac/Upload/HDSD_TRACUU_OPAC.v1.1.pdf
- Bản đầu vào do người dùng cung cấp: `D:/Download/HDSD_TRACUU_OPAC.v1.1.pdf`,1821058bytes.
- SHA256: `3eb7a16a5e30e61bb35a581aaa228ad32b3914a00c4ed52b1cf083b028953f56`.
- Manifest: `frontend/src/assets/opac-guide/provenance.json`, gồm trang, kích thước, dung lượng và hash từng ảnh. Ba ảnh có tổng435320bytes; chỉ ảnh được hiển thị mới cần tải.
- Đã render toàn bộ trang3/4/6 bằng Poppler để đối chiếu. Bản cuối dùng PDFium/Pillow từ runtime có sẵn, giữ nguyên trang, cạnh dài1600pixel, RGB, WebPquality92/method6. Không tạo thêm mũi tên hoặc nội dung minh họa bằng AI. Không đóng gói các trang chứa ví dụ thông tin đăng nhập.

Tái tạo với `pypdfium2` và Pillow trong môi trường công cụ riêng; ứng dụng chạy không cần cài các thư viện render:

```python
import pypdfium2 as pdfium

with pdfium.PdfDocument('HDSD_TRACUU_OPAC.v1.1.pdf') as pdf:
    for number in (3, 4, 6):
        page = pdf[number - 1]
        image = page.render(scale=1600 / max(page.get_size())).to_pil().convert('RGB')
        image.save(f'opac-page-{number}.webp', format='WEBP', quality=92, method=6)
        page.close()
```

Khi thay phiên bản PDF, rà soát lại hình và nguồn, cập nhật manifest và mapping kích thước/URL trong component. Không tự suy ra ảnh cũ đại diện cho giao diện, số lượng hoặc quyền truy cập hiện tại. Chú thích này cũng xuất hiện trong sản phẩm.

## Kiểm chứng

`frontend/src/guideImages.test.jsx` kiểm ảnh đúng nguồn, mở/đóng, mở ảnh gốc, fallback lỗi ảnh, nguồn trùng, các trạng thái không thích hợp, nguồn giả mạo, nút gợi ý thật và tải lịch sử. Có6ca ban đầu thất bại trước khi bổ sung ảnh; sau đó tái hiện và chặn khóa kế thừa `__proto__` trước khi chốt allowlist. Liên kết ảnh gốc cũng được kiểm thử thất bại trước khi thêm.

Đã kiểm tra trực tiếp trình duyệt: cả3ảnh tải được, hộp ảnh lớn/đóng bằng Escape, màn hình390×844 không tràn ngang. Viewport kiểm thử được reset. Bằng chứng cuối: `docs/validation/2026-11-03-guide-images.json`; ảnh chụp phiên thử nghiệm ở `tmp/guide-images-desktop.jpg` và `tmp/guide-images-mobile.jpg`.

Đây là ảnh minh họa theo bản PDF đã cung cấp, không phải ảnh chụp OPAC hiện tại. Website trả403 khi công cụ thử tải screenshot PDF; không thực hiện vượt kiểm soát truy cập. Không thay đổi RAG/LLM, dữ liệu người dùng hoặc tiến trình MARC cho tính năng này.
