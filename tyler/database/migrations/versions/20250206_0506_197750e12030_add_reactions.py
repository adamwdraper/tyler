"""Add reactions to messages

Revision ID: 197750e12030
Revises: 197750e12029
Create Date: 2025-02-06 05:06:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '197750e12030'
down_revision = '197750e12029'
branch_labels = None
depends_on = None


def upgrade():
    # Add reactions column to messages table
    with op.batch_alter_table('messages', schema=None) as batch_op:
        batch_op.add_column(sa.Column('reactions', sa.JSON(), nullable=True))
    
    # SQLite doesn't support adding a JSON column with a default value directly,
    # so we update the table after adding the column to set empty objects
    if op.get_context().dialect.name == 'sqlite':
        op.execute("UPDATE messages SET reactions = '{}'")


def downgrade():
    # Remove reactions column from messages table
    with op.batch_alter_table('messages', schema=None) as batch_op:
        batch_op.drop_column('reactions') 