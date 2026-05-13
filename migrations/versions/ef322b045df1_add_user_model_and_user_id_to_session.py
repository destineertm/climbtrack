"""add user model and user_id to session

Revision ID: ef322b045df1
Revises: 66010c3dbb19
Create Date: 2026-05-13

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'ef322b045df1'
down_revision = '2a7a68d6b279'
branch_labels = None
depends_on = None


def upgrade():
    # Create user table
    op.create_table(
        'user',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=150), nullable=False),
        sa.Column('display_name', sa.String(length=100), nullable=False),
        sa.Column('password_hash', sa.String(length=256), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
    )

    # Add user_id to session
    with op.batch_alter_table('session', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_session_user_id', 'user', ['user_id'], ['id'])


def downgrade():
    with op.batch_alter_table('session', schema=None) as batch_op:
        batch_op.drop_constraint('fk_session_user_id', type_='foreignkey')
        batch_op.drop_column('user_id')

    op.drop_table('user')