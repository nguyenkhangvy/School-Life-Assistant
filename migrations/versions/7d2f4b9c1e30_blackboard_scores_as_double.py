"""blackboard scores as double

Revision ID: 7d2f4b9c1e30
Revises: 25c0593b5109
Create Date: 2026-09-26 12:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7d2f4b9c1e30'
down_revision = '25c0593b5109'
branch_labels = None
depends_on = None


def upgrade():
    # MySQL FLOAT keeps about 7 digits; DOUBLE keeps the score exactly as Blackboard sent it.
    with op.batch_alter_table('school_bb_assignments', schema=None) as batch_op:
        batch_op.alter_column('points_possible', existing_type=sa.Float(), type_=sa.Double(), existing_nullable=True)
        batch_op.alter_column('score', existing_type=sa.Float(), type_=sa.Double(), existing_nullable=True)


def downgrade():
    with op.batch_alter_table('school_bb_assignments', schema=None) as batch_op:
        batch_op.alter_column('score', existing_type=sa.Double(), type_=sa.Float(), existing_nullable=True)
        batch_op.alter_column('points_possible', existing_type=sa.Double(), type_=sa.Float(), existing_nullable=True)
