# Quality Report — Lab Day 10: Data Pipeline & Data Observability

**Nhóm:** Nhóm 125 (Hồ Tất Bảo Hoàng, Trọng Vũ, Nguyễn Phương Nam)  
**run_id:** `2026-06-10T07-01Z`  
**Ngày chạy:** `2026-06-10`  
**Manifest:** `artifacts/manifests/manifest_2026-06-10T07-01Z.json`  
**Log:** `artifacts/logs/run_2026-06-10T07-01Z.log`

---

## 1. Tóm tắt số liệu pipeline

| Chỉ số | Inject Bad (before) | Fix (after) | Ghi chú |
|--------|---------------------|-------------|---------|
| `raw_records` | 247 | 247 | Cùng file raw CSV đầu vào |
| `cleaned_records` | 34 | 34 | Rule fix refund chỉ thay text, không thêm/bớt bản ghi |
| `quarantine_records` | 213 | 213 | Các rule quarantine hoạt động độc lập với refund fix |
| Expectation halt? | **Có** (`refund_no_stale_14d_window`) bỏ qua bằng `--skip-validate` | **Không** (tất cả PASS) | Log xác nhận |
| `embed_prune_removed` | 1 (prune chunk cũ sau restore) | 0 (ổn định) | Idempotency đảm bảo |
| `embed_upsert count` | 34 | 34 | Collection `day10_kb` |

---

## 2. Kết quả Expectation Suite (run `2026-06-10T07-01Z`)

| Expectation | Severity | Kết quả | Chi tiết |
|-------------|----------|---------|---------|
| `min_one_row` | **halt** | ✅ PASS | `cleaned_rows=34` |
| `no_empty_doc_id` | **halt** | ✅ PASS | `empty_doc_id_count=0` |
| `refund_no_stale_14d_window` | **halt** | ✅ PASS | `violations=0` |
| `chunk_min_length_8` | warn | ✅ PASS | `short_chunks=0` |
| `effective_date_iso_yyyy_mm_dd` | **halt** | ✅ PASS | `non_iso_rows=0` |
| `hr_leave_no_stale_10d_annual` | **halt** | ✅ PASS | `violations=0` |
| `no_stuttering_words` | warn | ✅ PASS | `stuttering_chunks=0` |
| `no_raw_warning_markers` | warn | ✅ PASS | `marker_chunks=0` |

> **Kết luận:** `should_halt = False` — pipeline tiếp tục đến bước embed.

---

## 3. Before / After Retrieval

