"""Auth audit log repository for persistence."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth_audit_log import AuthAuditLog


class AuthAuditLogRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(self, log_data: dict) -> AuthAuditLog:
        log = AuthAuditLog(**log_data)
        self._db.add(log)
        await self._db.flush()
        await self._db.refresh(log)
        return log
