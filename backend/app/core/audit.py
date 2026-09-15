"""
Shared audit_log row builder, used by any module's service layer that writes
AuditLog entries on create/update/delete (question_bank, enrollment, ...).
"""
from uuid import UUID
from app.modules.quiz_engine.models import AuditLog


def make_audit_entry(
    actor_id: UUID | None, action: str, entity_type: str, entity_id: UUID, diff: dict | None = None
) -> AuditLog:
    return AuditLog(actor_id=actor_id, action=action, entity_type=entity_type, entity_id=entity_id, diff=diff)
