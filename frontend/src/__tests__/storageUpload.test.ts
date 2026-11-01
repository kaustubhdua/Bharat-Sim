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
  tus_endpoint: "https://project.storage.supabase.co/storage/v1/upload/resumable/sign/bharatsim-private/runs/run-tus-123/input.apk",
  object_path: "runs/run-tus-123/input.apk",
  expires_in_seconds: 7200,
};

describe("resumable private APK uploads", () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.unstubAllGlobals();
  });

  it("creates a signed TUS session, uploads chunks and persists the resumable URL", async () => {
    const file = new File(["apk-binary-content"], "build.apk", {
      type: "application/vnd.android.package-archive",
      lastModified: 1234,
    });
    const sha256 = "a".repeat(64);
    savePendingApkUpload(sha256, file, ticket);
    const calls: Array<{ method: string; headers: HeadersInit | undefined; body?: BodyInit | null }> = [];

    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
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
    });
    expect(calls[1].headers).toMatchObject({
      "Tus-Resumable": "1.0.0",
      "Upload-Offset": "0",
      "Content-Type": "application/offset+octet-stream",
    });
    expect(progress.at(-1)).toBe(100);
    expect(getPendingApkUpload(sha256, file)).toMatchObject({ run_id: ticket.run_id });
  });

  it("resumes an existing upload from the server-confirmed offset without creating a new session", async () => {
    const file = new File(["apk-binary-content"], "build.apk", {
      type: "application/vnd.android.package-archive",
      lastModified: 1234,
    });
    const sha256 = "b".repeat(64);
    savePendingApkUpload(sha256, file, ticket);
    sessionStorage.setItem(
      Object.keys(sessionStorage).find(key => key.includes(sha256))!,
      JSON.stringify({
        ...JSON.parse(sessionStorage.getItem(Object.keys(sessionStorage).find(key => key.includes(sha256))!)!),
        upload_url: "https://project.storage.supabase.co/storage/v1/upload/resumable/session-123",
      }),
    );
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "HEAD") {
        return new Response(null, { status: 200, headers: { "Upload-Offset": "17" } });
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
