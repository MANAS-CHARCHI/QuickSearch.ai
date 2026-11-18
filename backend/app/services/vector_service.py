import uuid
from typing import Any, Dict, List, Optional, Sequence
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document_chunk import DocumentChunk


class PgVectorService:
    """PostgreSQL pgvector service for tenant-isolated vector storage and similarity search."""

    async def ping(self, db: AsyncSession) -> bool:
        """Verify that the pgvector extension is installed and active in PostgreSQL."""
        try:
            res = await db.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
            )
            return res.scalar_one_or_none() == 1
        except Exception:
            return False

    async def upsert_chunks(
        self,
        db: AsyncSession,
        file_id: uuid.UUID,
        user_id: uuid.UUID,
        chunks: Sequence[Dict[str, Any]],
    ) -> int:
        """
        Idempotently replace all chunks and embeddings for a file in PostgreSQL.
        Each chunk dict must contain: chunk_index, content, embedding, and optionally
        page_number and metadata_json.
        """
        await db.execute(
            delete(DocumentChunk).where(
                DocumentChunk.file_id == file_id,
                DocumentChunk.user_id == user_id,
            )
        )

        records = [
            DocumentChunk(
                id=uuid.uuid4(),
                file_id=file_id,
                user_id=user_id,
                chunk_index=chunk["chunk_index"],
                page_number=chunk.get("page_number", 1),
                content=chunk["content"],
                embedding=chunk["embedding"],
                metadata_json=chunk.get("metadata_json"),
            )
            for chunk in chunks
        ]
        db.add_all(records)
        await db.commit()
        return len(records)

    async def search_similar(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        query_embedding: List[float],
        top_k: int = 5,
        file_ids: Optional[List[uuid.UUID]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Perform strict per-user cosine similarity search using pgvector HNSW index.
        """
        distance_expr = DocumentChunk.embedding.cosine_distance(query_embedding).label("distance")
        stmt = (
            select(DocumentChunk, distance_expr)
            .where(DocumentChunk.user_id == user_id)
            .order_by(distance_expr)
            .limit(top_k)
        )
        if file_ids:
            stmt = stmt.where(DocumentChunk.file_id.in_(file_ids))

        result = await db.execute(stmt)
        rows = result.all()

        return [
            {
                "id": str(chunk.id),
                "file_id": str(chunk.file_id),
                "chunk_index": chunk.chunk_index,
                "page_number": chunk.page_number,
                "content": chunk.content,
                "metadata": chunk.metadata_json or {},
                "similarity": round(max(0.0, 1.0 - float(distance)), 6),
            }
            for chunk, distance in rows
        ]

    async def delete_file_chunks(
        self,
        db: AsyncSession,
        file_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """Delete all vector chunks belonging to a specific user's file."""
        await db.execute(
            delete(DocumentChunk).where(
                DocumentChunk.file_id == file_id,
                DocumentChunk.user_id == user_id,
            )
        )
        await db.commit()


vector_service = PgVectorService()
