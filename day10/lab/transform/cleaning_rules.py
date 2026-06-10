"""
Cleaning rules — raw export → cleaned rows + quarantine.

Baseline gồm các failure mode mở rộng (allowlist doc_id, parse ngày, HR stale version).
Sinh viên thêm ≥3 rule mới: mỗi rule phải ghi `metric_impact` (xem README — chống trivial).

Distinction (d): ngày cutoff HR đọc từ biến môi trường HR_LEAVE_MIN_EFFECTIVE_DATE
(mặc định 2026-01-01). Inject giá trị khác sẽ thay đổi quyết định clean mà không cần
chỉnh sửa code — chứng minh không hard-code.
"""

from __future__ import annotations

import csv
import hashlib
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Khớp export hợp lệ trong lab (mở rộng khi nhóm thêm doc mới — phải đồng bộ contract).
ALLOWED_DOC_IDS = frozenset(
    {
        "policy_refund_v4",
        "sla_p1_2026",
        "it_helpdesk_faq",
        "hr_leave_policy",
        "access_control_sop",
    }
)

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DMY_SLASH = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")
_YMD_SLASH = re.compile(r"^(\d{4})/(\d{1,2})/(\d{1,2})$")
_DMY_DASH = re.compile(r"^(\d{1,2})-(\d{1,2})-(\d{4})$")


def _norm_text(s: str) -> str:
    return " ".join((s or "").strip().split()).lower()


def _stable_chunk_id(doc_id: str, chunk_text: str, seq: int) -> str:
    h = hashlib.sha256(f"{doc_id}|{chunk_text}|{seq}".encode("utf-8")).hexdigest()[:16]
    return f"{doc_id}_{seq}_{h}"


def _normalize_effective_date(raw: str) -> Tuple[str, str]:
    """
    Trả về (iso_date, error_reason).
    iso_date rỗng nếu không parse được.
    """
    s = (raw or "").strip()
    if not s:
        return "", "empty_effective_date"
    
    # Isolate date part if it has a time component
    s_date = s.split('T')[0].split(' ')[0]
    
    if _ISO_DATE.match(s_date):
        return s_date, ""
        
    m_dmy_slash = _DMY_SLASH.match(s_date)
    if m_dmy_slash:
        dd, mm, yyyy = m_dmy_slash.group(1), m_dmy_slash.group(2), m_dmy_slash.group(3)
        return f"{yyyy}-{mm.zfill(2)}-{dd.zfill(2)}", ""
        
    m_ymd_slash = _YMD_SLASH.match(s_date)
    if m_ymd_slash:
        yyyy, mm, dd = m_ymd_slash.group(1), m_ymd_slash.group(2), m_ymd_slash.group(3)
        return f"{yyyy}-{mm.zfill(2)}-{dd.zfill(2)}", ""
        
    m_dmy_dash = _DMY_DASH.match(s_date)
    if m_dmy_dash:
        dd, mm, yyyy = m_dmy_dash.group(1), m_dmy_dash.group(2), m_dmy_dash.group(3)
        return f"{yyyy}-{mm.zfill(2)}-{dd.zfill(2)}", ""
        
    return "", "invalid_effective_date_format"


def _clean_chunk_text(text: str) -> str:
    """
    Dọn dẹp text bẩn: loại bỏ tiền tố warning/chú ý và sửa lặp từ.
    """
    t = (text or "").strip()
    # Loại bỏ các prefix warning
    while True:
        changed = False
        if t.startswith("!!!"):
            t = t[3:].strip()
            changed = True
        if t.startswith("Nội dung không rõ ràng:"):
            t = t[len("Nội dung không rõ ràng:"):].strip()
            changed = True
        if not changed:
            break
            
    # Chuẩn hóa lặp từ "làm việc làm việc" -> "làm việc"
    t = re.sub(r"(làm\s+việc\s*){2,}", "làm việc ", t, flags=re.IGNORECASE)
    
    # Chuẩn hóa khoảng trắng thừa
    return " ".join(t.split())


