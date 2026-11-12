"""导出控制器：渲染 MD/CSV，落共享卷并返回内容。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.constants.enums import ExportFormat
from src.models.funnel import FunnelDef
from src.schemas.export import ExportIn
from src.services import audit_service, export_service, report_service, run_service


def export_report(db: Session, payload: ExportIn, actor: dict) -> dict:
    report = report_service.get(db, payload.report_id)
    funnel = db.get(FunnelDef, report.funnel_id)
    run, _ = run_service.get_run(db, report.run_id)
    run_payload = run_service.serialize(run, funnel)
    if payload.format == ExportFormat.CSV:
        content = export_service.render_csv(report)
        filename = f"{report.code.lower()}-paths.csv"
        media_type = "text/csv"
    else:
        content = export_service.render_markdown(report, funnel, run_payload)
        filename = f"{report.code.lower()}-attribution.md"
        media_type = "text/markdown"
    path = export_service.persist(filename, content)
    audit_service.record(
        db,
        actor_email=actor["email"],
        actor_role=actor["role"],
        action="export.render",
        entity="report",
        entity_id=report.id,
        detail={"format": payload.format.value, "filename": filename, "bytes": len(content.encode("utf-8"))},
    )
    db.commit()
    return {
        "filename": filename,
        "media_type": media_type,
        "content": content,
        "path_count": len(report.top_paths or []),
        "stored_path": path,
    }
