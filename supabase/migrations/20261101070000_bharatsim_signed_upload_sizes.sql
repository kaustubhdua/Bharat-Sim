-- Record the expected size for direct-to-private-Storage APK uploads.
-- This allows the API to confirm the uploaded object matches the signed upload ticket.
ALTER TABLE bharatsim.runs
ADD COLUMN IF NOT EXISTS apk_size_bytes bigint;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'runs_apk_size_bytes_check'
          AND conrelid = 'bharatsim.runs'::regclass
    ) THEN
        ALTER TABLE bharatsim.runs
        ADD CONSTRAINT runs_apk_size_bytes_check
        CHECK (apk_size_bytes IS NULL OR apk_size_bytes BETWEEN 1 AND 157286400);
    END IF;
END
$$;
