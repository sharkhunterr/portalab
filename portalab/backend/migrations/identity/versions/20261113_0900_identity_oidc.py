"""identity schema — single sign-on (OIDC): the provider accounts linked to members, and the sign-ons in
progress (027)

Revision ID: identity_0002
Revises: identity_0001
Create Date: 2026-11-13 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "identity_0002"
down_revision: str | Sequence[str] | None = "identity_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "external_identities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("issuer", sa.String(length=512), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_sign_in_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["identity.users.id"],
            name=op.f("fk_external_identities_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_external_identities")),
        sa.UniqueConstraint("issuer", "subject", name="uq_external_identities_issuer_subject"),
        schema="identity",
    )
    op.create_index("ix_external_identities_user_id", "external_identities", ["user_id"], schema="identity")
    op.create_table(
        "oidc_logins",
        sa.Column("state", sa.String(length=64), nullable=False),
        sa.Column("nonce", sa.String(length=64), nullable=False),
        sa.Column("verifier", sa.String(length=128), nullable=False),
        sa.Column("next_path", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("state", name=op.f("pk_oidc_logins")),
        schema="identity",
    )


def downgrade() -> None:
    op.drop_table("oidc_logins", schema="identity")
    op.drop_index("ix_external_identities_user_id", table_name="external_identities", schema="identity")
    op.drop_table("external_identities", schema="identity")
