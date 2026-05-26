"""Auth audit log repository for persistence."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth_audit_log import AuthAuditLog


class AuthAuditLogRepository:
    def __init__(self, db: AsyncSession) -> None:
        """
        Store the provided asynchronous SQLAlchemy session for repository database operations.
        
        Parameters:
            db (AsyncSession): Asynchronous SQLAlchemy session used for database access.
        """
        self._db = db

    async def create(self, log_data: dict) -> AuthAuditLog:
        """
        Persist an AuthAuditLog created from the given data and return the persisted instance.
        
        Parameters:
            log_data (dict): Mapping of AuthAuditLog field names to values used to construct the record.
        
        Returns:
            AuthAuditLog: The persisted AuthAuditLog instance with any database-generated fields populated.
        """
        log = AuthAuditLog(**log_data)
        self._db.add(log)
        await self._db.flush()
        await self._db.refresh(log)
        return log
