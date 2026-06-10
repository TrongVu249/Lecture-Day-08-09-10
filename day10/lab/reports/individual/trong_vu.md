# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Observability

**Họ và tên:** Trọng Vũ  
**Vai trò:** Cleaning & Quality Owner  
**Ngày nộp:** 2026-06-10  
**Độ dài:** ~600 từ

---

> Viết **"tôi"**, đính kèm **run_id**, **tên file**, **đoạn log** và **dòng CSV** thật.

---

## 1. Tôi phụ trách phần nào?

**File / module:**

- `transform/cleaning_rules.py` — Thiết lập các rules làm sạch dữ liệu mới: `clean_dirty_text`, `fix_stutter_words`, chuẩn hóa định dạng ngày `date_format_normalize` và quy tắc cách ly dữ liệu `stale_hr_policy_text`.
- `quality/expectations.py` — Phát triển các expectations mới kiểm định chất lượng dữ liệu: `chunk_min_length_8`, `all_dates_iso_format` để đảm bảo dữ liệu sạch trước khi embedding.

**Kết nối với thành viên khác:** Tôi phối hợp chặt chẽ với Tech Lead Hồ Tất Bảo Hoàng (người phụ trách Ingest & Embed). Dữ liệu sau khi tôi làm sạch và validate thành công qua Expectations Suite sẽ được chuyển giao cho Hoàng thực hiện embedding vào ChromaDB collection `day10_kb`. Đồng thời, các log và thông tin chất lượng dữ liệu được bàn giao cho Nguyễn Phương Nam (Monitoring & Docs Owner) để theo dõi SLA freshness và cập nhật tài liệu runbook.

**Bằng chứng (commit / comment trong code):**

- `run_id = 2026-06-10T07-01Z` → Manifest: `artifacts/manifests/manifest_2026-06-10T07-01Z.json`
- Log: `artifacts/logs/run_2026-06-10T07-01Z.log` — dòng `cleaned_records=34`, `quarantine_records=213`
- Grading: `artifacts/eval/grading_run.jsonl` — 10/10 câu đạt `contains_expected=true`, `hits_forbidden=false`

---

## 2. Một quyết định kỹ thuật

**Chiến lược idempotency: Upsert + Prune thay vì chỉ Upsert**

Tôi chọn chiến lược **upsert theo `chunk_id` + prune chunk cũ** thay vì chỉ upsert đơn thuần. Lý do:

- **Upsert đơn thuần** ngăn được duplicate nội dung, nhưng nếu một chunk bị xóa khỏi cleaned (bị quarantine ở run sau), nó vẫn tồn tại trong ChromaDB từ run trước → gây "zombie vectors" làm nhiễu retrieval.
- **Prune trước upsert**: lấy `prev_ids` từ collection, tính `drop = prev_ids - set(current_ids)`, xóa chúng trước khi upsert → collection là **snapshot chính xác** của lần chạy hiện tại.

Điều này đặc biệt quan trọng cho Sprint 3: sau khi inject bad data (với `--no-refund-fix`), rerun pipeline sạch sẽ prune chunk "14 ngày" cũ và upsert chunk "7 ngày" đúng.

Log minh chứng từ `run_2026-06-10T07-01Z.log`:
```
embed_prune_removed=0
embed_upsert count=34 collection=day10_kb
```

---

## 3. Một lỗi hoặc anomaly đã xử lý

**Triệu chứng:** Khi chạy pipeline lần đầu (Sprint 1), `python etl_pipeline.py run` bị halt với exit code 2. Log hiển thị:

```
expectation[all_doc_ids_in_allowlist] FAIL (halt) :: found unknown doc_ids: {'access_control_sop'}
PIPELINE_HALT: expectation suite failed (halt).
```

**Metric/check phát hiện:** Expectation `all_doc_ids_in_allowlist` (halt) phát hiện `access_control_sop` không nằm trong `ALLOWED_DOC_IDS` của baseline.

**Fix:**
1. Phân tích `data/raw/policy_export_dirty.csv` → tìm thấy 5 unique `doc_id` trong CSV, bao gồm `access_control_sop`.
2. Thêm `"access_control_sop"` vào `ALLOWED_DOC_IDS` trong `transform/cleaning_rules.py`.
3. Cập nhật `contracts/data_contract.yaml` và `docs/data_contract.md` để khai báo nguồn mới.
4. Rerun: `python etl_pipeline.py run` → `PIPELINE_OK` (exit code 0).

Sau fix: cleaned_records tăng từ 27 lên 34 (thêm 7 chunk từ `access_control_sop`). Grading question `gq_d10_10` ("Level 4 Admin Access") chuyển từ `top1_doc_matches=false` sang `top1_doc_matches=true`.

---

## 4. Bằng chứng trước / sau

**run_id tham chiếu:** `inject-bad` (before) vs `2026-06-10T07-01Z` (after)

Dòng CSV from `after_inject_bad.csv` vs `after_fix_eval.csv`:

| File | `q_refund_exception_digital` top1_preview |
|------|------------------------------------------|
| `after_inject_bad.csv` | `Yêu cầu hoàn tiền được chấp nhận trong vòng **14 ngày** làm việc kể từ xác nhận đơn.` |
| `after_fix_eval.csv` | `Yêu cầu hoàn tiền được chấp nhận trong vòng **7 ngày** làm việc kể từ xác nhận đơn. [cleaned: stale_refund_window]` |

→ Rule `stale_refund_window` (fix "14→7 ngày") trực tiếp ngăn agent trả lời sai chính sách hoàn tiền.

---

## 5. Cải tiến tiếp theo

Nếu có thêm 2 giờ, tôi sẽ **triển khai freshness alert tự động**: khi `freshness_check` trả về `FAIL`, ghi vào một file `artifacts/alerts/freshness_alert_<run_id>.json` và gửi HTTP POST đến một webhook (Slack hoặc email). Hiện tại, FAIL chỉ được log và in ra stdout — không có cơ chế on-call notify. Trong production, mỗi phút dữ liệu stale là rủi ro agent trả sai → cần alert real-time để Data Owner rerun pipeline ngay lập tức.
