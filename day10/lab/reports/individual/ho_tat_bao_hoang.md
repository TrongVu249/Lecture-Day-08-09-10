# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Observability

**Họ và tên:** Hồ Tất Bảo Hoàng  
**Vai trò:** Tech Lead / Ingest & Embed Owner  
**Ngày nộp:** 2026-06-10  
**Độ dài:** ~500 từ

---

## 1. Tôi phụ trách phần nào?

**File / module:**

- `etl_pipeline.py` — Orchestration & Embed (tích hợp luồng và gọi `cmd_embed_internal()`).
- `data/raw/policy_export_dirty.csv` — Phân tích cấu trúc dữ liệu thô (247 bản ghi).
- Quản lý collection `day10_kb` trên ChromaDB.

**Kết nối với thành viên khác:**
Là Tech Lead, tôi phụ trách kết nối toàn bộ pipeline. Tôi nhận các rules làm sạch dữ liệu và bộ validation từ Trọng Vũ (Cleaning & Quality Owner), tích hợp vào hàm `clean_rows()` và `run_expectations()`. Sau khi dữ liệu được xác thực sạch sẽ, tôi tiến hành embedding vào database. Sau khi hoàn tất, tôi chuyển giao các tệp manifest và log cho Nguyễn Phương Nam (Monitoring & Docs Owner) để thiết lập hệ thống giám sát freshness SLA và soạn thảo tài liệu kỹ thuật.

**Bằng chứng (commit / comment trong code):**
- Lần chạy chính thức: `run_id = 2026-06-10T07-01Z`.
- Dòng log ghi nhận quá trình embed trong `artifacts/logs/run_2026-06-10T07-01Z.log`:
  ```
  embed_prune_removed=0
  embed_upsert count=34 collection=day10_kb
  ```
- Kết quả manifest được sinh ra tại: `artifacts/manifests/manifest_2026-06-10T07-01Z.json`.

---

## 2. Một quyết định kỹ thuật

**Chiến lược Idempotency: Upsert kết hợp Prune**

Tôi quyết định sử dụng cơ chế **upsert dựa trên `chunk_id` kết hợp với dọn dẹp (pruning) các ID thừa** thay vì chỉ upsert thông thường. 
- *Lý do:* Khi chạy lại pipeline với bộ quy tắc làm sạch nghiêm ngặt hơn (ví dụ: đưa thêm các bản ghi cũ vào quarantine), số lượng chunk sạch ở lần chạy sau sẽ ít hơn hoặc khác với lần chạy trước. Nếu chỉ thực hiện `upsert`, các vector cũ không còn tồn tại trong tập dữ liệu mới vẫn sẽ nằm lại trong ChromaDB (zombie vectors), gây nhiễu nghiêm trọng đến kết quả tìm kiếm của agent.
- *Thực hiện:* Trước khi upsert dữ liệu mới, tôi lấy toàn bộ ID hiện có trong collection (`prev_ids`), so sánh để tìm ra các ID thừa (`drop = prev_ids - current_ids`) và gọi hàm xóa chúng trước khi cập nhật dữ liệu mới.

---

## 3. Một lỗi hoặc anomaly đã xử lý

**Triệu chứng:**
Khi chạy thử nghiệm mô phỏng sự cố ở Sprint 3 với cấu hình inject dữ liệu stale (`--no-refund-fix --skip-validate`), ChromaDB nạp nhầm chunk chứa chính sách hoàn tiền cũ "14 ngày" từ tài liệu `policy_refund_v4` vào vector store. Khi chạy kiểm thử, câu hỏi `q_refund_exception_digital` trả về kết quả sai nghiệp vụ nghiêm trọng (`hits_forbidden=yes`).

**Cách phát hiện & Khắc phục:**
- Khi chạy kiểm thử validation, expectation `refund_no_stale_14d_window` báo lỗi `FAIL (halt)`.
- Tôi phối hợp với Trọng Vũ để kích hoạt lại rule `stale_refund_window` nhằm thay thế "14 ngày" thành "7 ngày" trong text trước khi nạp.
- Tôi tiến hành chạy lại pipeline chuẩn (không bỏ qua validate). Log hệ thống ghi nhận `embed_prune_removed=1`, chứng tỏ vector stale chứa thông tin "14 ngày" cũ đã bị loại bỏ thành công và nạp lại thông tin "7 ngày" chính xác.

---

## 4. Bằng chứng trước / sau

**run_id:** `inject-bad` (trước) vs `2026-06-10T07-01Z` (sau)

Kết quả từ file `after_inject_bad.csv` và `after_fix_eval.csv` cho câu hỏi hoàn tiền:

| Run ID | `q_refund_exception_digital` top1_preview | contains_expected | hits_forbidden |
|--------|------------------------------------------|-------------------|----------------|
| `inject-bad` | `...trong vòng 14 ngày làm việc...` | `no` | `yes` |
| `2026-06-10T07-01Z` | `...trong vòng 7 ngày làm việc... [cleaned: stale_refund_window]` | `yes` | `no` |

---

## 5. Cải tiến tiếp theo

Nếu có thêm 2 giờ, tôi sẽ nghiên cứu tích hợp **async/batch processing** khi gọi API embedding và lưu trữ vào ChromaDB. Việc này giúp cải thiện đáng kể tốc độ nạp dữ liệu (ingestion rate) trong trường hợp dữ liệu đầu vào tăng quy mô từ hàng trăm dòng lên hàng vạn dòng CSV, tránh nghẽn luồng xử lý chính của pipeline.
