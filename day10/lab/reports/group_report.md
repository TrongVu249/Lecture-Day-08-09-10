# Báo Cáo Nhóm — Lab Day 10: Data Pipeline & Data Observability

**Tên nhóm:** Nhóm 125
| Tên | Vai trò (Day 10) | Email |
|-----|------------------|-------|
| Hồ Tất Bảo Hoàng | Tech Lead / Ingest & Embed Owner | hoanghtb@example.com |
| Trọng Vũ | Cleaning & Quality Owner | vutrong@example.com |
| Nguyễn Phương Nam | Monitoring & Docs Owner | namnp@example.com |

**Ngày nộp:** 2026-06-10  
**Repo:** `Lecture-Day-08-09-10` (branch: main)  
**Độ dài:** ~900 từ

---

> **Nộp tại:** `reports/group_report.md`  
> Có **run_id**, **đường dẫn artifact**, và **bằng chứng before/after** (CSV eval và log so sánh).

---

## 1. Pipeline tổng quan

**Tóm tắt luồng:**

Nguồn raw là file CSV mô phỏng export từ DB/API: `data/raw/policy_export_dirty.csv` gồm **247 bản ghi**. Pipeline xử lý theo chuỗi: **Ingest → Clean → Validate → Embed → Monitor**.

- **Ingest**: `load_raw_csv()` đọc CSV và trả về danh sách dict Python.
- **Clean**: `clean_rows()` áp dụng bộ rules lọc và chuẩn hóa, trả về hai danh sách `cleaned` (34 bản ghi) và `quarantine` (213 bản ghi).
- **Validate**: `run_expectations()` kiểm tra dữ liệu cleaned; nếu có expectation severity `halt` thất bại, pipeline dừng lại (exit code 2).
- **Embed**: `cmd_embed_internal()` upsert 34 vectors vào ChromaDB collection `day10_kb` theo chiến lược idempotent (upsert theo `chunk_id` + prune chunk cũ).
- **Monitor**: `check_manifest_freshness()` so sánh `latest_exported_at` trong manifest với SLA 24 giờ.

`run_id` được ghi vào tên manifest (`manifest_<run_id>.json`) và log (`artifacts/logs/run_<run_id>.log`). Lần chạy chính thức: `run_id = 2026-06-10T07-01Z`.

**Lệnh chạy một dòng:**

```bash
python etl_pipeline.py run
```

---

## 2. Cleaning & Expectation

### 2a. Bảng metric_impact

| Rule / Expectation mới (tên ngắn) | Trước (số liệu) | Sau / khi inject (số liệu) | Chứng cứ (log / CSV / commit) |
|-----------------------------------|------------------|-----------------------------|-------------------------------|
| `clean_dirty_text` (loại `!!!` prefix + chuẩn hóa whitespace) | chunk_text có thể bắt đầu bằng `!!!` hoặc `Nội dung không rõ ràng:` | Tất cả chunk_text đã được trim và chuẩn hóa khoảng trắng | `artifacts/cleaned/cleaned_2026-06-10T07-01Z.csv` |
| `fix_stutter_words` (sửa lặp từ "làm việc làm việc") | Một số chunk có từ "làm việc" bị lặp 2 lần | Chỉ còn "làm việc" một lần | `transform/cleaning_rules.py` → `_clean_chunk_text()` |
| `stale_hr_policy_text` (quarantine HR chứa "10 ngày phép năm") | HR chunks với date hợp lệ nhưng text stale vẫn lọt vào embed | Bị quarantine với reason `stale_hr_policy_text` | `artifacts/quarantine/quarantine_2026-06-10T07-01Z.csv` |
| `date_format_normalize` (DD/MM/YYYY, YYYY/MM/DD, DD-MM-YYYY → ISO) | Nhiều bản ghi có ngày sai định dạng → quarantine `invalid_effective_date_format` | Các format phổ biến được parse và chuẩn hóa thành YYYY-MM-DD | `transform/cleaning_rules.py` → `_normalize_effective_date()` |
| Expectation `chunk_min_length_8` (warn) | Không có check độ dài tối thiểu | Cảnh báo nếu có chunk < 8 ký tự sau cleaning | `quality/expectations.py` |
| Expectation `all_dates_iso_format` (halt) | Không check format ngày sau clean | Halt nếu cleaned CSV vẫn chứa ngày sai ISO | `quality/expectations.py` |

**Rule chính (baseline + mở rộng):**

- `unknown_doc_id`: quarantine bản ghi doc_id ngoài allowlist 5 documents.
- `missing_effective_date` / `invalid_effective_date_format`: quarantine bản ghi thiếu hoặc sai ngày.
- `stale_hr_policy_effective_date`: quarantine hr_leave_policy có date < 2026-01-01.
- `stale_hr_policy_text`: quarantine hr_leave_policy chứa text "10 ngày phép" dù date hợp lệ *(mới - Sprint 2)*.
- `duplicate_chunk_text`: loại bỏ bản ghi trùng nội dung.
- `clean_dirty_text`: dọn text bẩn (prefix warning, lặp từ) *(mới - Sprint 2)*.
- `date_format_normalize`: chuẩn hóa DD/MM/YYYY, YYYY/MM/DD, DD-MM-YYYY sang ISO *(mới - Sprint 2)*.
- `stale_refund_window`: fix text "14 ngày" → "7 ngày" trong policy_refund_v4.

