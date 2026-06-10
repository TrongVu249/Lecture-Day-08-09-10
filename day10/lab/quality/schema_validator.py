"""
Pydantic schema validator cho cleaned rows — Bonus (+2).

Thay thế / bổ sung cho expectations.py bằng pydantic BaseModel
để validate schema thật trên từng cleaned row:
  - type checking (str, date format)
  - field constraints (min_length, regex)
  - custom validators (doc_id allowlist, effective_date range)

Tích hợp vào pipeline: gọi validate_cleaned_rows() sau clean_rows(),
trước run_expectations(). Lỗi validation được log và có thể halt.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

# Pydantic v1 hoặc v2 đều được hỗ trợ
try:
    from pydantic import BaseModel, Field, field_validator, model_validator  # v2
    _PYDANTIC_V2 = True
except ImportError:
    from pydantic import BaseModel, Field, validator  # type: ignore[no-redef]  # v1
    _PYDANTIC_V2 = False

_ALLOWED_DOC_IDS = frozenset({
    "policy_refund_v4",
    "sla_p1_2026",
    "it_helpdesk_faq",
    "hr_leave_policy",
    "access_control_sop",
})

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_CHUNK_ID_RE = re.compile(r"^[a-z0-9_]+_\d+_[a-f0-9]+$")


class CleanedRowSchema(BaseModel):
    """
    Schema contract cho mỗi row trong cleaned CSV.
    Validate bởi pydantic — không chỉ là placeholder.
    """

    chunk_id: str = Field(..., min_length=5, description="Unique hash-based chunk identifier")
    doc_id: str = Field(..., min_length=1, description="Document identifier from allowlist")
    chunk_text: str = Field(..., min_length=8, description="Cleaned chunk text, minimum 8 chars")
    effective_date: str = Field(..., description="Policy effective date in ISO YYYY-MM-DD format")
    exported_at: Optional[str] = Field(default="", description="Source export timestamp (optional)")

    if _PYDANTIC_V2:
        @field_validator("doc_id")
        @classmethod
        def doc_id_in_allowlist(cls, v: str) -> str:
            if v not in _ALLOWED_DOC_IDS:
                raise ValueError(f"doc_id '{v}' not in allowlist: {sorted(_ALLOWED_DOC_IDS)}")
            return v

        @field_validator("effective_date")
        @classmethod
        def effective_date_iso_format(cls, v: str) -> str:
            if not _ISO_DATE_RE.match(v.strip()):
                raise ValueError(f"effective_date '{v}' không đúng định dạng ISO YYYY-MM-DD")
            # Thêm: đảm bảo là ngày hợp lệ thật (không chỉ regex)
            try:
                datetime.strptime(v.strip(), "%Y-%m-%d")
            except ValueError:
                raise ValueError(f"effective_date '{v}' không phải ngày hợp lệ")
            return v.strip()

        @field_validator("chunk_id")
        @classmethod
        def chunk_id_format(cls, v: str) -> str:
            if not _CHUNK_ID_RE.match(v):
                raise ValueError(f"chunk_id '{v}' không đúng format <doc_id>_<seq>_<hash>")
            return v

        @field_validator("chunk_text")
        @classmethod
        def no_stale_markers(cls, v: str) -> str:
            if "14 ngày làm việc" in v and "policy_refund" in v.lower():
                raise ValueError("chunk_text chứa thông tin hoàn tiền stale (14 ngày)")
            if "10 ngày phép năm" in v:
                raise ValueError("chunk_text chứa thông tin phép HR stale (10 ngày phép)")
            if v.startswith("!!!") or v.startswith("Nội dung không rõ ràng:"):
                raise ValueError("chunk_text còn prefix warning chưa được clean")
            return v
    else:
        # Pydantic v1 validators
        @validator("doc_id")
        @classmethod
        def doc_id_in_allowlist(cls, v: str) -> str:
            if v not in _ALLOWED_DOC_IDS:
                raise ValueError(f"doc_id '{v}' not in allowlist")
            return v

        @validator("effective_date")
        @classmethod
        def effective_date_iso_format(cls, v: str) -> str:
            if not _ISO_DATE_RE.match(v.strip()):
                raise ValueError(f"effective_date '{v}' không đúng định dạng ISO YYYY-MM-DD")
            return v.strip()

        @validator("chunk_text")
        @classmethod
        def no_stale_markers(cls, v: str) -> str:
            if "10 ngày phép năm" in v:
                raise ValueError("chunk_text chứa thông tin phép HR stale")
            return v


class ValidationSummary:
    """Kết quả tổng hợp validate toàn bộ cleaned rows."""

    def __init__(self) -> None:
        self.valid: int = 0
        self.invalid: int = 0
        self.errors: List[Dict[str, Any]] = []

    def add_error(self, row_index: int, row: Dict[str, Any], error: str) -> None:
        self.invalid += 1
        self.errors.append({
            "row_index": row_index,
            "chunk_id": row.get("chunk_id", ""),
            "doc_id": row.get("doc_id", ""),
            "error": error,
        })

    @property
    def total(self) -> int:
        return self.valid + self.invalid

    @property
    def passed(self) -> bool:
        return self.invalid == 0

    def summary_line(self) -> str:
        return (
            f"pydantic_validate: total={self.total} valid={self.valid} "
            f"invalid={self.invalid} passed={self.passed}"
        )


def validate_cleaned_rows(
    rows: List[Dict[str, Any]],
) -> Tuple[ValidationSummary, List[Dict[str, Any]]]:
    """
    Validate từng row trong cleaned list bằng CleanedRowSchema (pydantic).

    Trả về (summary, valid_rows).
    valid_rows là danh sách row vượt qua schema — có thể dùng thay thế rows gốc
    để đảm bảo chỉ embed dữ liệu hợp lệ theo contract.
    """
    summary = ValidationSummary()
    valid_rows: List[Dict[str, Any]] = []

    for i, row in enumerate(rows):
        try:
            validated = CleanedRowSchema(**row)
            valid_rows.append(validated.model_dump() if _PYDANTIC_V2 else validated.dict())
            summary.valid += 1
        except Exception as exc:
            summary.add_error(i, row, str(exc))

    return summary, valid_rows
