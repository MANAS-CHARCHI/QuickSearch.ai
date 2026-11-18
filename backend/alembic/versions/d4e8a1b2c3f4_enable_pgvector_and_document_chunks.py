"""enable_pgvector_and_document_chunks

Revision ID: d4e8a1b2c3f4
Revises: c1f9b3e8d7a2
Create Date: 2026-11-18 07:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = 'd4e8a1b2c3f4'
down_revision: Union[str, Sequence[str], None] = 'c1f9b3e8d7a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Enable pgvector extension and create document_chunks table with HNSW cosine index."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        'document_chunks',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('file_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('page_number', sa.Integer(), nullable=False, server_default=sa.text('1')),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('embedding', Vector(384), nullable=False),
        sa.Column('metadata_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['file_id'], ['files.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('file_id', 'chunk_index', name='uq_document_chunks_file_chunk'),
    )
    op.create_index(op.f('ix_document_chunks_file_id'), 'document_chunks', ['file_id'], unique=False)
    op.create_index(op.f('ix_document_chunks_user_id'), 'document_chunks', ['user_id'], unique=False)
    op.create_index(
        'ix_document_chunks_embedding_hnsw',
        'document_chunks',
        ['embedding'],
        unique=False,
        postgresql_using='hnsw',
        postgresql_ops={'embedding': 'vector_cosine_ops'},
    )


def downgrade() -> None:
    """Drop document_chunks table and indexes."""
    op.drop_index('ix_document_chunks_embedding_hnsw', table_name='document_chunks')
    op.drop_index(op.f('ix_document_chunks_user_id'), table_name='document_chunks')
    op.drop_index(op.f('ix_document_chunks_file_id'), table_name='document_chunks')
    op.drop_table('document_chunks')
