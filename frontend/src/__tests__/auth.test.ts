import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const SESSION_KEY = "bharatsim.supabase.session";

async function loadAuth() {
  vi.stubEnv("VITE_SUPABASE_URL", "https://example.supabase.co");
  vi.stubEnv("VITE_SUPABASE_PUBLISHABLE_KEY", "sb_publishable_test");
  vi.resetModules();
  return import("../auth");
}

function sessionPayload(overrides: Record<string, unknown> = {}) {
  return {
    access_token: "access-token",
    refresh_token: "refresh-token",
    expires_in: 3600,
    expires_at: 1_893_456_000,
    token_type: "bearer",
    user: { id: "11111111-1111-4111-8111-111111111111", email: "test@example.com" },
    ...overrides,
  };
}

describe("Supabase browser authentication", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it("enters and exits public preview without creating an authenticated session", async () => {
    const auth = await loadAuth();

    expect(auth.isDemoMode()).toBe(false);
    auth.enterDemoMode();
    expect(auth.isDemoMode()).toBe(true);
    expect(auth.readSession()).toBeNull();

    auth.exitDemoMode();
    expect(auth.isDemoMode()).toBe(false);
    expect(auth.readSession()).toBeNull();
  });

  it("signs in with the publishable key and stores the returned session", async () => {
    const auth = await loadAuth();
    const payload = sessionPayload();
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => payload,
    });
    vi.stubGlobal("fetch", fetchMock);

    const session = await auth.signIn("test@example.com", "correct horse battery");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe("https://example.supabase.co/auth/v1/token?grant_type=password");
    expect(fetchMock.mock.calls[0][1].headers.apikey).toBe("sb_publishable_test");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      email: "test@example.com",
      password: "correct horse battery",
    });
    expect(session.access_token).toBe("access-token");
    expect(auth.readSession()).toEqual(session);
    expect(JSON.parse(sessionStorage.getItem(SESSION_KEY) || "{}").refresh_token).toBe("refresh-token");
  });

  it("handles email-confirmation signup without inventing a session", async () => {
    const auth = await loadAuth();
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ user: { id: "11111111-1111-4111-8111-111111111111" } }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(auth.signUp("new@example.com", "long-enough-password")).resolves.toBe(false);
    expect(auth.readSession()).toBeNull();
  });

  it("refreshes an expired session and persists the rotated tokens", async () => {
    const auth = await loadAuth();
    sessionStorage.setItem(SESSION_KEY, JSON.stringify({
      access_token: "old-access",
      refresh_token: "old-refresh",
      expires_at: 1,
      token_type: "bearer",
    }));
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => sessionPayload({ access_token: "new-access", refresh_token: "new-refresh" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const session = await auth.refreshSession();

    expect(fetchMock.mock.calls[0][0]).toBe("https://example.supabase.co/auth/v1/token?grant_type=refresh_token");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ refresh_token: "old-refresh" });
    expect(session.access_token).toBe("new-access");
    expect(auth.readSession()?.refresh_token).toBe("new-refresh");
  });

  it("clears the local session even when remote logout is unavailable", async () => {
    const auth = await loadAuth();
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(sessionPayload()));
    const fetchMock = vi.fn().mockRejectedValue(new TypeError("network unavailable"));
    vi.stubGlobal("fetch", fetchMock);

    await expect(auth.signOut()).resolves.toBeUndefined();

    expect(fetchMock.mock.calls[0][0]).toBe("https://example.supabase.co/auth/v1/logout");
    expect(fetchMock.mock.calls[0][1].headers.Authorization).toBe("Bearer access-token");
    expect(auth.readSession()).toBeNull();
  });
});
