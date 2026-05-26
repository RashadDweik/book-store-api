"""Add auth audit log table.

Stores append-only authentication activity (register/login/logout) without persisting raw refresh tokens.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "0004_add_auth_audit_logs"
down_revision = "0003_add_user_full_name"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auth_audit_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("event", sa.String(length=32), nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=1024), nullable=True),
        sa.Column("refresh_token_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_index("ix_auth_audit_logs_id", "auth_audit_logs", ["id"])
    op.create_index("ix_auth_audit_logs_user_id", "auth_audit_logs", ["user_id"])
    op.create_index("ix_auth_audit_logs_event", "auth_audit_logs", ["event"])
    op.create_index("ix_auth_audit_logs_created_at", "auth_audit_logs", ["created_at"])
    op.create_index(
        "ix_auth_audit_logs_refresh_token_hash",
        "auth_audit_logs",
        ["refresh_token_hash"],
    )


def downgrade() -> None:
    op.drop_index("ix_auth_audit_logs_refresh_token_hash", table_name="auth_audit_logs")
    op.drop_index("ix_auth_audit_logs_created_at", table_name="auth_audit_logs")
    op.drop_index("ix_auth_audit_logs_event", table_name="auth_audit_logs")
    op.drop_index("ix_auth_audit_logs_user_id", table_name="auth_audit_logs")
    op.drop_index("ix_auth_audit_logs_id", table_name="auth_audit_logs")
    op.drop_table("auth_audit_logs")
