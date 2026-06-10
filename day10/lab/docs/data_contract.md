# Data contract — Lab Day 10

> Bắt đầu từ `contracts/data_contract.yaml` — mở rộng và đồng bộ file này.

---

## 1. Nguồn dữ liệu (source map)

| Nguồn (doc_id) | Phương thức ingest | Failure mode chính | Metric / alert |
| :--- | :--- | :--- | :--- |
| **policy_refund_v4** | DB/API export (CSV) | Chứa thông tin hoàn tiền cũ (14 ngày thay vì 7 ngày), ngày tháng không chuẩn. | Hoạt động fix tự động; Halt nếu sau khi sạch vẫn còn lỗi 14 ngày (`refund_no_stale_14d_window`). |
| **sla_p1_2026** | DB/API export (CSV) | Thiếu thông tin SLA, ngày có định dạng không hợp lệ. | Check độ dài chunk tối thiểu (`chunk_min_length_8` - warn) và format ngày ISO (halt). |
| **it_helpdesk_faq** | DB/API export (CSV) | Các câu hỏi trùng lặp, thiếu thông tin text hoặc ngày bị rỗng. | Loại bỏ trùng lặp (`duplicate_chunk_text`); check text rỗng. |
| **hr_leave_policy** | DB/API export (CSV) | Nạp phiên bản cũ (2025 có ngày < 2026-01-01), chứa thông tin phép năm cũ (10 ngày phép). | Cách ly phiên bản cũ (`stale_hr_policy_effective_date`); Halt nếu chứa text 10 ngày phép (`hr_leave_no_stale_10d_annual`). |
| **access_control_sop** | DB/API export (CSV) | Tài liệu mới chưa được khai báo hoặc bị thiếu trong allowlist. | Cách ly lỗi `unknown_doc_id`. Sau khi cấu hình, chạy qua bộ lọc chuẩn để nạp vào vector store. |

---

## 2. Schema cleaned

| Cột | Kiểu | Bắt buộc | Ghi chú |
| :--- | :--- | :--- | :--- |
| **chunk_id** | string | Có | Khóa định danh duy nhất của chunk sau làm sạch (được hash từ doc_id + text + seq). |
| **doc_id** | string | Có | Mã logic xác định tài liệu nguồn (ví dụ: `access_control_sop`). |
| **chunk_text** | string | Có | Nội dung văn bản của chunk (phải có độ dài tối thiểu là 8 ký tự). |
| **effective_date** | date | Có | Ngày hiệu lực của chính sách, chuẩn hóa sang ISO YYYY-MM-DD. |
| **exported_at** | datetime | Có | Thời điểm xuất dữ liệu từ hệ thống nguồn. |

---

## 3. Quy tắc quarantine vs drop

- **Quarantine (Cách ly)**: 
  - Các bản ghi có `doc_id` không nằm trong allowlist (`unknown_doc_id`).
  - Bản ghi có `effective_date` trống hoặc sai định dạng không thể parse (`missing_effective_date`, `invalid_effective_date_format`).
  - Bản ghi của `hr_leave_policy` trước năm 2026 (`stale_hr_policy_effective_date`).
  - Bản ghi của `hr_leave_policy` chứa thông tin phép năm cũ "10 ngày phép" (`stale_hr_policy_text`).
  - Bản ghi trùng lặp nội dung (`duplicate_chunk_text`).
  - Dữ liệu cách ly được lưu tại `artifacts/quarantine/quarantine_[run_id].csv` phục vụ cho việc điều tra và điều phối lại.
- **Drop (Bỏ qua)**:
  - Bản ghi thiếu hoàn toàn nội dung chunk_text (`missing_chunk_text`).
- **Merge Approval**:
  - Dữ liệu trong quarantine chỉ được tái nạp khi chủ sở hữu nguồn dữ liệu (Ingestion/Data Quality Owner) xác nhận sửa đổi nghiệp vụ, cập nhật `cleaning_rules.py` hoặc điều chỉnh `data_contract.yaml`, và kích hoạt lại pipeline thành công.

---

## 4. Phiên bản & canonical

- **Source of truth (Canonical files)**:
  - `policy_refund_v4` -> `data/docs/policy_refund_v4.txt` (Chính sách hoàn tiền phiên bản 4 mới nhất - 7 ngày làm việc).
  - `sla_p1_2026` -> `data/docs/sla_p1_2026.txt` (Quy định SLA cho các ticket P1 năm 2026).
  - `it_helpdesk_faq` -> `data/docs/it_helpdesk_faq.txt` (FAQ xử lý sự cố IT Helpdesk).
  - `hr_leave_policy` -> `data/docs/hr_leave_policy.txt` (Quy định nghỉ phép năm 2026 - tối thiểu 12 ngày phép cho nhân viên < 3 năm).
  - `access_control_sop` -> `data/docs/access_control_sop.txt` (Quy trình chuẩn về cấp phát và quản lý quyền truy cập hệ thống).

