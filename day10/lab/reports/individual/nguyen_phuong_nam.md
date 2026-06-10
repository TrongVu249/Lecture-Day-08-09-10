# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Observability

**Họ và tên:** Nguyễn Phương Nam  
**Vai trò:** Monitoring & Docs Owner  
**Ngày nộp:** 2026-06-10  
**Độ dài:** ~500 từ

---

## 1. Tôi phụ trách phần nào?

**File / module:**

- `monitoring/freshness_check.py` — Triển khai đo lường độ tươi của dữ liệu (Freshness check).
- `docs/pipeline_architecture.md`, `docs/data_contract.md`, `docs/runbook.md` — Soạn thảo các tài liệu kỹ thuật của hệ thống.
- `reports/group_report.md` — Tổng hợp và hoàn thiện báo cáo nhóm Day 10.

**Kết nối với thành viên khác:**
Tôi chịu trách nhiệm phần giám sát và tài liệu hóa. Tôi nhận tệp tin manifest (`manifest_[run_id].json`) và file log sinh ra sau khi Hồ Tất Bảo Hoàng (Tech Lead / Ingest & Embed Owner) thực hiện embedding thành công. Tôi cũng phối hợp với Trọng Vũ (Cleaning & Quality Owner) để lấy thông tin cấu hình schema, các quy tắc quarantine nhằm đồng bộ vào tài liệu `data_contract.md` và `quality_report.md`.

**Bằng chứng (commit / comment trong code):**
- Lần chạy freshness check: `run_id = 2026-06-10T07-01Z`.
- Dòng log kiểm tra freshness trong console log của hệ thống:
  ```
  FAIL {"latest_exported_at": "2026-04-10T00:00:00", "age_hours": 1471.165, "sla_hours": 24.0, "reason": "freshness_sla_exceeded"}
  ```
- Ngoài ra tôi đã triển khai phần Dual Boundary Freshness trong `monitoring/freshness_check.py` với log output:
  ```
  freshness_boundary[ingest]=PASS  {"ingest_timestamp": "2026-06-10T07:44:27Z", "age_hours": 0.009, "sla_hours": 24.0}
  freshness_boundary[publish]=FAIL {"latest_exported_at": "2026-04-10T00:00:00", "age_hours": 1471.751, "sla_hours": 24.0}
  freshness_dual_overall=FAIL
  ```

---

## 2. Một quyết định kỹ thuật

**Thiết lập Dual Boundary Freshness (Giám sát 2 biên)**

Tôi quyết định bổ sung cơ chế kiểm tra **Dual Boundary Freshness** thay vì chỉ kiểm tra một biên thời gian xuất bản (Publish) duy nhất.
- *Lý do:* Đo lường đơn lẻ `latest_exported_at` (biên Publish) chỉ cho biết dữ liệu nguồn có bị trễ hay không. Tuy nhiên, nó không thể chỉ ra lỗi nếu bản thân pipeline bị kẹt không chạy trong nhiều ngày (khi đó file manifest cũ vẫn ghi nhận thời gian cũ nhưng không có lần chạy nào mới).
- *Thực hiện:* Đo biên **Ingest** (khi bắt đầu load CSV, ghi nhận `ingest_timestamp` vào manifest) để kiểm tra pipeline có chạy định kỳ không. Đồng thời đo biên **Publish** để kiểm tra dữ liệu nguồn. Kết quả tổng hợp chỉ `PASS` nếu cả hai biên đều nằm trong SLA.

---

## 3. Một lỗi hoặc anomaly đã xử lý

**Triệu chứng:**
Khi chạy kiểm tra freshness lần đầu, console hiển thị kết quả `FAIL` liên tục với giá trị `age_hours: 1471.03` mặc dù hệ thống nạp dữ liệu hoạt động bình thường và sinh log mới.

**Cách phát hiện & Khắc phục:**
- Tôi kiểm tra manifest `manifest_2026-06-10T07-01Z.json`, thấy trường `latest_exported_at` được lấy từ tệp tin thô là ngày `2026-04-10`. Do đây là tệp tin CSV giả lập tĩnh của Lab, nên thời gian xuất dữ liệu bị cố định ở quá khứ, dẫn tới việc tính toán độ lệch thời gian thực tế luôn vượt quá SLA 24h.
- Tôi đã xác nhận đây không phải lỗi logic của code check, mà là anomaly do đặc thù dữ liệu thử nghiệm.
- Tôi tiến hành tài liệu hóa hiện tượng này trong `docs/runbook.md`, phân loại rõ ràng trạng thái này và đưa ra hành động khắc phục cho môi trường Production (cần cập nhật nguồn tạo CSV động hoặc cấu hình lại biến môi trường `FRESHNESS_SLA_HOURS` phù hợp).

---

## 4. Bằng chứng trước / sau

**run_id:** `bonus-final`

Thông tin trích xuất từ manifest thể hiện hai mốc thời gian giám sát:

```json
{
  "run_id": "bonus-final",
  "ingest_timestamp": "2026-06-10T07:44:27Z",
  "latest_exported_at": "2026-04-10T00:00:00",
  "sla_hours": 24.0
}
```

Kết quả check cho thấy biên Ingest đạt yêu cầu (0.009 giờ < 24 giờ) nhưng biên Publish không đạt (1471.75 giờ > 24 giờ), hệ thống cảnh báo dữ liệu nguồn bị trễ.

---

## 5. Cải tiến tiếp theo

Nếu có thêm 2 giờ, tôi sẽ viết một webhook tích hợp gửi cảnh báo trực tiếp qua **Slack** hoặc **Discord** khi Freshness Check phát hiện trạng thái `FAIL`. Việc chỉ log stdout rất dễ bị bỏ qua trong môi trường vận hành lớn, cần gửi thông tin tức thời đến kênh on-call của đội ngũ kỹ sư để xử lý ngay lập tức.
