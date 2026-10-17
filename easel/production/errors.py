"""Public production errors, with no provider bodies or credentials attached."""
from __future__ import annotations


class ProductionError(Exception):
    def __init__(self, code: str, user_message: str, *, status_code: int = 422,
                 retryable: bool = False, affected_ids: list[str] | None = None,
                 operation_id: str | None = None, requires_decision: bool = False):
        super().__init__(user_message)
        self.code = code
        self.user_message = user_message
        self.status_code = status_code
        self.retryable = retryable
        self.affected_ids = affected_ids or []
        self.operation_id = operation_id
        self.requires_decision = requires_decision

    def as_dict(self) -> dict:
        return {"code": self.code, "user_message": self.user_message,
                "retryable": self.retryable, "affected_ids": self.affected_ids,
                "operation_id": self.operation_id, "requires_decision": self.requires_decision}


class NotFound(ProductionError):
    def __init__(self, message: str = "记录不存在或不可访问"):
        super().__init__("not_found", message, status_code=404)


class Conflict(ProductionError):
    def __init__(self, message: str = "命令与现有记录冲突", *, code: str = "command_conflict"):
        super().__init__(code, message, status_code=409)


class StaleRevision(Conflict):
    def __init__(self, message: str = "版本已变化，请刷新后重试"):
        super().__init__(message, code="stale_revision")


class MigrationError(ProductionError):
    def __init__(self, message: str = "V2 数据库迁移失败，原有记录已保留"):
        super().__init__("migration_failed", message, status_code=503)
