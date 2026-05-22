"""Add users.full_name.

The API schemas expect `full_name` to exist and be non-null.
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_add_user_full_name"
down_revision = "0002_add_roles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("full_name", sa.String(length=255), nullable=True))

    # Backfill existing rows before enforcing non-null.
    op.execute(
        sa.text("UPDATE users SET full_name = :full_name WHERE full_name IS NULL").bindparams(
            full_name="User"
        )
    )

    op.alter_column(
        "users",
        "full_name",
        existing_type=sa.String(length=255),
        nullable=False,
    )


def downgrade() -> None:
    op.drop_column("users", "full_name")