def load_raw_csv(path: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append({k: (v or "").strip() for k, v in r.items()})
    return rows


def clean_rows(
    rows: List[Dict[str, str]],
    *,
    apply_refund_window_fix: bool = True,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Trả về (cleaned, quarantine).

    Baseline (mở rộng theo narrative Day 10):
    1) Quarantine: doc_id không thuộc allowlist (export lạ / catalog sai).
    2) Chuẩn hoá effective_date sang YYYY-MM-DD; quarantine nếu không parse được.
    3) Quarantine: chunk hr_leave_policy có effective_date < 2026-01-01 (bản HR cũ / conflict version).
    4) Quarantine: chunk_text rỗng hoặc effective_date rỗng sau chuẩn hoá.
    5) Loại trùng nội dung chunk_text (giữ bản đầu).
    6) Fix stale refund: policy_refund_v4 chứa '14 ngày làm việc' → 7 ngày.
    
    Sinh viên mở rộng Sprint 2:
    - Dọn dẹp text bẩn (!!!" và "Nội dung không rõ ràng:") và chuẩn hóa khoảng trắng.
    - Sửa lặp từ "làm việc làm việc".
    - Lọc bỏ bản ghi HR chứa thông tin 10 ngày phép cũ (mặc dù date hợp lệ) -> quarantine với lý do stale_hr_policy_text.
    """
    quarantine: List[Dict[str, Any]] = []
    seen_text: set[str] = set()
    cleaned: List[Dict[str, Any]] = []
    seq = 0

    for raw in rows:
        doc_id = raw.get("doc_id", "")
        text = raw.get("chunk_text", "")
        eff_raw = raw.get("effective_date", "")
        exported_at = raw.get("exported_at", "")

        if doc_id not in ALLOWED_DOC_IDS:
            quarantine.append({**raw, "reason": "unknown_doc_id"})
            continue

        eff_norm, eff_err = _normalize_effective_date(eff_raw)
        if eff_err == "empty_effective_date":
            quarantine.append({**raw, "reason": "missing_effective_date"})
            continue
        if eff_err == "invalid_effective_date_format":
            quarantine.append({**raw, "reason": eff_err, "effective_date_raw": eff_raw})
            continue

        # Distinction (d): đọc cutoff từ env, không hard-code trong code.
        # Thay đổi HR_LEAVE_MIN_EFFECTIVE_DATE trong .env để inject giá trị khác
        # và chứng minh quyết định quarantine/clean thay đổi theo cấu hình.
        hr_cutoff = os.environ.get("HR_LEAVE_MIN_EFFECTIVE_DATE", "2026-01-01")
        if doc_id == "hr_leave_policy" and eff_norm < hr_cutoff:
            quarantine.append(
                {
                    **raw,
                    "reason": "stale_hr_policy_effective_date",
                    "effective_date_normalized": eff_norm,
                }
            )
            continue

        # Clean dirty text, warnings and stuttering words
        cleaned_text = _clean_chunk_text(text)
        if not cleaned_text:
            quarantine.append({**raw, "reason": "missing_chunk_text"})
            continue

        # Quarantine stale HR leave policy text containing 10-day leave
        if doc_id == "hr_leave_policy":
            stale_hr_markers = ["10 ngày phép năm", "10 ngày làm việc phép năm"]
            if any(marker in cleaned_text for marker in stale_hr_markers):
                quarantine.append(
                    {
                        **raw,
                        "reason": "stale_hr_policy_text",
                        "effective_date_normalized": eff_norm,
                    }
                )
                continue

        key = _norm_text(cleaned_text)
        if key in seen_text:
            quarantine.append({**raw, "reason": "duplicate_chunk_text"})
            continue
        seen_text.add(key)

        fixed_text = cleaned_text
        if apply_refund_window_fix and doc_id == "policy_refund_v4":
            if "14 ngày làm việc" in fixed_text:
                fixed_text = fixed_text.replace(
                    "14 ngày làm việc",
                    "7 ngày làm việc",
                )
                fixed_text += " [cleaned: stale_refund_window]"

        seq += 1
        cleaned.append(
            {
                "chunk_id": _stable_chunk_id(doc_id, fixed_text, seq),
                "doc_id": doc_id,
                "chunk_text": fixed_text,
                "effective_date": eff_norm,
                "exported_at": exported_at or "",
            }
        )

    return cleaned, quarantine


def write_cleaned_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("chunk_id,doc_id,chunk_text,effective_date,exported_at\n", encoding="utf-8")
        return
    fieldnames = ["chunk_id", "doc_id", "chunk_text", "effective_date", "exported_at"]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})


def write_quarantine_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("chunk_id,doc_id,chunk_text,effective_date,exported_at,reason\n", encoding="utf-8")
        return
    keys: List[str] = []
    seen_k: set[str] = set()
    for r in rows:
        for k in r.keys():
            if k not in seen_k:
                seen_k.add(k)
                keys.append(k)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore", restval="")
        w.writeheader()
        for r in rows:
            w.writerow(r)