**Ví dụ expectation fail và cách xử lý:**

Khi chạy inject mode (`--no-refund-fix --skip-validate`), expectation `refund_no_stale_14d_window` báo `FAIL (halt)` vì chunk "14 ngày làm việc" lọt vào cleaned. Pipeline log `WARN: expectation failed but --skip-validate → tiếp tục embed` và vẫn upsert. Kết quả: agent trả về thông tin stale. Fix: chạy lại pipeline bình thường (không có `--no-refund-fix`), expectation PASS, agent trả về đúng 7 ngày.

---

## 3. Before / after ảnh hưởng retrieval

**Kịch bản inject (Sprint 3):**

Chạy pipeline với `--no-refund-fix --skip-validate` để mô phỏng sự cố embedding dữ liệu stale. Rule sửa cửa sổ hoàn tiền bị tắt → chunk "14 ngày làm việc" được embed vào ChromaDB. Expectation `refund_no_stale_14d_window` phát hiện nhưng bị bỏ qua nhờ `--skip-validate`.

**Kết quả định lượng:**

| Câu hỏi | Before (inject) top1_preview | After (fix) top1_preview | Thay đổi |
|---------|------------------------------|--------------------------|---------|
| `q_refund_exception_digital` | `14 ngày làm việc kể từ xác nhận đơn` | `7 ngày làm việc kể từ xác nhận đơn [cleaned: stale_refund_window]` | ✅ Đúng sau fix |
| `q_hr_annual_leave_under3` | `12 ngày phép năm theo chính sách 2026` | `12 ngày phép năm theo chính sách 2026` | ✅ Ổn định (HR rule hoạt động) |
| `q_p1_update_frequency` | `contains_expected=no` | `contains_expected=no` | ⚠️ Miss cả 2 (thiếu chunk cụ thể về interval P1) |

Đường dẫn artifacts:
- Before: [`after_inject_bad.csv`](file:///d:/Project/Vin_AI/Lab%2010/Lecture-Day-08-09-10/day10/lab/artifacts/eval/after_inject_bad.csv)
- After: [`after_fix_eval.csv`](file:///d:/Project/Vin_AI/Lab%2010/Lecture-Day-08-09-10/day10/lab/artifacts/eval/after_fix_eval.csv)

---

## 4. Freshness & Monitoring

**SLA được chọn:** 24 giờ (thiết lập qua `FRESHNESS_SLA_HOURS=24` trong `.env`).

**Kết quả freshness check** (run_id `2026-06-10T07-01Z`):

```
FAIL {"latest_exported_at": "2026-04-10T00:00:00", "age_hours": 1471.165, "sla_hours": 24.0, "reason": "freshness_sla_exceeded"}
```

- **Ý nghĩa PASS:** Dữ liệu được export trong vòng 24 giờ → collection tươi, agent có thể phục vụ an toàn.
- **Ý nghĩa WARN:** Manifest thiếu timestamp → không tính được age, cần điều tra ngay.
- **Ý nghĩa FAIL:** `age_hours > 24` → dữ liệu stale. Trong demo này, `latest_exported_at` cố định là `2026-04-10` nên luôn FAIL — đây là hành vi mong muốn để minh họa cơ chế alert. Trong production, cần rerun pipeline khi nhận FAIL.

---

## 5. Liên hệ Day 09

Pipeline Day 10 dùng **collection riêng** `day10_kb` tách biệt khỏi collection Day 09. Lý do tách: Day 09 dùng corpus tĩnh `.txt` cho RAG experiment; Day 10 xử lý export CSV động qua ETL đầy đủ với data cleaning và validation, mô phỏng production pipeline.

Hai collection chia sẻ cùng thư mục `data/docs/` làm nguồn canonical. Nếu cần cập nhật corpus cho Day 09, có thể đồng bộ bằng cách chỉnh `CHROMA_COLLECTION` trong `.env`. Pipeline Day 10 đảm bảo chất lượng dữ liệu trước khi serve — đây là layer bổ sung phù hợp với kiến trúc multi-agent của Day 09.

---

## 6. Rủi ro còn lại & việc chưa làm

- **Freshness FAIL cố định:** `latest_exported_at` là timestamp cứng trong CSV demo → không phản ánh thời điểm chạy thực. Production cần ghi timestamp động khi ingest.
- **Câu hỏi `q_p1_update_frequency` chưa pass:** Corpus thiếu chunk cụ thể về tần suất cập nhật sự cố P1 → `contains_expected=no` cả hai eval. Cần bổ sung chunk vào `sla_p1_2026.txt`.
- **Chưa tích hợp alert tự động:** Freshness FAIL chỉ được log, chưa gửi cảnh báo Slack/email.
- **Chưa dùng Great Expectations/Pydantic:** Validation hiện tại là Python thuần; nâng cấp lên framework chuyên dụng sẽ mạnh hơn.
