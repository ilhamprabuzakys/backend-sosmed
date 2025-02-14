"""Commit

Revision ID: 04d009744842
Revises: d2d524f265c3
Create Date: 2024-06-19 12:00:51.888725

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '04d009744842'
down_revision: Union[str, None] = 'd2d524f265c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('crawler',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('url_latest', sa.Text(), nullable=False),
    sa.Column('url_search', sa.Text(), nullable=False),
    sa.Column('url_popular', sa.Text(), nullable=False),
    sa.Column('api', sa.Text(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('crawler')
    # ### end Alembic commands ###
