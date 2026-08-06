\set ON_ERROR_STOP on

BEGIN;

INSERT INTO collection_runs (
    execution_id,
    status,
    total_announcement_count,
    successful_announcement_count,
    failed_announcement_count,
    finished_at
)
VALUES (
    'rag_smoke_20260806',
    'success',
    1,
    1,
    0,
    now()
);

INSERT INTO announcements (
    collection_run_id,
    source_announcement_id,
    title,
    detail_url,
    region,
    announcement_date,
    publication_status
)
SELECT
    id,
    'RAG-SMOKE-001',
    'RAG schema smoke test',
    'https://example.test/notices/rag-1',
    'Seoul',
    DATE '2026-08-06',
    'open'
FROM collection_runs
WHERE execution_id = 'rag_smoke_20260806';

INSERT INTO documents (
    announcement_id,
    original_filename,
    document_format,
    storage_path,
    file_size_bytes,
    checksum_sha256,
    download_status
)
SELECT
    id,
    'rag_smoke.hwpx',
    'hwpx',
    '/tmp/rag_smoke.hwpx',
    1234,
    repeat('a', 64),
    'completed'
FROM announcements
WHERE source_announcement_id = 'RAG-SMOKE-001';

INSERT INTO processing_runs (
    document_id,
    execution_status,
    verification_status,
    current_stage,
    pipeline_version,
    output_root_path,
    exit_code,
    started_at,
    finished_at
)
SELECT
    id,
    'succeeded',
    'pass',
    'structure',
    '1.0.0',
    '/tmp/outputs/rag_smoke',
    0,
    now(),
    now()
FROM documents
WHERE original_filename = 'rag_smoke.hwpx';

INSERT INTO chunk_sets (
    processing_run_id,
    chunker_version,
    strategy,
    config,
    input_content_version,
    status,
    is_active,
    chunk_count,
    started_at,
    finished_at,
    activated_at
)
SELECT
    id,
    '1.1',
    'section_and_content_type',
    '{
        "max_tokens": 800,
        "overlap_tokens": 80,
        "table_strategy": "row_group"
    }'::jsonb,
    'structured-v1',
    'completed',
    true,
    1,
    now(),
    now(),
    now()
FROM processing_runs
WHERE output_root_path = '/tmp/outputs/rag_smoke';

INSERT INTO chunks (
    chunk_set_id,
    announcement_id,
    document_id,
    external_chunk_key,
    chunk_index,
    document_format,
    content_type,
    title,
    section_path,
    content,
    search_text,
    embedding_text,
    token_count,
    character_count,
    source_block_ids,
    source_page,
    source_reference,
    metadata,
    content_hash,
    status
)
SELECT
    cs.id,
    a.id,
    d.id,
    'rag_smoke_chunk_0000',
    0,
    'hwpx',
    'paragraph',
    'Eligibility',
    '["eligibility"]'::jsonb,
    'Adults and corporations residing domestically may apply.',
    'eligibility domestic adult corporation',
    'Eligibility Adults and corporations residing domestically may apply.',
    30,
    55,
    '["block_0821"]'::jsonb,
    8,
    '{"origin_path":["sections",0,"contents",0]}'::jsonb,
    '{}'::jsonb,
    repeat('b', 64),
    'completed'
FROM chunk_sets cs
JOIN processing_runs pr
    ON pr.id = cs.processing_run_id
JOIN documents d
    ON d.id = pr.document_id
JOIN announcements a
    ON a.id = d.announcement_id
WHERE pr.output_root_path = '/tmp/outputs/rag_smoke';

INSERT INTO embeddings (
    chunk_id,
    model_name,
    model_version,
    dimension,
    normalized,
    embedding_text_hash,
    embedding,
    status
)
SELECT
    id,
    'BAAI/bge-m3',
    'default',
    1024,
    true,
    repeat('c', 64),
    (
        '['
        || array_to_string(
            array_fill('0.03125'::text, ARRAY[1024]),
            ','
        )
        || ']'
    )::vector(1024),
    'completed'
FROM chunks
WHERE external_chunk_key = 'rag_smoke_chunk_0000';

SELECT
    (
        SELECT COUNT(*)
        FROM chunk_sets
        WHERE strategy = 'section_and_content_type'
    ) AS chunk_set_count,
    (
        SELECT COUNT(*)
        FROM chunks
        WHERE external_chunk_key = 'rag_smoke_chunk_0000'
    ) AS chunk_count,
    (
        SELECT COUNT(*)
        FROM embeddings e
        JOIN chunks c ON c.id = e.chunk_id
        WHERE c.external_chunk_key = 'rag_smoke_chunk_0000'
    ) AS embedding_count,
    (
        SELECT vector_dims(e.embedding)
        FROM embeddings e
        JOIN chunks c ON c.id = e.chunk_id
        WHERE c.external_chunk_key = 'rag_smoke_chunk_0000'
    ) AS vector_dimension,
    (
        SELECT round(vector_norm(e.embedding)::numeric, 6)
        FROM embeddings e
        JOIN chunks c ON c.id = e.chunk_id
        WHERE c.external_chunk_key = 'rag_smoke_chunk_0000'
    ) AS vector_norm;

DELETE FROM collection_runs
WHERE execution_id = 'rag_smoke_20260806';

SELECT
    (
        SELECT COUNT(*)
        FROM chunk_sets cs
        JOIN processing_runs pr ON pr.id = cs.processing_run_id
        WHERE pr.output_root_path = '/tmp/outputs/rag_smoke'
    ) AS chunk_set_count_after_delete,
    (
        SELECT COUNT(*)
        FROM chunks
        WHERE external_chunk_key = 'rag_smoke_chunk_0000'
    ) AS chunk_count_after_delete,
    (
        SELECT COUNT(*)
        FROM embeddings e
        JOIN chunks c ON c.id = e.chunk_id
        WHERE c.external_chunk_key = 'rag_smoke_chunk_0000'
    ) AS embedding_count_after_delete;

ROLLBACK;