# Thu thập metadata OPAC công khai

Kiểm tra06/11/2026: trước resume có12.425 snapshot MARC hợp lệ và1.125 trang
listing, cùng frozen pack22.401ID không đổi hash. Sách in trong frozen pack đủ
10.457 MARC, nhưng listing trực tiếp lúc19:44ICT hiện10.460 (tăng ròng3, chưa
xác định các ID thay đổi); tài liệu số vẫn7.487, có160 MARC trước resume.
Không trộn listing mới vào pack cũ. Đã tiếp tục supervisor hiện có sau khi xác
nhận không còn worker/khóa;35 trang trống từ lượt trước là phần thiếu trước resume,
chỉ được tính thành công khi lưu được snapshot MARC hợp lệ sau kiểm tra lại.
Lượt quét sau resume19:53–19:54ICT xác minh12.435 MARC (thêm10), còn9.966ID thiếu;
bốn ID đã hoãn14628/14886/15215/18480 phục hồi,31ID cũ vẫn thiếu. Toàn bộ12.425
MARC và1.125trang cũ, pack và manifest của pack giữ nguyên byte/hash. Một worker
logic22452/interpreter29296 và supervisor26704 tiếp tục, khóa output đang được giữ.
Số sau resume, bằng chứng hash/process/khóa và48 kiểm thử liên quan nằm ở
[validation/2026-11-06-marc-checkpoint.json](validation/2026-11-06-marc-checkpoint.json).
Tổng/seed khớp không chứng minh toàn bộ tập ID hiện tại; sáu route còn lại mới
được đối soát với snapshot cũ. Không tuyên bố harvest hay dự án hoàn tất.

Ngày 05/11/2026, ID23229 trả đúng ID nhưng phần biên mục trống. Có thể dùng
`--defer-missing-marc` cùng `--details-from-pack` để ghi riêng các trang thiếu
MARC rồi tiếp tục ID khác. Manifest lưu `deferred_details` với URL, ngày kiểm
tra và hash phản hồi; không tạo snapshot MARC rỗng. Khi còn mục thiếu, lượt thu
thập kết thúc với `complete=false`, `phase=details_deferred`. Chạy lại sẽ kiểm
tra các mục đó lần nữa. Không có cờ này vẫn dừng như trước; sai ID, HTTP từ chối
và lỗi mạng không được bỏ qua. Không chạy worker trùng chỉ để kiểm tra lại.

Cập nhật03/11/2026:319MARC cũ đã kiểm tra hash/schema; lần mở lại toàn bộ danh mục phát hiện seed khác snapshot và dừng `inventory_changed_use_new_output_directory`. Đã bổ sung `--details-from-pack` để tiếp tục các MARC còn thiếu của inventory đã xác minh22.401ID mà không ghi đè/refresh listing. Gói được kiểm tra toàn bộ trước HTTP, gồm cả5ID bị cách ly khỏi catalog vì giới hạn trường. SnapshotMARC cũ được giữ. ClockSQLite chung với API và khóa output thay giới hạn chỉ theo process ở các đoạn lịch sử; [lệnh chạy và phạm vi](local-release.md). Không coi việc hoàn thành frozen pack là tổng website hiện tại.

Ngày 01/11/2026, truy cập HTTPS trực tiếp từ máy phát triển tới trang chủ, danh mục sách và chi tiết OPAC đã trả HTTP 200 trở lại. Công cụ đọc web bên ngoài vẫn gặp 403; đây là hai đường truy cập khác nhau. Các ghi nhận 403/522 trước đó trong `opac-access-2026-11-01.md` là lịch sử, không mô tả trạng thái hiện tại của đường truy cập từ máy này.

`robots.txt` vẫn ghi `Disallow: /` và `Crawl-delay: 10`. Collector mặc định dừng trước danh mục nếu không được robots cho phép. Theo yêu cầu rõ ràng của người vận hành về thu thập metadata công khai, lần chạy này dùng cờ xác nhận dưới đây; cờ được ghi vào manifest và không thay đổi crawler trong ứng dụng. Nó không mở đăng nhập, vượt Cloudflare, giả danh trình duyệt hoặc cấp quyền tải sách toàn văn. Mọi 401/403/429/5xx dừng lượt chạy; không tự thử đổi danh tính hay tiếp tục khi bị từ chối.

```powershell
backend/.venv/Scripts/python scripts/collect_opac.py --output backend/runtime/opac-public-20261101 --acknowledge-robots-disallow
```

Không chạy hai collector cùng thư mục hoặc hai lượt OPAC đồng thời. Một lượt dùng một luồng, khoảng cách tối thiểu 10 giây giữa request trên toàn bộ tám phiên danh mục. Các phiên chỉ giữ cookie/viewstate ẩn danh trong bộ nhớ. Phân trang POST thực hiện đúng nút công khai `raiseShowRecord` và `hidCurrentPage` trong `js/OShow.js`; không phải giao dịch mượn, lưu danh sách hoặc đăng nhập. Helper mạng giữ ghim DNS/IP công khai, HTTPS/TLS, giới hạn phản hồi 1 MiB và từ chối redirect trước khi theo sang URL khác.

