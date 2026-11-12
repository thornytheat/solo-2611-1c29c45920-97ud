from __future__ import annotations

from pydantic import BaseModel

from src.constants.enums import ExportFormat


class ExportIn(BaseModel):
    report_id: int
    format: ExportFormat = ExportFormat.MARKDOWN
