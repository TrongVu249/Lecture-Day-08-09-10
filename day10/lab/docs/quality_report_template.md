# Quality report — Lab Day 10 (nhóm)

**run_id:** `2026-06-10T07-01Z`  
**Ngày:** `2026-06-10`

---

## 1. Tóm tắt số liệu

| Chỉ số | Trước (Inject Bad) | Sau (Fix) | Ghi chú |
|--------|--------------------|-----------|---------|
| raw_records | 247 | 247 | Giống nhau vì cùng tệp đầu vào raw CSV. |
| cleaned_records | 34 | 34 | Giống nhau vì rule fix refund window chỉ thay đổi nội dung chữ, không loại bỏ bản ghi. |
| quarantine_records | 213 | 213 | Giống nhau do các bộ lọc quarantine hoạt động độc lập với rule fix refund window. |
| Expectation halt? | Có (Halt) | Không | Lần đầu bị halt ở `refund_no_stale_14d_window` nhưng được bỏ qua nhờ `--skip-validate`. Lần sau vượt qua tất cả expectations sạch sẽ. |

---

## 2. Before / after retrieval (bắt buộc)

> Đường dẫn tới các file kết quả:
> - Trước: [after_inject_bad.csv](file:///d:/Project/Vin_AI/Lab%2010/Lecture-Day-08-09-10/day10/lab/artifacts/eval/after_inject_bad.csv)
> - Sau: [after_fix_eval.csv](file:///d:/Project/Vin_AI/Lab%2010/Lecture-Day-08-09-10/day10/lab/artifacts/eval/after_fix_eval.csv)

**Câu hỏi then chốt:** refund window (`q_refund_window`)  
**Trước:**
- `top1_doc_id`: `policy_refund_v4`
- `top1_preview`: `"Ngoại lệ không được hoàn tiền: sản phẩm thuộc danh mục hàng kỹ thuật số (license key, subscription). Đơn hàng đã áp dụng mã giảm giá Flash Sale cũng không được hoàn. (Chính sách ho"`
- `contains_expected`: `yes`
- `hits_forbidden`: `no`
- `top1_doc_expected`: `yes`

**Sau:**
- `top1_doc_id`: `policy_refund_v4`
- `top1_preview`: `"Ngoại lệ không được hoàn tiền: sản phẩm thuộc danh mục hàng kỹ thuật số (license key, subscription). Đơn hàng đã áp dụng mã giảm giá Flash Sale cũng không được hoàn. (Chính sách ho"`
- `contains_expected`: `yes`
- `hits_forbidden`: `no`
- `top1_doc_expected`: `yes`

*Nhận xét:* Đối với `q_refund_window`, top-1 document trả về đều là ngoại lệ hoàn tiền, tuy nhiên ở câu hỏi liên quan `q_refund_exception_digital` dưới đây, sự thay đổi được thể hiện rõ ràng:

**Ngoại lệ hoàn tiền (`q_refund_exception_digital`):**
- **Trước (Inject Bad):** `Yêu cầu hoàn tiền được chấp nhận trong vòng 14 ngày làm việc kể từ xác nhận đơn. (Chính sách hoàn tiền policy refund v4)` -> Trả về thông tin cũ lỗi thời (14 ngày).
- **Sau (Fix):** `Yêu cầu hoàn tiền được chấp nhận trong vòng 7 ngày làm việc kể từ xác nhận đơn. [cleaned: stale_refund_window] (Chính sách hoàn tiền policy refund v4)` -> Đã được làm sạch thành 7 ngày, đảm bảo tính đúng đắn cho câu trả lời của agent.

**Merit (khuyến nghị):** versioning HR — `q_hr_annual_leave_under3` (`contains_expected`, `hits_forbidden`, cột `top1_doc_expected`)

**Trước:**
- `top1_doc_id`: `hr_leave_policy`
- `top1_preview`: `Nhân viên dưới 3 năm kinh nghiệm được 12 ngày phép năm theo chính sách 2026. (Chính sách nghỉ phép HR leave policy 2026)`
- `contains_expected`: `yes`
- `hits_forbidden`: `no`
- `top1_doc_expected`: `yes`

**Sau:**
- `top1_doc_id`: `hr_leave_policy`
- `top1_preview`: `Nhân viên dưới 3 năm kinh nghiệm được 12 ngày phép năm theo chính sách 2026. (Chính sách nghỉ phép HR leave policy 2026)`
- `contains_expected`: `yes`
- `hits_forbidden`: `no`
- `top1_doc_expected`: `yes`

---

## 3. Freshness & monitor

- Kết quả `freshness_check` của run gần nhất: **FAIL**
- SLA được chọn: `24.0 giờ` (thiết lập qua `.env` `FRESHNESS_SLA_HOURS=24`).
- Giải thích:
  - Trường `latest_exported_at` của dữ liệu đã làm sạch là `2026-04-10T00:00:00`.
  - So với thời điểm chạy pipeline hiện tại (`2026-06-10`), khoảng thời gian trễ (age) lên đến `1471.03 giờ`, vượt quá mức SLA 24 giờ cho phép. Do đó, hệ thống giám sát đã cảnh báo trạng thái **FAIL**.

---

## 4. Corruption inject (Sprint 3)

- **Phương pháp mô phỏng tiêm lỗi:** Chạy pipeline với tham số `--no-refund-fix` để tắt rule sửa đổi văn bản hoàn tiền từ `14 ngày` thành `7 ngày`. Cùng với đó sử dụng tham số `--skip-validate` để tránh pipeline bị dừng (HALT) bởi bộ kiểm tra chất lượng dữ liệu (Expectation Suite) khi có bản ghi vi phạm.
- **Cách phát hiện:**
  - Expectation Suite phát hiện lỗi tại expectation `refund_no_stale_14d_window` (trả về trạng thái `FAIL (halt)`).
  - Đánh giá chất lượng truy vấn qua `eval_retrieval.py` cho thấy các câu truy vấn lấy ra câu trả lời chứa thông tin stale (`14 ngày làm việc` thay vì `7 ngày làm việc` được quy định trong chính sách 2026).

---

## 5. Hạn chế & việc chưa làm

- Dữ liệu demo có thông tin ngày tháng xuất bản cũ (`2026-04-10`) nên freshness check luôn luôn báo FAIL nếu đặt SLA 24 giờ trong môi trường production thực tế. Cần có cơ chế giả lập thời gian hoặc cập nhật thời gian export động khi ingest dữ liệu mới.
- Chưa tích hợp một công cụ visualize chuyên nghiệp cho trước/sau (ví dụ: dashboard so sánh tự động hiển thị side-by-side).
