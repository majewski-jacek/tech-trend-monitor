"""add_revoked_tokens_table

Revision ID: 8b2e93ce9739
Revises: 2b0254d11adf
Create Date: 2026-10-22 14:36:56.542431

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8b2e93ce9739'
down_revision: Union[str, Sequence[str], None] = '2b0254d11adf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'revoked_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('token', sa.String(length=500), nullable=False),
        sa.Column('jti', sa.String(length=64), nullable=True),
        sa.Column('revoked_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_revoked_tokens_id'), 'revoked_tokens', ['id'], unique=False)
    op.create_index(op.f('ix_revoked_tokens_token'), 'revoked_tokens', ['token'], unique=True)
    op.create_index(op.f('ix_revoked_tokens_jti'), 'revoked_tokens', ['jti'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_revoked_tokens_jti'), table_name='revoked_tokens')
    op.drop_index(op.f('ix_revoked_tokens_token'), table_name='revoked_tokens')
    op.drop_index(op.f('ix_revoked_tokens_id'), table_name='revoked_tokens')
    op.drop_table('revoked_tokens')