> **Artifacts:**
> - Before (inject bad): [`after_inject_bad.csv`](file:///d:/Project/Vin_AI/Lab%2010/Lecture-Day-08-09-10/day10/lab/artifacts/eval/after_inject_bad.csv)
> - After (fix): [`after_fix_eval.csv`](file:///d:/Project/Vin_AI/Lab%2010/Lecture-Day-08-09-10/day10/lab/artifacts/eval/after_fix_eval.csv)

### 3a. Câu hỏi hoàn tiền — `q_refund_exception_digital`

| Metric | Before (inject) | After (fix) |
|--------|-----------------|-------------|
| `top1_doc_id` | `policy_refund_v4` | `policy_refund_v4` |
| `top1_preview` | `"...trong vòng **14 ngày** làm việc kể từ xác nhận đơn..."` | `"...trong vòng **7 ngày** làm việc kể từ xác nhận đơn. [cleaned: stale_refund_window]..."` |
| `contains_expected` | `no` (không thấy "7 ngày") | `yes` |
| `hits_forbidden` | `yes` ("14 ngày" là forbidden) | `no` |

**Phân tích:** Rule `stale_refund_window` (fix `14 ngày → 7 ngày`) trực tiếp ngăn agent trả lời sai chính sách hoàn tiền. Khi inject xấu, expectation `refund_no_stale_14d_window` phát hiện `FAIL (halt)` nhưng bị bypass bởi `--skip-validate`.

---

### 3b. Câu hỏi phép HR — `q_hr_annual_leave_under3`

| Metric | Before (inject) | After (fix) |
|--------|-----------------|-------------|
| `top1_doc_id` | `hr_leave_policy` | `hr_leave_policy` |
| `top1_preview` | `"...12 ngày phép năm theo chính sách 2026..."` | `"...12 ngày phép năm theo chính sách 2026..."` |
| `contains_expected` | `yes` | `yes` |
| `hits_forbidden` | `no` | `no` |
| `top1_doc_expected` | `yes` | `yes` |

**Phân tích:** HR rule hoạt động ổn định — rule `stale_hr_policy_effective_date` quarantine bản ghi 2025 (effective_date < 2026-01-01) và rule `stale_hr_policy_text` quarantine bản ghi chứa "10 ngày phép". Kết quả: agent luôn trả "12 ngày" đúng.

---

### 3c. Grading questions — Kết quả cuối

| Câu | Chủ đề | `contains_expected` | `hits_forbidden` | `top1_doc_matches` |
|-----|--------|--------------------|-----------------|--------------------|
| gq_d10_01 | Hoàn tiền (7 ngày) | ✅ true | ✅ false | ✅ true |
| gq_d10_02 | Ngoại lệ hoàn tiền | ✅ true | ✅ false | ✅ true |
| gq_d10_03 | Finance xử lý 3-5 ngày | ✅ true | ✅ false | ✅ true |
| gq_d10_04 | SLA P1 phản hồi 15 phút | ✅ true | ✅ false | ✅ true |
| gq_d10_05 | SLA P1 resolution 4 giờ | ✅ true | ✅ false | ✅ true |
| gq_d10_06 | Auto escalate P1 sau 10 phút | ✅ true | ✅ false | ✅ true |
| gq_d10_07 | Tài khoản bị khóa sau 5 lần | ✅ true | ✅ false | ✅ true |
| gq_d10_08 | VPN tối đa 2 thiết bị | ✅ true | ✅ false | ✅ true |
| gq_d10_09 | HR 2026: dưới 3 năm = 12 ngày | ✅ true | ✅ false | ✅ true |
| gq_d10_10 | Level 4 Admin: IT Manager + CISO | ✅ true | ✅ false | ✅ true |

> **10/10 câu đạt** — đủ điều kiện hạng Distinction.

---

## 4. Freshness & Monitoring

- **SLA:** `24.0 giờ` (cấu hình `FRESHNESS_SLA_HOURS=24` trong `.env`)
- **Kết quả run `2026-06-10T07-01Z`:**

```
FAIL {"latest_exported_at": "2026-04-10T00:00:00", "age_hours": 1471.03, "sla_hours": 24.0, "reason": "freshness_sla_exceeded"}
```

| Trạng thái | Điều kiện | Hành động |
|-----------|-----------|-----------|
| **PASS** | `age_hours ≤ 24` | Không cần hành động |
| **WARN** | Manifest thiếu `latest_exported_at` | Điều tra manifest |
| **FAIL** | `age_hours > 24` | Rerun `python etl_pipeline.py run` |

**Giải thích FAIL:** Trường `latest_exported_at = 2026-04-10T00:00:00` là timestamp cứng trong CSV demo — cố ý để minh họa cơ chế monitoring. Trong production, cần ghi timestamp động khi ingest.

---

## 5. Corruption Inject — Sprint 3

**Phương pháp mô phỏng:**

```bash
python etl_pipeline.py run --no-refund-fix --skip-validate
```

- `--no-refund-fix`: tắt rule `stale_refund_window` → chunk "14 ngày" không bị sửa → được embed vào ChromaDB
- `--skip-validate`: bỏ qua Expectation Suite (nếu không có flag này, pipeline halt ở `refund_no_stale_14d_window`)

**Phát hiện lỗi:**

1. **Expectation Suite** (`refund_no_stale_14d_window` → `FAIL (halt)`) phát hiện ngay nếu không có `--skip-validate`
2. **eval_retrieval.py** → `hits_forbidden=yes` cho câu refund — bằng chứng agent trả sai

**Phục hồi:**

```bash
python etl_pipeline.py run
# embed_prune_removed=1 (prune chunk "14 ngày" cũ)
# embed_upsert count=34 (upsert chunk "7 ngày" mới)
```

Sau phục hồi: `gq_d10_01` → `contains_expected=true`, `hits_forbidden=false` ✅

---

## 6. Rule mới — Metric Impact

| Rule / Expectation | Loại | Trước | Sau | Chứng cứ |
|--------------------|------|-------|-----|-----------|
| `clean_dirty_text` (loại `!!!` prefix, chuẩn hóa whitespace) | Clean | chunk_text có thể bắt đầu `!!!` | Tất cả trim sạch | `artifacts/cleaned/cleaned_2026-06-10T07-01Z.csv` |
| `fix_stutter_words` (sửa "làm việc làm việc") | Clean | Một số chunk lặp từ | Chỉ còn 1 lần | `transform/cleaning_rules.py` → `_clean_chunk_text()` |
| `stale_hr_policy_text` (quarantine HR "10 ngày phép năm") | Quarantine | HR chunks date hợp lệ nhưng text stale lọt qua | Bị quarantine, `reason=stale_hr_policy_text` | `artifacts/quarantine/quarantine_2026-06-10T07-01Z.csv` |
| `date_format_normalize` (DD/MM/YYYY → ISO) | Normalize | Nhiều bản ghi quarantine sai format | Các format phổ biến parse thành YYYY-MM-DD | `transform/cleaning_rules.py` → `_normalize_effective_date()` |
| `chunk_min_length_8` (warn) | Expectation | Không có check độ dài | Cảnh báo chunk < 8 ký tự | `quality/expectations.py` |
| `effective_date_iso_yyyy_mm_dd` (halt) | Expectation | Không check ISO sau clean | Halt nếu ngày sai format tồn tại | `quality/expectations.py` |

---

## 7. Hạn chế & Việc chưa làm

- **Freshness FAIL cố định:** `latest_exported_at` là timestamp cứng trong CSV demo. Production cần ghi timestamp động khi ingest.
- **Câu `q_p1_update_frequency` chưa pass:** Corpus thiếu chunk về tần suất cập nhật P1 → `contains_expected=no` trong eval thường (không ảnh hưởng grading questions).
- ~~Chưa tích hợp pydantic~~: **Đã hoàn thành** — `quality/schema_validator.py` (Bonus +2).
- ~~Freshness chỉ đo 1 boundary~~: **Đã hoàn thành** — dual boundary `ingest` + `publish` (Bonus +1).

---

## 8. Bonus — Bằng chứng

### Bonus +1: Freshness đo 2 boundary (`run_id=bonus-final`)

```
freshness_boundary[ingest]=PASS  {"ingest_timestamp": "2026-06-10T07:44:27Z", "age_hours": 0.009, "sla_hours": 24.0}
freshness_boundary[publish]=FAIL {"latest_exported_at": "2026-04-10T00:00:00", "age_hours": 1471.751, "sla_hours": 24.0}
freshness_dual_overall=FAIL
```

| Boundary | Timestamp | Age (hours) | Status |
|----------|-----------|-------------|--------|
| **Ingest** (khi pipeline đọc raw CSV) | `2026-06-10T07:44:27Z` | 0.009 | ✅ PASS |
| **Publish** (khi data được export từ source) | `2026-04-10T00:00:00` | 1471.751 | ❌ FAIL |

- **Module:** `monitoring/freshness_check.py` → `check_dual_boundary_freshness()`
- **Manifest field mới:** `ingest_timestamp` (ghi khi `load_raw_csv()` xong)
- **Ý nghĩa:** Boundary ingest PASS chứng minh pipeline tươi; boundary publish FAIL cảnh báo data nguồn đã cũ — hai thông tin khác nhau và đều có giá trị monitoring.

### Bonus +2: Pydantic schema validation thật (`run_id=bonus-final`)

```
pydantic_validate: total=34 valid=34 invalid=0 passed=True
```

- **Module:** `quality/schema_validator.py` → `CleanedRowSchema` (pydantic `BaseModel`)
- **Fields validated:** `chunk_id` (regex format), `doc_id` (allowlist), `chunk_text` (min_length=8, no stale markers), `effective_date` (ISO regex + `datetime.strptime` check thực)
- **Custom validators:** `doc_id_in_allowlist`, `effective_date_iso_format`, `chunk_id_format`, `no_stale_markers`
- **Tích hợp pipeline:** Gọi `validate_cleaned_rows()` sau `clean_rows()`, trước `run_expectations()`. Nếu có row fail schema → log lỗi cụ thể + chỉ pass `valid_rows` xuống bước embed.
- **Hỗ trợ:** pydantic v2 (field_validator) với fallback v1 (validator)
```
