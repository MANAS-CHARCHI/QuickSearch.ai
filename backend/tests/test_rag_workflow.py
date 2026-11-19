"""
Unit and Integration Tests for Embedding-Driven RAG Assistant using LangGraph & Claude Haiku.
"""
import asyncio
import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.services.rag_workflow import (
    embed_query_node,
    grade_and_format_context_node,
    retrieve_embeddings_node,
    should_generate_answer,
    run_assistant_rag,
    RAGState,
    MIN_RAG_SIMILARITY,
    RAG_TOP_K,
)
from app.services.vector_service import vector_service


def test_rag_threshold_constants():
    """Verify calibrated top_k=10 and MIN_RAG_SIMILARITY constants."""
    assert RAG_TOP_K == 10
    assert MIN_RAG_SIMILARITY == 0.05


@pytest.mark.asyncio
async def test_embed_query_node():
    state: RAGState = {"query": "What is my mutual fund portfolio?"}
    res = await embed_query_node(state)
    assert "query_embedding" in res
    vec = res["query_embedding"]
    assert len(vec) == 384
    # Vector is normalized
    norm = sum(x * x for x in vec) ** 0.5
    assert 0.99 <= norm <= 1.01


def test_grade_and_format_context_node():
    # 1. No chunks -> has_relevant_context = False
    state_empty: RAGState = {"retrieved_chunks": []}
    res_empty = asyncio.run(grade_and_format_context_node(state_empty))
    assert res_empty["has_relevant_context"] is False
    assert res_empty["context_text"] == ""
    assert should_generate_answer(res_empty) == "no_embeddings_fallback"

    # 2. Chunks present -> has_relevant_context = True
    chunks = [
        {
            "filename": "samco_holding.pdf",
            "page_number": 1,
            "similarity": 0.92,
            "content": "Samco Flexi Cap Fund has 92.57% in Indian equities.",
        }
    ]
    state_chunks: RAGState = {"retrieved_chunks": chunks}
    res_chunks = asyncio.run(grade_and_format_context_node(state_chunks))
    assert res_chunks["has_relevant_context"] is True
    assert "Samco Flexi Cap Fund" in res_chunks["context_text"]
    assert "Source: samco_holding.pdf" in res_chunks["context_text"]
    assert should_generate_answer(res_chunks) == "generate_haiku_answer"


@pytest.mark.asyncio
async def test_run_assistant_rag_empty_vault():
    from app.core.database import engine
    try:
        async with AsyncSessionLocal() as db:
            random_user_id = str(uuid.uuid4())
            res = await run_assistant_rag(
                query="What is my passport number?",
                user_id=random_user_id,
                db=db,
            )
            assert res["reply"]
            # Must state no data found with 0 tokens
            assert "No data found" in res["reply"]
            assert res["tokens_used"] == 0
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_run_assistant_rag_grounded_on_embeddings():
    from app.services.ingestion_service import _embed_chunk_text
    from app.models.file import FileDocument
    from app.models.user import User
    from app.core.database import engine
    from sqlalchemy import select

    try:
        async with AsyncSessionLocal() as db:
            user_res = await db.execute(select(User).limit(1))
            user = user_res.scalar_one_or_none()
            assert user is not None, "Test requires at least one existing User in DB"
            test_uid = user.id
            test_fid = uuid.uuid4()

            # Insert a verified document record
            doc = FileDocument(
                id=test_fid,
                user_id=test_uid,
                filename="aadhaar_card_scan.pdf",
                original_filename="aadhaar_card_scan.pdf",
                s3_key="vault-secured/aadhaar_dummy.pdf",
                file_size=1024,
                mime_type="application/pdf",
                sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                scan_status="indexed",
                document_type="Identity Document",
                category="Identity",
                description="Verified Aadhaar Card",
            )
            db.add(doc)
            await db.commit()

            # Insert 384-dim embedded chunk into pgvector
            chunk_text = "Name: Ramesh Patel Aadhaar Number: 4321 8765 2109"
            embedding = _embed_chunk_text(chunk_text, 384)

            await vector_service.upsert_chunks(
                db=db,
                file_id=test_fid,
                user_id=test_uid,
                chunks=[{
                    "chunk_index": 0,
                    "content": chunk_text,
                    "embedding": embedding,
                    "page_number": 1,
                }],
            )

            # 1. Ask question that exists in the embeddings
            res = await run_assistant_rag(
                query="Ramesh Patel Aadhaar Number 4321 8765 2109",
                user_id=str(test_uid),
                db=db,
            )

            assert res["reply"]
            # Specific details are formatted in backticks for copyability
            assert "4321 8765 2109" in res["reply"]
            assert "aadhaar_card_scan.pdf" in res.get("sources", [])
            assert res["tokens_used"] > 0

            # 2. Ask question for information not present in the embeddings
            low_sim_res = await run_assistant_rag(
                query="What was my total mutual fund equity dividend last year?",
                user_id=str(test_uid),
                db=db,
            )
            assert "No data found" in low_sim_res["reply"]

            # Clean up test records
            await vector_service.delete_file_chunks(db=db, file_id=test_fid, user_id=test_uid)
            await db.delete(doc)
            await db.commit()
    finally:
        await engine.dispose()
