"""talent scalings and base stats

Revision ID: 978e3f8758a4
Revises: 43be42c2394d
Create Date: 2026-10-15 22:18:30.332279

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '978e3f8758a4'
down_revision: Union[str, Sequence[str], None] = '43be42c2394d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('talent_scalings',
    sa.Column('character_id', sa.Integer(), nullable=False),
    sa.Column('talent', sa.String(length=16), nullable=False),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('stat', sa.String(length=32), nullable=False),
    sa.Column('coef', sa.Float(), nullable=False),
    sa.ForeignKeyConstraint(['character_id'], ['characters.id'], name=op.f('fk_talent_scalings_character_id_characters'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('character_id', 'talent', 'kind', 'stat', name=op.f('pk_talent_scalings'))
    )
    with op.batch_alter_table('char_builds', schema=None) as batch_op:
        batch_op.add_column(sa.Column('talent_priority', sa.JSON(), server_default='[]', nullable=False))

    with op.batch_alter_table('characters', schema=None) as batch_op:
        batch_op.add_column(sa.Column('base_hp', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('base_atk', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('base_def', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('ascension_stat', sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column('ascension_value', sa.Float(), nullable=True))



def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('characters', schema=None) as batch_op:
        batch_op.drop_column('ascension_value')
        batch_op.drop_column('ascension_stat')
        batch_op.drop_column('base_def')
        batch_op.drop_column('base_atk')
        batch_op.drop_column('base_hp')

    with op.batch_alter_table('char_builds', schema=None) as batch_op:
        batch_op.drop_column('talent_priority')

    op.drop_table('talent_scalings')
