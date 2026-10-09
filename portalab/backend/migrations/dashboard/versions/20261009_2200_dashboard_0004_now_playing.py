"""dashboard — « now playing » merged into « playing on the server » (027)

« playing on the server » shows everyone's streams (nobody named) or only the member's own: a member's
« now playing » becomes it, set to « mine » — or goes, when « playing on the server » is already there.

Revision ID: dashboard_0004
Revises: dashboard_0003
Create Date: 2026-10-09 22:00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "dashboard_0004"
down_revision: str | Sequence[str] | None = "dashboard_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM dashboard.widget_instances AS old
        WHERE old.widget_key = 'media.now_playing'
          AND EXISTS (
            SELECT 1 FROM dashboard.widget_instances AS kept
            WHERE kept.user_id = old.user_id AND kept.widget_key = 'media.server_playing'
          )
        """
    )
    op.execute(
        """
        UPDATE dashboard.widget_instances
        SET widget_key = 'media.server_playing',
            config = jsonb_build_object('scope', 'me') || (config - 'scope' - 'limit')
        WHERE widget_key = 'media.now_playing'
        """
    )


def downgrade() -> None:
    """The merge is kept (« now playing » no longer exists)."""
