"""initial schema

Revision ID: 43be42c2394d
Revises: 
Create Date: 2026-10-15 21:50:43.416009

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '43be42c2394d'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('characters',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('key', sa.String(length=64), nullable=False),
    sa.Column('game_id', sa.Integer(), nullable=True),
    sa.Column('name', sa.String(length=64), nullable=False),
    sa.Column('element', sa.String(length=16), nullable=False),
    sa.Column('weapon_type', sa.String(length=16), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_characters')),
    sa.UniqueConstraint('game_id', name=op.f('uq_characters_game_id')),
    sa.UniqueConstraint('key', name=op.f('uq_characters_key'))
    )
    op.create_table('domains',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('key', sa.String(length=64), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_domains')),
    sa.UniqueConstraint('key', name=op.f('uq_domains_key'))
    )
    op.create_table('artifact_sets',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('key', sa.String(length=64), nullable=False),
    sa.Column('game_id', sa.Integer(), nullable=True),
    sa.Column('name', sa.String(length=128), nullable=False),
    sa.Column('domain_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['domain_id'], ['domains.id'], name=op.f('fk_artifact_sets_domain_id_domains')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_artifact_sets')),
    sa.UniqueConstraint('game_id', name=op.f('uq_artifact_sets_game_id')),
    sa.UniqueConstraint('key', name=op.f('uq_artifact_sets_key'))
    )
    op.create_table('char_builds',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('character_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=False),
    sa.Column('sands_main', sa.JSON(), nullable=False),
    sa.Column('goblet_main', sa.JSON(), nullable=False),
    sa.Column('circlet_main', sa.JSON(), nullable=False),
    sa.ForeignKeyConstraint(['character_id'], ['characters.id'], name=op.f('fk_char_builds_character_id_characters')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_char_builds'))
    )
    with op.batch_alter_table('char_builds', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_char_builds_character_id'), ['character_id'], unique=False)

    op.create_table('owned_characters',
    sa.Column('character_id', sa.Integer(), nullable=False),
    sa.Column('level', sa.Integer(), nullable=False),
    sa.Column('stats', sa.JSON(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    sa.ForeignKeyConstraint(['character_id'], ['characters.id'], name=op.f('fk_owned_characters_character_id_characters'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('character_id', name=op.f('pk_owned_characters'))
    )
    op.create_table('build_queue',
    sa.Column('character_id', sa.Integer(), nullable=False),
    sa.Column('build_id', sa.Integer(), nullable=True),
    sa.Column('priority', sa.Integer(), nullable=False),
    sa.Column('target_score', sa.Float(), nullable=False),
    sa.ForeignKeyConstraint(['build_id'], ['char_builds.id'], name=op.f('fk_build_queue_build_id_char_builds'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['character_id'], ['characters.id'], name=op.f('fk_build_queue_character_id_characters'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('character_id', name=op.f('pk_build_queue'))
    )
    op.create_table('build_sets',
    sa.Column('build_id', sa.Integer(), nullable=False),
    sa.Column('set_id', sa.Integer(), nullable=False),
    sa.Column('rank', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['build_id'], ['char_builds.id'], name=op.f('fk_build_sets_build_id_char_builds'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['set_id'], ['artifact_sets.id'], name=op.f('fk_build_sets_set_id_artifact_sets')),
    sa.PrimaryKeyConstraint('build_id', 'set_id', name=op.f('pk_build_sets'))
    )
    op.create_table('farm_sessions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('character_id', sa.Integer(), nullable=False),
    sa.Column('build_id', sa.Integer(), nullable=True),
    sa.Column('domain_id', sa.Integer(), nullable=False),
    sa.Column('started_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    sa.Column('ended_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['build_id'], ['char_builds.id'], name=op.f('fk_farm_sessions_build_id_char_builds'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['character_id'], ['characters.id'], name=op.f('fk_farm_sessions_character_id_characters')),
    sa.ForeignKeyConstraint(['domain_id'], ['domains.id'], name=op.f('fk_farm_sessions_domain_id_domains')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_farm_sessions'))
    )
    op.create_table('stat_weights',
    sa.Column('build_id', sa.Integer(), nullable=False),
    sa.Column('stat', sa.String(length=32), nullable=False),
    sa.Column('weight', sa.Float(), nullable=False),
    sa.ForeignKeyConstraint(['build_id'], ['char_builds.id'], name=op.f('fk_stat_weights_build_id_char_builds'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('build_id', 'stat', name=op.f('pk_stat_weights'))
    )
    op.create_table('artifacts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('set_id', sa.Integer(), nullable=False),
    sa.Column('slot', sa.String(length=16), nullable=False),
    sa.Column('main_stat', sa.String(length=32), nullable=False),
    sa.Column('level', sa.Integer(), nullable=False),
    sa.Column('rarity', sa.Integer(), nullable=False),
    sa.Column('obtained_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    sa.Column('source', sa.String(length=16), server_default='manual', nullable=False),
    sa.Column('equipped_by', sa.Integer(), nullable=True),
    sa.Column('session_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['equipped_by'], ['characters.id'], name=op.f('fk_artifacts_equipped_by_characters'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['session_id'], ['farm_sessions.id'], name=op.f('fk_artifacts_session_id_farm_sessions'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['set_id'], ['artifact_sets.id'], name=op.f('fk_artifacts_set_id_artifact_sets')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_artifacts'))
    )
    with op.batch_alter_table('artifacts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_artifacts_set_id'), ['set_id'], unique=False)

    op.create_table('resin_log',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('domain_id', sa.Integer(), nullable=False),
    sa.Column('resin_spent', sa.Integer(), nullable=False),
    sa.Column('condensed', sa.Boolean(), nullable=False),
    sa.Column('date', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    sa.Column('session_id', sa.Integer(), nullable=True),
    sa.Column('five_stars', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['domain_id'], ['domains.id'], name=op.f('fk_resin_log_domain_id_domains')),
    sa.ForeignKeyConstraint(['session_id'], ['farm_sessions.id'], name=op.f('fk_resin_log_session_id_farm_sessions'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_resin_log'))
    )
    op.create_table('artifact_substats',
    sa.Column('artifact_id', sa.Integer(), nullable=False),
    sa.Column('stat', sa.String(length=32), nullable=False),
    sa.Column('value', sa.Float(), nullable=False),
    sa.Column('active', sa.Boolean(), server_default=sa.true(), nullable=False),
    sa.ForeignKeyConstraint(['artifact_id'], ['artifacts.id'], name=op.f('fk_artifact_substats_artifact_id_artifacts'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('artifact_id', 'stat', name=op.f('pk_artifact_substats'))
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('artifact_substats')
    op.drop_table('resin_log')
    with op.batch_alter_table('artifacts', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_artifacts_set_id'))

    op.drop_table('artifacts')
    op.drop_table('stat_weights')
    op.drop_table('farm_sessions')
    op.drop_table('build_sets')
    op.drop_table('build_queue')
    op.drop_table('owned_characters')
    with op.batch_alter_table('char_builds', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_char_builds_character_id'))

    op.drop_table('char_builds')
    op.drop_table('artifact_sets')
    op.drop_table('domains')
    op.drop_table('characters')
