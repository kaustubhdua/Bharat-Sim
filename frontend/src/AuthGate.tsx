import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { Activity, ArrowRight, LoaderCircle, ShieldCheck } from "lucide-react";
import { authConfigured, readSession, refreshSession, signIn, signOut, signUp, type UserSession } from "./auth";

export default function AuthGate({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<UserSession | null>(() => authConfigured ? readSession() : null);
  const [checking, setChecking] = useState(authConfigured);
  const [signupMode, setSignupMode] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    if (!authConfigured) return;
    let active = true;
    const current = readSession();
    if (!current) { setChecking(false); return; }
    const renew = async () => {
      try {
        const next = current.expires_at * 1000 > Date.now() + 60_000 ? current : await refreshSession();
        if (active) setSession(next);
      } catch {
        if (active) setSession(null);
      } finally {
        if (active) setChecking(false);
      }
    };
    void renew();
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!session) return;
    const delay = Math.max(5_000, session.expires_at * 1000 - Date.now() - 60_000);
    const timer = window.setTimeout(async () => {
      try { setSession(await refreshSession()); }
      catch { setSession(null); setError("Your session expired. Please sign in again."); }
    }, delay);
    return () => window.clearTimeout(timer);
  }, [session]);

  if (!authConfigured) return <>{children}</>;
  if (checking) return <div className="auth-screen"><LoaderCircle className="auth-spin" /><p>Restoring secure session…</p></div>;

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true); setError(""); setNotice("");
    try {
      if (signupMode) {
        const created = await signUp(email.trim(), password);
        if (created) setSession(readSession());
        else { setNotice("Account created. Check your email to confirm it, then sign in."); setSignupMode(false); }
      } else {
        setSession(await signIn(email.trim(), password));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed.");
    } finally { setBusy(false); }
  }

  async function logout() {
    await signOut();
    setSession(null);
    setPassword("");
  }

  if (!session) return (
    <main className="auth-screen">
      <section className="auth-card">
        <div className="auth-brand"><span><Activity size={22} /></span><div><b>BharatSim</b><small>THE CHEAP PHONE TEST</small></div></div>
        <div className="auth-eyebrow"><ShieldCheck size={14} /> SECURE WORKSPACE</div>
        <h1>{signupMode ? "Create your workspace access." : "Welcome back."}</h1>
        <p className="auth-copy">Sign in to access your Android resilience runs and private analysis reports.</p>
        <form onSubmit={submit}>
          <label htmlFor="auth-email">Email address</label>
          <input id="auth-email" type="email" autoComplete="email" required value={email} onChange={e => setEmail(e.target.value)} />
          <label htmlFor="auth-password">Password</label>
          <input id="auth-password" type="password" autoComplete={signupMode ? "new-password" : "current-password"} minLength={8} required value={password} onChange={e => setPassword(e.target.value)} />
          {error && <div className="auth-error" role="alert">{error}</div>}
          {notice && <div className="auth-notice" role="status">{notice}</div>}
          <button className="auth-submit" disabled={busy}>{busy ? <LoaderCircle className="auth-spin" size={17} /> : <>{signupMode ? "Create account" : "Sign in"} <ArrowRight size={16} /></>}</button>
        </form>
        <button className="auth-switch" onClick={() => { setSignupMode(!signupMode); setError(""); setNotice(""); }}>{signupMode ? "Already have an account? Sign in" : "New to BharatSim? Create an account"}</button>
        <small className="auth-foot">Your session is kept in this browser tab and refreshed before expiry. Never share your password or access token.</small>
      </section>
    </main>
  );

  return <><div className="auth-session-bar"><span><ShieldCheck size={14} /> Signed in{session.user?.email ? " · " + session.user.email : ""}</span><button onClick={() => void logout()}>Sign out</button></div>{children}</>;
}
