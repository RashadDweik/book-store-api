"""Add release date to books.

Stores the book release/publication date as a nullable date.
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_add_book_release_date"
down_revision = "0004_add_auth_audit_logs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("books", sa.Column("release_date", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("books", "release_date")