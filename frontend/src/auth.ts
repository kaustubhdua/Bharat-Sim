const SUPABASE_URL = (import.meta.env.VITE_SUPABASE_URL || "").replace(/\/$/, "");
const SUPABASE_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY || "";
const SESSION_KEY = "bharatsim.supabase.session";

export type UserSession = {
  access_token: string;
  refresh_token: string;
  expires_at: number;
  token_type: string;
  user?: { id: string; email?: string };
};

export const authConfigured = Boolean(SUPABASE_URL && SUPABASE_KEY);

export function readSession(): UserSession | null {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as UserSession;
    return parsed.access_token && parsed.refresh_token ? parsed : null;
  } catch {
    return null;
  }
}

function saveSession(data: Record<string, unknown>): UserSession {
  const session: UserSession = {
    access_token: String(data.access_token || ""),
    refresh_token: String(data.refresh_token || ""),
    expires_at: Number(data.expires_at || (Math.floor(Date.now() / 1000) + Number(data.expires_in || 3600))),
    token_type: String(data.token_type || "bearer"),
    user: data.user as UserSession["user"],
  };
  if (!session.access_token || !session.refresh_token) throw new Error("Supabase did not return a complete session.");
  sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
  return session;
}

async function authRequest(path: string, body: Record<string, string>): Promise<Record<string, unknown>> {
  const response = await fetch(SUPABASE_URL + path, {
    method: "POST",
    headers: { "Content-Type": "application/json", apikey: SUPABASE_KEY },
    body: JSON.stringify(body),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = typeof payload.msg === "string" ? payload.msg : typeof payload.message === "string" ? payload.message : typeof payload.error_description === "string" ? payload.error_description : "Authentication request failed.";
    throw new Error(message);
  }
  return payload as Record<string, unknown>;
}

export async function signIn(email: string, password: string): Promise<UserSession> {
  return saveSession(await authRequest("/auth/v1/token?grant_type=password", { email, password }));
}

export async function signUp(email: string, password: string): Promise<boolean> {
  const payload = await authRequest("/auth/v1/signup", { email, password });
  if (payload.access_token && payload.refresh_token) {
    saveSession(payload);
    return true;
  }
  return false;
}

export async function refreshSession(): Promise<UserSession> {
  const current = readSession();
  if (!current?.refresh_token) throw new Error("Your session has expired. Please sign in again.");
  return saveSession(await authRequest("/auth/v1/token?grant_type=refresh_token", { refresh_token: current.refresh_token }));
}

export async function signOut(): Promise<void> {
  const current = readSession();
  try {
    if (current?.access_token) {
      await fetch(SUPABASE_URL + "/auth/v1/logout", {
        method: "POST",
        headers: { apikey: SUPABASE_KEY, Authorization: "Bearer " + current.access_token },
      }).catch(() => undefined);
    }
  } finally {
    // Local logout must complete even if the Auth server is temporarily unreachable.
    sessionStorage.removeItem(SESSION_KEY);
  }
}
