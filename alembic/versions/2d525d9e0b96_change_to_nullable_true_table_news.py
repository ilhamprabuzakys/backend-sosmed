"""Change to nullable True table news

Revision ID: 2d525d9e0b96
Revises: 9eb05bae4d62
Create Date: 2024-06-18 16:13:30.940154

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2d525d9e0b96'
down_revision: Union[str, None] = '9eb05bae4d62'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###
