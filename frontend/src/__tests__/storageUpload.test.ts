import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  getPendingApkUpload,
  savePendingApkUpload,
  uploadApkResumable,
  type SignedApkUploadTicket,
} from "../storageUpload";

const ticket: SignedApkUploadTicket = {
  run_id: "run-tus-123",
  upload_token: "signed-upload-token-abcdefghijklmnopqrstuvwxyz",
  tus_endpoint: "https://project.storage.supabase.co/storage/v1/upload/resumable",
  object_path: "runs/run-tus-123/input.apk",
  expires_in_seconds: 7200,
};

describe("resumable private APK uploads", () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
    // Keep the trusted Storage host deterministic even when Vercel injects
    // production VITE_SUPABASE_URL into the build-time test process.
    vi.stubEnv("VITE_SUPABASE_URL", "https://project.supabase.co");
    vi.stubEnv("VITE_SUPABASE_PUBLISHABLE_KEY", "sb_publishable_test_key");
  });

  it("creates a signed TUS session, uploads chunks and persists the resumable URL", async () => {
    const file = new File(["apk-binary-content"], "build.apk", {
      type: "application/vnd.android.package-archive",
      lastModified: 1234,
    });
    const sha256 = "a".repeat(64);
    savePendingApkUpload(sha256, file, ticket);
    const calls: Array<{ method: string; headers: HeadersInit | undefined; body?: BodyInit | null }> = [];

    const fetchMock = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      const method = init?.method || "GET";
      calls.push({ method, headers: init?.headers, body: init?.body });
      if (method === "POST") {
        return new Response(null, {
          status: 201,
          headers: { Location: "https://project.storage.supabase.co/storage/v1/upload/resumable/session-123" },
        });
      }
      if (method === "PATCH") {
        return new Response(null, {
          status: 204,
          headers: { "Upload-Offset": String(file.size) },
        });
      }
      if (method === "HEAD") {
        return new Response(null, {
          status: 200,
          headers: { "Upload-Offset": "0" },
        });
      }
      throw new Error("Unexpected method " + method);
    });
    vi.stubGlobal("fetch", fetchMock);
    const progress: number[] = [];

    await uploadApkResumable(file, sha256, ticket, value => progress.push(value));

    expect(calls.map(call => call.method)).toEqual(["POST", "PATCH"]);
    expect(calls[0].headers).toMatchObject({
      "Tus-Resumable": "1.0.0",
      "Upload-Length": String(file.size),
      "x-signature": ticket.upload_token,
      apikey: "sb_publishable_test_key",
    });
    expect(calls[1].headers).toMatchObject({
      "Tus-Resumable": "1.0.0",
      "Upload-Offset": "0",
      "Content-Type": "application/offset+octet-stream",
      apikey: "sb_publishable_test_key",
    });
    expect(progress.at(-1)).toBe(100);
    expect(getPendingApkUpload(sha256, file)).toMatchObject({ run_id: ticket.run_id });
  });

  it("rejects a tampered resumable URL before sending APK bytes", () => {
    const file = new File(["apk-binary-content"], "build.apk", {
      type: "application/vnd.android.package-archive",
      lastModified: 1234,
    });
    const sha256 = "c".repeat(64);
    savePendingApkUpload(sha256, file, ticket);
    const key = "bharatsim.pending-apk-upload.v1." + sha256;
    const pending = JSON.parse(sessionStorage.getItem(key)!);
    pending.upload_url = "https://attacker.example/collect";
    sessionStorage.setItem(key, JSON.stringify(pending));

    expect(getPendingApkUpload(sha256, file)).toBeNull();
  });

  it("requests a fresh ticket when the persisted TUS session has expired", async () => {
    const file = new File(["apk-binary-content"], "build.apk", {
      type: "application/vnd.android.package-archive",
      lastModified: 1234,
    });
    const sha256 = "d".repeat(64);
    savePendingApkUpload(sha256, file, ticket);
    const pendingKey = "bharatsim.pending-apk-upload.v1." + sha256;
    sessionStorage.setItem(pendingKey, JSON.stringify({
      ...JSON.parse(sessionStorage.getItem(pendingKey)!),
      upload_url: "https://project.storage.supabase.co/storage/v1/upload/resumable/session-expired",
    }));
    vi.stubGlobal("fetch", vi.fn(async () => new Response(null, { status: 410 })));

    await expect(uploadApkResumable(file, sha256, ticket, () => undefined))
      .rejects.toThrow("fresh upload ticket");
  });

  it("resumes an existing upload from the server-confirmed offset without creating a new session", async () => {
    const file = new File(["apk-binary-content"], "build.apk", {
      type: "application/vnd.android.package-archive",
      lastModified: 1234,
    });
    const sha256 = "b".repeat(64);
    savePendingApkUpload(sha256, file, ticket);
    const pendingKey = "bharatsim.pending-apk-upload.v1." + sha256;
    sessionStorage.setItem(
      pendingKey,
      JSON.stringify({
        ...JSON.parse(sessionStorage.getItem(pendingKey)!),
        upload_url: "https://project.storage.supabase.co/storage/v1/upload/resumable/session-123",
      }),
    );
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "HEAD") {
        return new Response(null, { status: 200, headers: { "Upload-Offset": String(file.size) } });
      }
      throw new Error("A completed upload should not need another request.");
    });
    vi.stubGlobal("fetch", fetchMock);
    const progress: number[] = [];

    await uploadApkResumable(file, sha256, ticket, value => progress.push(value));

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][1]?.method).toBe("HEAD");
    expect(progress.at(-1)).toBe(100);
  });
});
