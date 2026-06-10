"""
Kiểm tra freshness từ manifest pipeline (SLA đơn giản theo giờ).

Bonus (+1): check_dual_boundary_freshness() đo ĐỒNG THỜI 2 boundary:
  - Boundary 1 (ingest):  `ingest_timestamp` — khi pipeline bắt đầu đọc raw CSV.
  - Boundary 2 (publish): `latest_exported_at` — timestamp xuất data từ source system.
Cả hai boundary được ghi vào manifest và log riêng biệt để có minh chứng đầy đủ.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple


def parse_iso(ts: str) -> datetime | None:
    if not ts:
        return None
    try:
        # Cho phép "2026-04-10T08:00:00" không có timezone
        if ts.endswith("Z"):
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def check_manifest_freshness(
    manifest_path: Path,
    *,
    sla_hours: float = 24.0,
    now: datetime | None = None,
) -> Tuple[str, Dict[str, Any]]:
    """
    Trả về ("PASS" | "WARN" | "FAIL", detail dict).

    Đọc trường `latest_exported_at` (boundary publish) từ manifest.
    """
    now = now or datetime.now(timezone.utc)
    if not manifest_path.is_file():
        return "FAIL", {"reason": "manifest_missing", "path": str(manifest_path)}

    data: Dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    ts_raw = data.get("latest_exported_at") or data.get("run_timestamp")
    dt = parse_iso(str(ts_raw)) if ts_raw else None
    if dt is None:
        return "WARN", {"reason": "no_timestamp_in_manifest", "manifest": data}

    age_hours = (now - dt).total_seconds() / 3600.0
    detail = {
        "latest_exported_at": ts_raw,
        "age_hours": round(age_hours, 3),
        "sla_hours": sla_hours,
    }
    if age_hours <= sla_hours:
        return "PASS", detail
    return "FAIL", {**detail, "reason": "freshness_sla_exceeded"}


def check_dual_boundary_freshness(
    manifest_path: Path,
    *,
    sla_hours: float = 24.0,
    now: datetime | None = None,
) -> Tuple[str, Dict[str, Any]]:
    """
    Bonus (+1): Đo freshness tại 2 boundary riêng biệt.

    Boundary 1 — Ingest boundary:
        `ingest_timestamp` trong manifest = thời điểm pipeline bắt đầu đọc raw CSV.
        Đo khoảng cách từ ingest đến now → phản ánh "data đã chờ bao lâu trong pipeline".

    Boundary 2 — Publish boundary:
        `latest_exported_at` = timestamp xuất data gốc từ source system (trong CSV).
        Đo khoảng cách từ export nguồn đến now → phản ánh "data gốc bao lâu rồi".

    Trả về (overall_status, detail_dict).
    overall_status = FAIL nếu BẤT KỲ boundary nào FAIL.
    """
    now = now or datetime.now(timezone.utc)
    if not manifest_path.is_file():
        return "FAIL", {"reason": "manifest_missing", "path": str(manifest_path)}

    data: Dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    results: List[Dict[str, Any]] = []
    overall_fail = False
    overall_warn = False

    # --- Boundary 1: Ingest ---
    ingest_raw = data.get("ingest_timestamp") or data.get("run_timestamp")
    dt_ingest = parse_iso(str(ingest_raw)) if ingest_raw else None
    if dt_ingest is None:
        results.append({"boundary": "ingest", "status": "WARN", "reason": "no_ingest_timestamp"})
        overall_warn = True
    else:
        age_ingest = round((now - dt_ingest).total_seconds() / 3600.0, 3)
        b1_status = "PASS" if age_ingest <= sla_hours else "FAIL"
        if b1_status == "FAIL":
            overall_fail = True
        results.append({
            "boundary": "ingest",
            "status": b1_status,
            "ingest_timestamp": ingest_raw,
            "age_hours": age_ingest,
            "sla_hours": sla_hours,
        })

    # --- Boundary 2: Publish (latest_exported_at từ source) ---
    pub_raw = data.get("latest_exported_at")
    dt_pub = parse_iso(str(pub_raw)) if pub_raw else None
    if dt_pub is None:
        results.append({"boundary": "publish", "status": "WARN", "reason": "no_latest_exported_at"})
        overall_warn = True
    else:
        age_pub = round((now - dt_pub).total_seconds() / 3600.0, 3)
        b2_status = "PASS" if age_pub <= sla_hours else "FAIL"
        if b2_status == "FAIL":
            overall_fail = True
        results.append({
            "boundary": "publish",
            "status": b2_status,
            "latest_exported_at": pub_raw,
            "age_hours": age_pub,
            "sla_hours": sla_hours,
        })

    if overall_fail:
        overall = "FAIL"
    elif overall_warn:
        overall = "WARN"
    else:
        overall = "PASS"

    return overall, {"dual_boundary": results, "overall": overall}
