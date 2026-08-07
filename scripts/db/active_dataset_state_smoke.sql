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
    'active_state_smoke_20260806',
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
    'ACTIVE-STATE-SMOKE-001',
    'Active dataset state smoke test',
    'https://example.test/notices/active-state-1',
    'Seoul',
    DATE '2026-08-06',
    'open'
FROM collection_runs
WHERE execution_id = 'active_state_smoke_20260806';

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
    'active_state_smoke.hwpx',
    'hwpx',
    '/tmp/active_state_smoke.hwpx',
    1234,
    repeat('d', 64),
    'completed'
FROM announcements
WHERE source_announcement_id = 'ACTIVE-STATE-SMOKE-001';

INSERT INTO processing_runs (
    document_id,
    execution_status,
    verification_status,
    current_stage,
    pipeline_version,
    output_root_path,
    exit_code,
    started_at,
    finished_at,
    is_active,
    activated_at
)
SELECT
    id,
    'succeeded',
    'pass',
    'completed',
    '1.0.0',
    '/tmp/active_state_smoke/run-1',
    0,
    now(),
    now(),
    true,
    now()
FROM documents
WHERE original_filename = 'active_state_smoke.hwpx';

UPDATE system_state
SET
    active_collection_run_id = (
        SELECT id
        FROM collection_runs
        WHERE execution_id = 'active_state_smoke_20260806'
    ),
    updated_at = now()
WHERE id = 1;

SELECT
    ss.id AS system_state_id,
    cr.execution_id AS active_collection_run,
    pr.execution_status,
    pr.verification_status,
    pr.is_active,
    pr.activated_at IS NOT NULL AS has_activated_at
FROM system_state ss
JOIN collection_runs cr
    ON cr.id = ss.active_collection_run_id
JOIN announcements a
    ON a.collection_run_id = cr.id
JOIN documents d
    ON d.announcement_id = a.id
JOIN processing_runs pr
    ON pr.document_id = d.id
WHERE ss.id = 1;

DO $$
BEGIN
    BEGIN
        UPDATE processing_runs
        SET execution_status = 'failed'
        WHERE output_root_path = '/tmp/active_state_smoke/run-1';

        RAISE EXCEPTION
            'Expected active processing run check constraint violation';
    EXCEPTION
        WHEN check_violation THEN
            RAISE NOTICE
                'PASS: active run requires succeeded and pass status';
    END;
END
$$;

DO $$
DECLARE
    target_document_id integer;
BEGIN
    SELECT id
    INTO target_document_id
    FROM documents
    WHERE original_filename = 'active_state_smoke.hwpx';

    BEGIN
        INSERT INTO processing_runs (
            document_id,
            execution_status,
            verification_status,
            current_stage,
            pipeline_version,
            output_root_path,
            exit_code,
            started_at,
            finished_at,
            is_active,
            activated_at
        )
        VALUES (
            target_document_id,
            'succeeded',
            'pass',
            'completed',
            '1.0.1',
            '/tmp/active_state_smoke/run-2',
            0,
            now(),
            now(),
            true,
            now()
        );

        RAISE EXCEPTION
            'Expected one active run per document violation';
    EXCEPTION
        WHEN unique_violation THEN
            RAISE NOTICE
                'PASS: only one active processing run per document';
    END;
END
$$;

DO $$
BEGIN
    BEGIN
        DELETE FROM collection_runs
        WHERE execution_id = 'active_state_smoke_20260806';

        RAISE EXCEPTION
            'Expected active collection run delete restriction';
    EXCEPTION
        WHEN foreign_key_violation THEN
            RAISE NOTICE
                'PASS: active collection run cannot be deleted';
    END;
END
$$;

SELECT
    execution_status,
    verification_status,
    is_active
FROM processing_runs
WHERE output_root_path = '/tmp/active_state_smoke/run-1';

UPDATE system_state
SET
    active_collection_run_id = NULL,
    updated_at = now()
WHERE id = 1;

DELETE FROM collection_runs
WHERE execution_id = 'active_state_smoke_20260806';

SELECT
    (
        SELECT COUNT(*)
        FROM collection_runs
        WHERE execution_id = 'active_state_smoke_20260806'
    ) AS collection_run_count,
    (
        SELECT COUNT(*)
        FROM announcements
        WHERE source_announcement_id = 'ACTIVE-STATE-SMOKE-001'
    ) AS announcement_count,
    (
        SELECT COUNT(*)
        FROM documents
        WHERE original_filename = 'active_state_smoke.hwpx'
    ) AS document_count,
    (
        SELECT COUNT(*)
        FROM processing_runs
        WHERE output_root_path LIKE '/tmp/active_state_smoke/%'
    ) AS processing_run_count;

ROLLBACK;