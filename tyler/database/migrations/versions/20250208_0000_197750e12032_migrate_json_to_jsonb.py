"""migrate json to jsonb columns

Revision ID: 197750e12032
Revises: 197750e12031
Create Date: 2025-02-08 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '197750e12032'
down_revision = '197750e12031'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        # Table: threads
        op.alter_column('threads', 'attributes',
                   existing_type=sa.JSON(),
                   type_=postgresql.JSONB(astext_type=sa.Text()),
                   existing_nullable=False,
                   postgresql_using='attributes::jsonb')
        op.alter_column('threads', 'platforms',
                   existing_type=sa.JSON(),
                   type_=postgresql.JSONB(astext_type=sa.Text()),
                   existing_nullable=True,
                   postgresql_using='platforms::jsonb')

        # Table: messages
        op.alter_column('messages', 'tool_calls',
                   existing_type=sa.JSON(),
                   type_=postgresql.JSONB(astext_type=sa.Text()),
                   existing_nullable=True,
                   postgresql_using='tool_calls::jsonb')
        op.alter_column('messages', 'attributes',
                   existing_type=sa.JSON(),
                   type_=postgresql.JSONB(astext_type=sa.Text()),
                   existing_nullable=False,
                   postgresql_using='attributes::jsonb')
        op.alter_column('messages', 'attachments',
                   existing_type=sa.JSON(),
                   type_=postgresql.JSONB(astext_type=sa.Text()),
                   existing_nullable=True,
                   postgresql_using='attachments::jsonb')
        op.alter_column('messages', 'metrics',
                   existing_type=sa.JSON(),
                   type_=postgresql.JSONB(astext_type=sa.Text()),
                   existing_nullable=False,
                   postgresql_using='metrics::jsonb')
        op.alter_column('messages', 'platforms',
                   existing_type=sa.JSON(),
                   type_=postgresql.JSONB(astext_type=sa.Text()),
                   existing_nullable=True,
                   postgresql_using='platforms::jsonb')


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        # Table: messages
        op.alter_column('messages', 'platforms',
                   existing_type=postgresql.JSONB(astext_type=sa.Text()),
                   type_=sa.JSON(),
                   existing_nullable=True,
                   postgresql_using='platforms::text::json')
        op.alter_column('messages', 'metrics',
                   existing_type=postgresql.JSONB(astext_type=sa.Text()),
                   type_=sa.JSON(),
                   existing_nullable=False,
                   postgresql_using='metrics::text::json')
        op.alter_column('messages', 'attachments',
                   existing_type=postgresql.JSONB(astext_type=sa.Text()),
                   type_=sa.JSON(),
                   existing_nullable=True,
                   postgresql_using='attachments::text::json')
        op.alter_column('messages', 'attributes',
                   existing_type=postgresql.JSONB(astext_type=sa.Text()),
                   type_=sa.JSON(),
                   existing_nullable=False,
                   postgresql_using='attributes::text::json')
        op.alter_column('messages', 'tool_calls',
                   existing_type=postgresql.JSONB(astext_type=sa.Text()),
                   type_=sa.JSON(),
                   existing_nullable=True,
                   postgresql_using='tool_calls::text::json')

        # Table: threads
        op.alter_column('threads', 'platforms',
                   existing_type=postgresql.JSONB(astext_type=sa.Text()),
                   type_=sa.JSON(),
                   existing_nullable=True,
                   postgresql_using='platforms::text::json')
        op.alter_column('threads', 'attributes',
                   existing_type=postgresql.JSONB(astext_type=sa.Text()),
                   type_=sa.JSON(),
                   existing_nullable=False,
                   postgresql_using='attributes::text::json') 