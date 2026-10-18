"""source-system connectors, contact fields and the contact matching weight

Revision ID: c3d5e7f9a1b2
Revises: b7e2c4d91a05
Create Date: 2026-10-18 00:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3d5e7f9a1b2'
down_revision: Union[str, Sequence[str], None] = 'b7e2c4d91a05'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('source_system', schema=None) as batch_op:
        batch_op.add_column(sa.Column('pull_url', sa.String(length=1000), nullable=True))
        batch_op.add_column(sa.Column('pull_kind', sa.String(length=10), nullable=True))
        batch_op.add_column(sa.Column('last_pull_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('last_pull_status', sa.String(length=500), nullable=True))

    with op.batch_alter_table('source_record', schema=None) as batch_op:
        batch_op.add_column(sa.Column('extracted_email', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('extracted_phone', sa.String(length=20), nullable=True))

    with op.batch_alter_table('business_entity', schema=None) as batch_op:
        batch_op.add_column(sa.Column('email', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('phone', sa.String(length=20), nullable=True))

    with op.batch_alter_table('matching_config', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('contact_weight', sa.Float(), server_default='0.06', nullable=False)
        )


def downgrade() -> None:
    with op.batch_alter_table('matching_config', schema=None) as batch_op:
        batch_op.drop_column('contact_weight')
    with op.batch_alter_table('business_entity', schema=None) as batch_op:
        batch_op.drop_column('phone')
        batch_op.drop_column('email')
    with op.batch_alter_table('source_record', schema=None) as batch_op:
        batch_op.drop_column('extracted_phone')
        batch_op.drop_column('extracted_email')
    with op.batch_alter_table('source_system', schema=None) as batch_op:
        batch_op.drop_column('last_pull_status')
        batch_op.drop_column('last_pull_at')
        batch_op.drop_column('pull_kind')
        batch_op.drop_column('pull_url')