## Nội dung và đối soát

- Tám lối duyệt công khai được lấy luân phiên: sáu nhóm Video, CD-ROM, Báo/tạp chí, Luận văn, Tài liệu số, Sách truyền thống; thêm Khóa luận (DicID10/Browse36) và Báo/tạp chí điện tử (DicID11/Browse7) từ các điều khiển công khai trên trang chủ. Mỗi nhóm có tổng, khoảng thứ tự, trang và tập ID riêng. Không cộng các tổng để khẳng định số tài liệu duy nhất.
- `pages/<category>-<page>.json` lưu nhan đề, ID nguồn và toàn bộ trường metadata hiển thị trong thẻ kết quả. Không lưu HTML, viewstate, cookie hoặc thông tin tài khoản.
- Sau khi lấy xong danh mục, `records/<id>.json` lưu các trường MARC công khai đến 8xx, giữ trường lặp và kiểm tra `hidItemID` trùng ID yêu cầu. Loại các trường nội bộ 9xx; không tải liên kết toàn văn, ảnh bìa, dữ liệu người mượn hoặc thực hiện đặt mượn.
- Mỗi snapshot có URL, thời điểm lấy và SHA-256. Resume kiểm tra hash, cấu trúc, ID, nguồn, khoảng mục và số bản ghi; cache hỏng được tải lại. Khi tổng hoặc trang đầu thay đổi, dừng với `inventory_changed_use_new_output_directory` để tránh trộn hai inventory. Tạo thư mục mới cho lần refresh; không ghi đè bộ đang dùng.
- Cùng ID thuộc nhiều nhóm được gộp khi lấy chi tiết, nhưng thành viên từng nhóm được giữ nguyên. ID lặp trong cùng nhóm, sai trang, sai tổng hoặc thiếu trường đều làm lượt chạy dừng. Chỉ đánh dấu nhóm hoàn tất khi số ID duy nhất đúng tổng của nhóm.
- `manifest.json` ghi `phase`, `listing_records`, `detail_records`, `categories`, `blocked`, `complete`. `complete` áp dụng cho những nhóm được chọn và mức `details_requested`; chỉ lượt mặc định đủ tám lối duyệt và chi tiết mới phản ánh toàn bộ metadata trong phạm vi này.

Đây là staging, chưa tự nhập vào database hoặc huấn luyện. Ký hiệu bản sách, giá bìa hoặc thông tin biên mục không phải cam kết còn sách, phí dịch vụ hay trạng thái thời gian thực. Tài liệu số OPAC vẫn khác nguồn DSpace; chưa có crosswalk để khẳng định hai danh mục trùng nhau.

## Tiếp tục và theo dõi

Chạy lại đúng lệnh trên để tiếp tục snapshot hợp lệ; không tự tải lại những trang đã hoàn thành. Mỗi lần khởi động vẫn mở lại trang đầu của từng nhóm để kiểm tra inventory và tạo phiên ẩn danh mới cho phân trang. Thêm `--listings-only` nếu chỉ cần metadata trên thẻ kết quả; `--max-pages 8` chỉ là smoke test giới hạn, không được coi là hoàn thành toàn bộ.

Trong giai đoạn mở lại seed, bộ đếm manifest chỉ phản ánh những nhóm đã kiểm tra ở lượt hiện tại nên có thể tạm nhỏ hơn tổng ID trong các snapshot cũ. Snapshot cũ được giữ nguyên và được kiểm tra/nạp lại khi đi qua; đây không phải thao tác xóa dữ liệu. Số `unique_ids_in_stored_pages` trong bằng chứng tĩnh là tổng các snapshot đã kiểm chứng lúc ghi bằng chứng, khác counter tiến trình đang khởi động.

Một lần phân trang báo/tạp chí trả HTTP200 nhưng thiếu summary, làm lượt đầu dừng sau223ID. Truy vấn danh mục mới rồi mở lại trang2/3 trả đúng dữ liệu; chưa xác định nguyên nhân phía nguồn. Collector hiện chỉ với lỗi thiếu summary sẽ mở lại trang đầu một lần, yêu cầu seed hoàn toàn khớp rồi thử đúng trang cần lấy một lần. Thất bại tiếp thì dừng; không hồi phục theo cách này khi HTTP từ chối, sai ID hoặc sai khoảng mục. `session_refreshes` và hash của phản hồi lỗi được ghi vào manifest. Lượt tiếp theo đã đi qua trang lỗi; đây không phải bằng chứng phiên nhiều ngày luôn ổn định.

