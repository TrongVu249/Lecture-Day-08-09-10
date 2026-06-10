# Runbook — Lab Day 10 (Data Pipeline Incident Response)

**Cập nhật:** 2026-06-10  
**Phiên bản:** v1.0

---

## Freshness SLA — Giải thích trạng thái

Module `monitoring/freshness_check.py` so sánh trường `latest_exported_at` trong manifest với thời điểm kiểm tra hiện tại. SLA mặc định: **24 giờ** (cấu hình qua `FRESHNESS_SLA_HOURS` trong `.env`).

| Trạng thái | Điều kiện | Ý nghĩa | Hành động |
|-----------|-----------|---------|-----------|
| **PASS** | `age_hours <= sla_hours` | Dữ liệu trong collection được export và embed trong vòng SLA cho phép (ví dụ: ≤ 24 giờ). Pipeline hoạt động đúng kế hoạch. | Không cần hành động. Tiếp tục monitor theo lịch. |
| **WARN** | `latest_exported_at` không đọc được hoặc không tồn tại trong manifest | Manifest thiếu timestamp → không thể tính age. Thường do chạy với `--run-id` tùy chỉnh hoặc manifest bị tạo sai. | Kiểm tra lại manifest JSON, xác nhận trường `latest_exported_at` tồn tại và có định dạng ISO. |
| **FAIL** | `age_hours > sla_hours` hoặc manifest không tìm thấy | Dữ liệu trong collection đã cũ hơn SLA (ví dụ: 1471 giờ > 24 giờ), hoặc manifest bị mất. RAG agent có nguy cơ trả lời dựa trên thông tin lỗi thời. | Rerun pipeline ngay: `python etl_pipeline.py run`. Kiểm tra `artifacts/manifests/` cho run mới nhất. |

> **Lưu ý môi trường demo:** Dữ liệu demo có `latest_exported_at = 2026-04-10T00:00:00` (cố định trong CSV). Freshness SLA 24h sẽ luôn báo **FAIL** trong môi trường này. Đây là hành vi mong muốn để minh họa cơ chế monitoring — không phải lỗi logic.

---

## Kịch bản 1: Agent trả lời sai thông tin hoàn tiền ("14 ngày" thay vì "7 ngày")

### Symptom

- User/agent báo: chính sách hoàn tiền là "14 ngày làm việc".
- Query `q_refund_exception_digital` trong eval trả về `14 ngày làm việc` thay vì `7 ngày làm việc`.
- Câu hỏi grading `gq_d10_01` có `hits_forbidden = true`.

### Detection

| Metric / Check | Tín hiệu lỗi |
|----------------|--------------|
| Expectation `refund_no_stale_14d_window` | `FAIL (halt)` — phát hiện chunk chứa "14 ngày làm việc" trong `policy_refund_v4` |
| `eval_retrieval.py` kết quả | `contains_expected=no` hoặc `hits_forbidden=yes` cho các câu refund |
| Manifest `no_refund_fix=true` | Pipeline được chạy với `--no-refund-fix` |

### Diagnosis

| Bước | Việc làm | Kết quả mong đợi |
|------|----------|------------------|
| 1 | Kiểm tra `artifacts/manifests/*.json` → tìm file mới nhất, xem trường `no_refund_fix` | Nếu `true` → lỗi do chạy inject mode |
| 2 | Xem `artifacts/logs/run_*.log` → tìm dòng `expectation[refund_no_stale_14d_window]` | Nếu `FAIL (halt)` → xác nhận dữ liệu stale đã lọt vào embed |
| 3 | Mở `artifacts/quarantine/*.csv` → kiểm tra cột `quarantine_reason` | Bản ghi "14 ngày" lẽ ra phải bị quarantine với reason `stale_refund_window` |
| 4 | Chạy `python eval_retrieval.py --out artifacts/eval/debug_eval.csv` | So sánh với `after_fix_eval.csv` — các dòng `hits_forbidden=yes` chỉ ra chunk lỗi |

### Mitigation

```bash
# Fix: chạy lại pipeline với rule hoàn tiền được bật (mặc định)
python etl_pipeline.py run

# Sau khi chạy, verify:
python grading_run.py --out artifacts/eval/grading_run.jsonl
# Tất cả 10 câu phải có contains_expected=true, hits_forbidden=false
```

### Prevention

- Thêm expectation `refund_no_stale_14d_window` với severity `halt` (đã có) — ngăn embed khi có chunk stale.
- Không chạy `--no-refund-fix` trong môi trường production.
- Thiết lập freshness alert: nếu `FRESHNESS_SLA_HOURS` bị vượt, gửi cảnh báo cho Data Owner.

---

## Kịch bản 2: Agent trả lời sai thông tin nghỉ phép HR ("10 ngày" thay vì "12 ngày")

### Symptom

- Agent báo nhân viên dưới 3 năm được "10 ngày phép năm".
- Grading question `gq_d10_09` có `hits_forbidden = true`.

### Detection

| Metric / Check | Tín hiệu lỗi |
|----------------|--------------|
| Expectation `hr_leave_no_stale_10d_annual` | `FAIL (halt)` — phát hiện chunk HR chứa "10 ngày phép" |
| Eval `q_hr_annual_leave_under3` | `contains_expected=no` (12 ngày không xuất hiện) |
| Quarantine CSV | Thiếu bản ghi `stale_hr_policy_effective_date` (hr_leave_policy 2025) |

### Diagnosis

| Bước | Việc làm | Kết quả mong đợi |
|------|----------|------------------|
| 1 | Kiểm tra `artifacts/manifests/*.json` → `run_id` gần nhất | Xác nhận đúng run đang serve |
| 2 | Mở `artifacts/quarantine/*.csv` | Bản ghi hr_leave_policy có `effective_date < 2026-01-01` phải bị quarantine |
| 3 | Chạy `python eval_retrieval.py` | Xem `top1_preview` cho câu HR — phải thấy "12 ngày phép năm 2026" |

### Mitigation

```bash
# Rerun pipeline — rule stale_hr_policy_effective_date sẽ lọc bản ghi 2025
python etl_pipeline.py run
```

### Prevention

- Rule `stale_hr_policy_effective_date` quarantine bản ghi HR trước 2026 (đã có).
- Rule `hr_leave_no_stale_10d_annual` halt nếu bản ghi HR chứa "10 ngày phép" lọt qua (đã có).

---

## Kịch bản 3: Manifest missing — Freshness FAIL

### Symptom

- `python etl_pipeline.py freshness --manifest <path>` trả về `FAIL {"reason": "manifest_missing"}`.
- Không có file nào trong `artifacts/manifests/`.

### Diagnosis

| Bước | Việc làm | Kết quả mong đợi |
|------|----------|------------------|
| 1 | Kiểm tra `artifacts/manifests/*.json` | Phải có ít nhất 1 file manifest sau khi pipeline chạy thành công |
| 2 | Xem log `artifacts/logs/` | Tìm dòng `manifest_written=` — nếu không có, pipeline chưa chạy đến bước cuối |
| 3 | Chạy `python etl_pipeline.py run` | Tạo manifest mới nhất |

### Mitigation

```bash
python etl_pipeline.py run
# Sau đó kiểm tra:
python etl_pipeline.py freshness --manifest artifacts/manifests/manifest_<run_id>.json
```

---

## Nối sang Day 11

Nếu triển khai tiếp:
- Thêm **alert tự động** (email / Slack webhook) khi freshness FAIL.
- Tích hợp **Great Expectations** để validate schema mạnh hơn.
- Tạo **guardrail** ngăn RAG agent phục vụ khi freshness FAIL.
