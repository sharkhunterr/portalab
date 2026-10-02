"""authz initial schema — permission catalog, roles, groups, grants, assignments, Admin singleton (spec 003 T006)

Revision ID: authz_0001
Revises:
Create Date: 2026-10-01 20:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "authz_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("authz",)
depends_on: str | Sequence[str] | None = ("identity_0001",)

TZ = sa.DateTime(timezone=True)
ADMIN_ROLE_ID = "01900000-0000-7000-8000-00000000ad01"
BASE_ROLES = (
    ("01900000-0000-7000-8000-000000000001", "user", "User"),
    ("01900000-0000-7000-8000-000000000002", "support", "Support"),
    ("01900000-0000-7000-8000-000000000003", "moderator", "Moderator"),
    ("01900000-0000-7000-8000-000000000004", "editor", "Editor"),
    (ADMIN_ROLE_ID, "admin", "Admin"),
)

RESERVED_TRIGGER = f"""
CREATE OR REPLACE FUNCTION authz.reject_reserved_grant() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF (SELECT reserved FROM authz.permissions WHERE key = NEW.permission_key)
       AND NOT (NEW.holder_kind = 'role' AND NEW.holder_id = '{ADMIN_ROLE_ID}'::uuid) THEN
        RAISE EXCEPTION 'reserved permission % can only be held by the Admin role', NEW.permission_key
            USING ERRCODE = 'P0002';
    END IF;
    RETURN NEW;
END;
$$;
"""  # noqa: S608 — constant role id, no user input


def upgrade() -> None:
    op.execute('CREATE SCHEMA IF NOT EXISTS "authz"')
    op.create_table(
        "permissions",
        sa.Column("key", sa.String(128), nullable=False),
        sa.Column("description", sa.String(512), nullable=False),
        sa.Column("declared_by", sa.String(128), nullable=False),
        sa.Column("sensitive", sa.Boolean(), nullable=False),
        sa.Column("reserved", sa.Boolean(), nullable=False),
        sa.Column("requires_confirmation", sa.Boolean(), nullable=False),
        sa.Column("user_grantable", sa.Boolean(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("key", name="pk_permissions"),
        schema="authz",
    )
    op.create_table(
        "roles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("system", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_roles"),
        sa.UniqueConstraint("key", name="uq_roles_key"),
        sa.CheckConstraint("kind IN ('base', 'custom')", name="ck_roles_kind"),
        schema="authz",
    )
    op.create_table(
        "groups",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.String(512), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_groups"),
        sa.UniqueConstraint("key", name="uq_groups_key"),
        schema="authz",
    )
    op.create_table(
        "grants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("holder_kind", sa.String(8), nullable=False),
        sa.Column("holder_id", sa.Uuid(), nullable=False),
        sa.Column("permission_key", sa.String(128), nullable=False),
        sa.Column("effect", sa.String(8), nullable=False),
        sa.Column("scope_kind", sa.String(16), nullable=False),
        sa.Column("scope_ref", sa.String(128), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("created_by", sa.Uuid()),
        sa.Column("created_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_grants"),
        sa.ForeignKeyConstraint(
            ["permission_key"], ["authz.permissions.key"], name="fk_grants_permission_key_permissions"
        ),
        sa.UniqueConstraint(
            "holder_kind",
            "holder_id",
            "permission_key",
            "scope_kind",
            "scope_ref",
            name="uq_grants_holder_scope",
        ),
        sa.CheckConstraint("holder_kind IN ('role', 'group', 'user')", name="ck_grants_holder_kind"),
        sa.CheckConstraint("effect IN ('allow', 'deny')", name="ck_grants_effect"),
        sa.CheckConstraint(
            "scope_kind IN ('global', 'self', 'owned', 'module', 'service', 'plugin')",
            name="ck_grants_scope_kind",
        ),
        schema="authz",
    )
    op.create_index("ix_grants_holder", "grants", ["holder_kind", "holder_id"], schema="authz")
    op.execute(RESERVED_TRIGGER)
    op.execute(
        "CREATE TRIGGER grants_reserved BEFORE INSERT OR UPDATE ON authz.grants "
        "FOR EACH ROW EXECUTE FUNCTION authz.reject_reserved_grant()"
    )

    for table, column, target in (("user_roles", "role_id", "roles"), ("user_groups", "group_id", "groups")):
        op.create_table(
            table,
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column(column, sa.Uuid(), nullable=False),
            sa.Column("granted_by", sa.Uuid()),
            sa.Column("granted_at", TZ, nullable=False),
            sa.Column("revoked_at", TZ),
            sa.PrimaryKeyConstraint("id", name=f"pk_{table}"),
            sa.ForeignKeyConstraint(["user_id"], ["identity.users.id"], name=f"fk_{table}_user_id_users"),
            sa.ForeignKeyConstraint([column], [f"authz.{target}.id"], name=f"fk_{table}_{column}_{target}"),
            schema="authz",
        )
        op.create_index(f"ix_{table}_user_id", table, ["user_id"], schema="authz")
        op.create_index(
            f"uq_{table}_active",
            table,
            ["user_id", column],
            unique=True,
            schema="authz",
            postgresql_where=sa.text("revoked_at IS NULL"),
        )
    op.execute(
        "CREATE UNIQUE INDEX uq_user_roles_single_admin ON authz.user_roles ((true)) "
        f"WHERE role_id = '{ADMIN_ROLE_ID}' AND revoked_at IS NULL"
    )

    op.create_table(
        "admin_singleton",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("current_admin_user_id", sa.Uuid()),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_admin_singleton"),
        sa.ForeignKeyConstraint(
            ["current_admin_user_id"],
            ["identity.users.id"],
            name="fk_admin_singleton_current_admin_user_id_users",
        ),
        sa.CheckConstraint("id = 1", name="ck_admin_singleton_single_row"),
        schema="authz",
    )
    op.create_table(
        "confirmations",
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("principal_user_id", sa.Uuid(), nullable=False),
        sa.Column("permission_key", sa.String(128), nullable=False),
        sa.Column("resource_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", TZ, nullable=False),
        sa.Column("consumed_at", TZ),
        sa.PrimaryKeyConstraint("token_hash", name="pk_confirmations"),
        schema="authz",
    )
    op.create_index("ix_confirmations_expires_at", "confirmations", ["expires_at"], schema="authz")

    roles = sa.table(
        "roles",
        sa.column("id", sa.Uuid()),
        sa.column("key"),
        sa.column("name"),
        sa.column("kind"),
        sa.column("system"),
        schema="authz",
    )
    op.bulk_insert(
        roles,
        [
            {"id": rid, "key": key, "name": name, "kind": "base", "system": True}
            for rid, key, name in BASE_ROLES
        ],
    )
    op.execute("INSERT INTO authz.admin_singleton (id, current_admin_user_id, version) VALUES (1, NULL, 0)")


def downgrade() -> None:
    for table in (
        "confirmations",
        "admin_singleton",
        "user_groups",
        "user_roles",
        "grants",
        "groups",
        "roles",
        "permissions",
    ):
        op.drop_table(table, schema="authz")
    op.execute("DROP FUNCTION IF EXISTS authz.reject_reserved_grant()")
    op.execute('DROP SCHEMA IF EXISTS "authz"')
