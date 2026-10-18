"""switch user_account to Firebase identity (username+hashed_password -> firebase_uid, required unique email)

Revision ID: a1b2c3d4e5f6
Revises: 7c1d4e9a2f88
Create Date: 2026-09-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '7c1d4e9a2f88'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Deliberately wipes existing user_account rows: their hashed_password
    values are meaningless once Firebase is the identity source, and
    usernames aren't a stable key to carry over to email-based login.
    Every user (including the bootstrap admin) gets recreated in Firebase
    and re-provisioned locally after this migration runs: the bootstrap
    admin is re-created (or its existing Firebase account adopted) on the
    next start, other users need to be added again by that admin.
    """
    op.execute("DELETE FROM user_account")

    with op.batch_alter_table('user_account', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_user_account_username'))
        batch_op.drop_column('username')
        batch_op.drop_column('hashed_password')
        batch_op.add_column(sa.Column('firebase_uid', sa.String(length=128), nullable=False))
        batch_op.create_index(batch_op.f('ix_user_account_firebase_uid'), ['firebase_uid'], unique=True)
        batch_op.alter_column('email', existing_type=sa.String(length=255), nullable=False)
        batch_op.create_index(batch_op.f('ix_user_account_email'), ['email'], unique=True)


def downgrade() -> None:
    """Downgrade schema.

    Restores the old column shape only — cannot recover the deleted rows
    or their original passwords/usernames.
    """
    with op.batch_alter_table('user_account', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_user_account_email'))
        batch_op.alter_column('email', existing_type=sa.String(length=255), nullable=True)
        batch_op.drop_index(batch_op.f('ix_user_account_firebase_uid'))
        batch_op.drop_column('firebase_uid')
        # server_default so the downgrade also works if rows were added since the upgrade
        batch_op.add_column(sa.Column('hashed_password', sa.String(length=255), nullable=False, server_default=''))
        batch_op.add_column(sa.Column('username', sa.String(length=64), nullable=False, server_default=''))
        batch_op.create_index(batch_op.f('ix_user_account_username'), ['username'], unique=True)
