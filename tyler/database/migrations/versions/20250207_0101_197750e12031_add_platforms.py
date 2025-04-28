"""add platforms

Revision ID: 197750e12031
Revises: 197750e12030
Create Date: 2024-05-07 01:01:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '197750e12031'
down_revision = '197750e12030'
branch_labels = None
depends_on = None


def upgrade():
    """
    Upgrade database schema to add platforms field to messages and threads.
    """
    # Add platforms column to messages table
    op.add_column('messages', sa.Column('platforms', sa.JSON(), nullable=True))
    
    # Add platforms column to threads table
    op.add_column('threads', sa.Column('platforms', sa.JSON(), nullable=True))
    
    # Copy data from source to platforms for threads (using SQL for efficiency)
    op.execute("""
    UPDATE threads 
    SET platforms = source 
    WHERE source IS NOT NULL
    """)
    
    # Drop the source column from threads
    op.drop_column('threads', 'source')


def downgrade():
    """
    Downgrade database schema to revert changes.
    """
    # Add source column back to threads
    op.add_column('threads', sa.Column('source', sa.JSON(), nullable=True))
    
    # Copy data from platforms to source (using SQL for efficiency)
    op.execute("""
    UPDATE threads 
    SET source = platforms 
    WHERE platforms IS NOT NULL
    """)
    
    # Drop the platforms column from threads
    op.drop_column('threads', 'platforms')
    
    # Drop platforms column from messages
    op.drop_column('messages', 'platforms') 