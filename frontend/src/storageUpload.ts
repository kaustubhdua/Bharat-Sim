export type SignedApkUploadTicket = {
  run_id: string;
  upload_token: string;
  tus_endpoint: string;
  object_path: string;
  expires_in_seconds: number;
};

type PendingUpload = SignedApkUploadTicket & {
  file_size: number;
  file_last_modified: number;
  expires_at: number;
  upload_url?: string;
};

const STORAGE_KEY_PREFIX = "bharatsim.pending-apk-upload.v1.";
const TUS_VERSION = "1.0.0";
const CHUNK_SIZE = 6 * 1024 * 1024;
const RETRY_DELAYS = [0, 1000, 2000, 4000, 8000, 15000];

function storageKey(sha256: string): string {
  return STORAGE_KEY_PREFIX + sha256;
}

function readPending(sha256: string): PendingUpload | null {
  try {
    const raw = sessionStorage.getItem(storageKey(sha256));
    if (!raw) return null;
    const value = JSON.parse(raw) as PendingUpload;
    if (
      !value.run_id ||
      !value.upload_token ||
      !value.tus_endpoint ||
      !value.object_path ||
      !Number.isFinite(value.expires_at) ||
      value.expires_at <= Date.now()
    ) {
      sessionStorage.removeItem(storageKey(sha256));
      return null;
    }
    return value;
  } catch {
    return null;
  }
}

export function getPendingApkUpload(sha256: string, file: File): SignedApkUploadTicket | null {
  const pending = readPending(sha256);
  if (!pending || pending.file_size !== file.size || pending.file_last_modified !== file.lastModified) {
    return null;
  }
  return pending;
}

export function savePendingApkUpload(sha256: string, file: File, ticket: SignedApkUploadTicket): void {
  const pending: PendingUpload = {
    ...ticket,
    file_size: file.size,
    file_last_modified: file.lastModified,
    expires_at: Date.now() + Math.min(ticket.expires_in_seconds, 7200) * 1000,
  };
  sessionStorage.setItem(storageKey(sha256), JSON.stringify(pending));
}

export function clearPendingApkUpload(sha256: string): void {
  sessionStorage.removeItem(storageKey(sha256));
}

function updatePendingUploadUrl(sha256: string, uploadUrl: string): void {
  const pending = readPending(sha256);
  if (!pending) return;
  pending.upload_url = uploadUrl;
  // Supabase TUS session URLs remain valid for up to 24 hours after creation.
  pending.expires_at = Date.now() + 24 * 60 * 60 * 1000;
  sessionStorage.setItem(storageKey(sha256), JSON.stringify(pending));
}

function encodeMetadata(value: string): string {
  return btoa(value);
}

function metadataHeader(file: File, objectPath: string): string {
  return [
    "bucketName " + encodeMetadata("bharatsim-private"),
    "objectName " + encodeMetadata(objectPath),
    "contentType " + encodeMetadata(file.type || "application/vnd.android.package-archive"),
    "cacheControl " + encodeMetadata("3600"),
  ].join(",");
}

function sleep(milliseconds: number): Promise<void> {
  return new Promise(resolve => window.setTimeout(resolve, milliseconds));
}

async function createTusUpload(file: File, sha256: string, ticket: SignedApkUploadTicket): Promise<string> {
  const response = await fetch(ticket.tus_endpoint, {
    method: "POST",
    headers: {
      "Tus-Resumable": TUS_VERSION,
      "Upload-Length": String(file.size),
      "Upload-Metadata": metadataHeader(file, ticket.object_path),
      "x-signature": ticket.upload_token,
    },
  });
  if (response.status !== 201) {
    throw new Error("Could not start resumable private upload (" + response.status + ").");
  }
  const location = response.headers.get("Location");
  if (!location) {
    throw new Error("Storage did not return a resumable upload location. Check Storage CORS expose headers.");
  }
  const uploadUrl = new URL(location, ticket.tus_endpoint).toString();
  updatePendingUploadUrl(sha256, uploadUrl);
  return uploadUrl;
}

async function getUploadOffset(uploadUrl: string, token: string): Promise<number> {
  const response = await fetch(uploadUrl, {
    method: "HEAD",
    headers: {
      "Tus-Resumable": TUS_VERSION,
    },
  });
  if (!response.ok) {
    throw new Error("Could not resume the private upload (" + response.status + ").");
  }
  const offset = Number(response.headers.get("Upload-Offset"));
  if (!Number.isSafeInteger(offset) || offset < 0) {
    throw new Error("Storage returned an invalid resumable upload offset.");
  }
  return offset;
}

export async function uploadApkResumable(
  file: File,
  sha256: string,
  ticket: SignedApkUploadTicket,
  onProgress: (percentage: number) => void,
): Promise<void> {
  const pending = readPending(sha256);
  let uploadUrl = pending?.run_id === ticket.run_id ? pending.upload_url : undefined;
  let offset = 0;

  if (uploadUrl) {
    try {
      offset = await getUploadOffset(uploadUrl, ticket.upload_token);
    } catch {
      uploadUrl = undefined;
    }
  }

  if (!uploadUrl) {
    uploadUrl = await createTusUpload(file, sha256, ticket);
    offset = 0;
  }

  if (offset > file.size) {
    throw new Error("Storage upload offset exceeds the selected APK size.");
  }

  onProgress(file.size === 0 ? 100 : Math.round((offset / file.size) * 100));

  while (offset < file.size) {
    const chunk = file.slice(offset, Math.min(offset + CHUNK_SIZE, file.size));
    let completed = false;
    let lastError: unknown;

    for (let attempt = 0; attempt < RETRY_DELAYS.length; attempt += 1) {
      if (RETRY_DELAYS[attempt]) await sleep(RETRY_DELAYS[attempt]);
      try {
        const response = await fetch(uploadUrl, {
          method: "PATCH",
          headers: {
            "Tus-Resumable": TUS_VERSION,
            "Upload-Offset": String(offset),
            "Content-Type": "application/offset+octet-stream",
          },
          body: chunk,
        });
        if (response.status === 204) {
          const nextOffset = Number(response.headers.get("Upload-Offset"));
          if (!Number.isSafeInteger(nextOffset) || nextOffset !== offset + chunk.size) {
            throw new Error("Storage returned an unexpected upload offset.");
          }
          offset = nextOffset;
          completed = true;
          onProgress(Math.min(100, Math.round((offset / file.size) * 100)));
          break;
        }
        if (response.status === 409 || response.status >= 500 || response.status === 429) {
          offset = await getUploadOffset(uploadUrl, ticket.upload_token);
          if (offset >= file.size) {
            completed = true;
            onProgress(100);
            break;
          }
          lastError = new Error("Temporary Storage upload response (" + response.status + ").");
          continue;
        }
        throw new Error("Private APK upload failed (" + response.status + ").");
      } catch (error) {
        lastError = error;
        try {
          offset = await getUploadOffset(uploadUrl, ticket.upload_token);
          if (offset >= file.size) {
            completed = true;
            onProgress(100);
            break;
          }
        } catch {
          // A dropped connection can make both PATCH and HEAD fail; retry the same offset.
        }
      }
    }

    if (!completed) {
      throw lastError instanceof Error
        ? new Error("Upload paused after a network interruption. Select the same APK again to resume. " + lastError.message)
        : new Error("Upload paused after repeated network interruptions. Select the same APK again to resume.");
    }
  }

  onProgress(100);
}
