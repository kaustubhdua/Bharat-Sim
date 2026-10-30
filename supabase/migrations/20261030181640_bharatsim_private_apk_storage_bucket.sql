-- Private APK object bucket for BharatSim. The API/worker use server-side service-role
-- credentials; anon/authenticated clients receive no object policies for this bucket.
-- Do not make this bucket public or place the service-role key in the frontend.
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
    'bharatsim-private',
    'bharatsim-private',
    false,
    157286400,
    ARRAY[
        'application/vnd.android.package-archive',
        'application/zip',
        'application/octet-stream'
    ]::text[]
)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    public = false,
    file_size_limit = EXCLUDED.file_size_limit,
    allowed_mime_types = EXCLUDED.allowed_mime_types;
