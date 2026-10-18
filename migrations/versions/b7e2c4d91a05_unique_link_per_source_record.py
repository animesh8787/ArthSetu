"""one link per source record

A record belongs to exactly one business. Concurrent matching runs could
previously link the same record twice; the unique index makes the database
refuse the second one.

Revision ID: b7e2c4d91a05
Revises: a1b2c3d4e5f6
Create Date: 2026-10-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'b7e2c4d91a05'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop duplicate links (oldest wins), then enforce uniqueness."""
    op.execute(
        """
        DELETE FROM entity_record_link WHERE id IN (
            SELECT id FROM (
                SELECT id, ROW_NUMBER() OVER (
                    PARTITION BY source_record_id ORDER BY created_at, id
                ) AS rn
                FROM entity_record_link
            ) ranked WHERE rn > 1
        )
        """
    )
    with op.batch_alter_table('entity_record_link', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_entity_record_link_source_record_id'))
        batch_op.create_index(
            batch_op.f('ix_entity_record_link_source_record_id'),
            ['source_record_id'],
            unique=True,
        )


def downgrade() -> None:
    with op.batch_alter_table('entity_record_link', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_entity_record_link_source_record_id'))
        batch_op.create_index(
            batch_op.f('ix_entity_record_link_source_record_id'),
            ['source_record_id'],
            unique=False,
        )