Trên Windows, trình đọc có thể tạm giữ manifest khiến atomic replace trảWinError5. Writer thử lại tối đa8lần, tổng thời gian chờ6,35giây; lỗi kéo dài vẫn được báo và tệp cũ giữ nguyên. Không xóa tệp đích hoặc ghi đè trực tiếp để né khóa. Có test giả lập lỗi tạm thời/vĩnh viễn và kiểm chứng bằng khóa chia sẻ Windows thật. Tránh giữ file checkpoint mở bằng công cụ khóa độc quyền.

```powershell
Get-Content backend/runtime/opac-public-20261101/manifest.json
Get-Content backend/runtime/opac-public-20261101/collector.stdout.log -Tail 10
Get-Content backend/runtime/opac-public-20261101/collector.stderr.log
```

Lượt nền ngày 01/11 được khởi động với cửa sổ ẩn; PID và thời điểm nằm trong `process.json` cùng thư mục. Kiểm tra PID còn thuộc đúng lệnh trước khi dừng bằng `Stop-Process`. Snapshot đã ghi được giữ để resume. Tắt máy, mất mạng, phiên nguồn hết hạn hoặc HTTP từ chối có thể dừng tiến trình; không có cam kết máy cá nhân chạy liên tục nhiều ngày.

Kiểm tra lúc20:46ICT phát hiện worker trước đã biến mất, checkpoint cuối20:30ICT có1.726ID/89trang, không có lỗi kết thúc. Đã xác minh lại snapshot và tiếp tục lúc20:48ICT qua supervisor ẩn được tạo bằng WMI, nằm ngoài chuỗi tiến trình terminal. `process.json` bổ sung supervisor PID; `exit-<timestamp>.json` hoặc `supervisor-error-<timestamp>.json` ghi kết thúc nếu supervisor quan sát được. Script tạm `tmp/supervise-opac-20261101.ps1` không tạo lịch chạy, dịch vụ hay thay cấu hình hệ thống. Đây là kiểm chứng khởi động và tiến độ, chưa chứng minh được nguyên nhân dừng trước đó hoặc độ bền nhiều ngày.

## Kiểm chứng hiện tại

Lần kiểm tra sau dừng ở4.138ID với lỗi định danh trên trang50: OPAC hiển thị số thứ tự1.000.thay cho1000. Parser đã hỗ trợ dấu chấm nhóm hàng nghìn và vẫn so sánh chính xác thứ tự mong đợi. Trang thật981–1.000đã đọc đủ20biểu ghi; có regression cho1.000/10.000/12.345và dạng sai. Lượt thu thập đã được tiếp tục, chưa khẳng định hoàn tất.

Đã kiểm tra thực tế sáu trang đầu, 103 ID khác nhau; danh mục sách truyền thống có 10.457 mục và POST trang 2 trả đúng thứ tự 21–40. Đã tải/kiểm tra MARC của một đại diện mỗi nhóm: ID5712/14146/13144/14639/22237/17832 có lần lượt17/10/23/12/17/13trường sau khi loại9xx. Đây là kiểm chứng cơ chế, chưa phải toàn bộ harvest. Lượt nền tiếp tục sau smoke test; số tiến độ tại một thời điểm nằm trong `docs/validation/2026-11-01-collection-resumed.json`, trạng thái mới nhất ở manifest runtime.

Tổng trên trang danh mục được kiểm tra trực tiếp là: sách10.457, tài liệu số7.487, luận văn3.259, báo/tạp chí823, CD-ROM371, video3. Hai tổng tài liệu số và luận văn khác bộ đếm trang chủ7.510 và3.260; chưa xác định nguyên nhân. Giữ nguyên hai loại bằng chứng, không lấy bộ đếm trang chủ làm số bản ghi đã tải, không suy ra những mục chênh lệch là công khai hoặc xác định được ID của chúng.

Hai lối bổ sung trả1biểu ghi Khóa luận (ID23325) và2biểu ghi báo/tạp chí điện tử (ID18560,15869). Nhóm thứ hai là biểu ghi tạp chí theo năm, không thể đồng nhất với nhãn670toàn văn trên trang chủ hoặc suy ra số file bài báo. Giữ nguồn và hội viên từng nhóm, không đếm trùng thành tài liệu mới.

MARC của đại diện bổ sung23325 và18560 đã được kiểm tra định danh, có16và83trường tương ứng. Điều tra giới hạn về số tạp chí và UI xuất danh sách ở [opac-serials.md](opac-serials.md); chưa chứng minh được export toàn bộ hoặc tìm ra ID riêng cho từng số tạp chí.

```powershell
backend/.venv/Scripts/python -m pytest tests/test_opac_collection.py tests/test_integrations.py -q
```

Kiểm thử gồm dữ liệu tiếng Việt, trường lặp, sai ID/trang, hash/schema cache, resume, đối soát tổng, robots mặc định, pacing, redirect và dừng khi bị từ chối. Chưa kiểm chứng hết vòng thu thập nhiều giờ/ngày; không đánh dấu `PROJECT COMPLETE` từ smoke test.
