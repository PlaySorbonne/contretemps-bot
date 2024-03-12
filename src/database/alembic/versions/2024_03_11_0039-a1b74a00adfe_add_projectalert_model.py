"""add ProjectAlert model

Revision ID: a1b74a00adfe
Revises: 15cc3db8cb54
Create Date: 2024-03-11 00:39:39.125456

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b74a00adfe'
down_revision: Union[str, None] = '15cc3db8cb54'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('project_alert',
    sa.Column('alert_id', sa.String(), nullable=False),
    sa.Column('project_id', sa.Integer(), nullable=False),
    sa.Column('channel_id', sa.String(), nullable=False),
    sa.Column('kind', sa.Integer(), nullable=False),
    sa.Column('last_update', sa.String(), nullable=True),
    sa.Column('frequency', sa.String(), nullable=True),
    sa.Column('template', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['project_id'], ['project.project_id'], ),
    sa.PrimaryKeyConstraint('alert_id', 'project_id')
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('project_alert')
    # ### end Alembic commands ###