"""Service for inserting auth audit log rows.

This is best-effort: failures must not affect endpoint responses.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

import structlog

from app.core.database import AsyncSessionFactory
from app.repositories.auth_audit_log_repository import AuthAuditLogRepository


AuthAuditEvent = Literal["register", "login", "logout"]

logger = structlog.get_logger()


class AuthAuditLogService:
    def __init__(self) -> None:
        self._session_factory = AsyncSessionFactory

    async def insert_event(
        self,
        *,
        user_id: UUID,
        event: AuthAuditEvent,
        ip_address: str | None = None,
        user_agent: str | None = None,
        refresh_token_hash: str | None = None,
    ) -> None:
        """Insert an audit row.

        This method never raises.
        """
        try:
            async with self._session_factory() as db:
                try:
                    repo = AuthAuditLogRepository(db)
                    await repo.create(
                        {
                            "user_id": user_id,
                            "event": event,
                            "ip_address": ip_address,
                            "user_agent": user_agent,
                            "refresh_token_hash": refresh_token_hash,
                        }
                    )
                    await db.commit()
                except Exception:
                    try:
                        await db.rollback()
                    except Exception:
                        pass
                    logger.warning(
                        "auth.audit_log_insert_failed",
                        event=event,
                        user_id=str(user_id),
                        exc_info=True,
                    )
        except Exception:
            logger.warning(
                "auth.audit_log_session_failed",
                event=event,
                user_id=str(user_id),
                exc_info=True,
            )
