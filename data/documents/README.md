# Tài liệu thư viện
Đặt bản sao tài liệu được phép dùng để thử nghiệm RAG tại đây. Ghi rõ nguồn và phiên bản trong tài liệu dự án.

`lic-source-manifest-2026-10-31.json` ghi phạm vi thu thập32 trang ứng viên,30 trang có văn bản,2 trang rỗng, URL/hash và các loại nội dung bị loại. Tài liệu hướng dẫn LIC33 trang đã đọc trang12 và kiểm tra ảnh lịch phục vụ; manifest lưu hash PDF, không đưa bản PDF lớn hay tài khoản mẫu vào Git. Bản chụp thô nằm trong `tmp/library-sources-2026-10-31` trên máy thu thập, không tự nhập vào RAG. Phần FAQ được tuyển chọn nằm trong `data/faq/public-library-2026-10-31.json`.
# Expanded public-source review, 1 November 2026

The exhaustive in-scope LIC HTML frontier is now staged through `scripts/collect_lic.py`:100 real sitemap page locations and141 outcomes after navigation. The old349loc count included249 image locations. Hash-checked text and links stay in ignored `backend/runtime/lic-public`;30 unique relevant candidates require manual review and are not auto-published. See `docs/lic-collection.md` and its evidence for exclusions, duplicates and actual coverage limits.

The guide linked from LIC's orientation page at `wp-content/uploads/2024/11/1.HD-su-dung-thu-vien-va-khai-thac-hieu-qua-cac-CSDL-tai-nguyen-thong-tin-thu-vien.pdf` was separately downloaded within a16MiB operator-only bound:7,486,705 bytes,33 pages, SHA256 `a2e1bfcb91744de396dbcc65e954583b6e684e5209d9853b73a0c0bfed89a6cc`. Page12 was rendered and visually read, plus text extraction. Its hours differ from the2022 guide; both remain unconfirmed references. The application crawler's1MiB limit is unchanged. Raw PDF/extracted text are not committed or treated as model instructions.

Current OPAC browser counters and robots/access evidence are in `docs/opac-access-2026-11-01.md`. They do not establish a deduplicated export, copies available, or permission to acquire full text. No OPAC bulk collection is claimed.
