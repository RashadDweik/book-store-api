"""Add roles and user role_id."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid

revision = "0002_add_roles"
down_revision = "0001_initial_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=50), nullable=False),
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
        sa.UniqueConstraint("name", name="uq_roles_name"),
    )
    op.create_index("ix_roles_id", "roles", ["id"])
    op.create_index("ix_roles_name", "roles", ["name"])

    # Use a lightweight table definition for bulk insert without ORM models.
    user_role_id = uuid.uuid4()
    admin_role_id = uuid.uuid4()
    roles_table = sa.table(
        "roles",
        sa.column("id", UUID(as_uuid=True)),
        sa.column("name", sa.String()),
    )
    # Seed default roles so existing users can be assigned.
    op.bulk_insert(
        roles_table,
        [
            {"id": user_role_id, "name": "user"},
            {"id": admin_role_id, "name": "admin"},
        ],
    )

    op.add_column("users", sa.Column("role_id", UUID(as_uuid=True), nullable=True))
    op.create_index("ix_users_role_id", "users", ["role_id"])
    op.create_foreign_key(
        "fk_users_role_id_roles",
        "users",
        "roles",
        ["role_id"],
        ["id"],
    )
    # Backfill existing users before enforcing non-null role_id.
    op.execute(
        sa.text("UPDATE users SET role_id = :role_id WHERE role_id IS NULL").bindparams(
            role_id=user_role_id
        )
    )
    op.alter_column("users", "role_id", existing_type=UUID(as_uuid=True), nullable=False)


def downgrade() -> None:
    op.drop_constraint("fk_users_role_id_roles", "users", type_="foreignkey")
    op.drop_index("ix_users_role_id", table_name="users")
    op.drop_column("users", "role_id")

    op.drop_index("ix_roles_name", table_name="roles")
    op.drop_index("ix_roles_id", table_name="roles")
    op.drop_table("roles")
