import React, { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import "./Auth.css";

const AUTH_BASE = process.env.REACT_APP_AUTH_BASE || "http://127.0.0.1:8010";

export default function Auth({
  variant = "full",
  allowSignup = false,
  onSuccess,
}) {
  const [form, setForm] = useState({ username: "", password: "", remember: true });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [showPw, setShowPw] = useState(false);

  const navigate = useNavigate();
  const location = useLocation();

  const onChange = (k, v) => setForm((p) => ({ ...p, [k]: v }));

  // ---------- LOGIN HANDLER ----------
  async function handleLogin(e) {
    e.preventDefault();
    setErr("");

    if (!form.username || !form.password) {
      setErr("Please enter both username and password.");
      return;
    }

    setBusy(true);
    try {
      const body = new URLSearchParams();
      body.set("username", form.username);
      body.set("password", form.password);

      const res = await fetch(`${AUTH_BASE}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body,
      });

      if (!res.ok) {
        const msg = await res.json().catch(() => ({}));
        throw new Error(msg?.detail || "Login failed");
      }

      const data = await res.json();
      const storage = form.remember ? localStorage : sessionStorage;

      storage.setItem("access_token", data.access_token);
      storage.setItem("refresh_token", data.refresh_token);
      storage.setItem("token_type", data.token_type || "bearer");
      storage.setItem("auth_user", form.username);

      onSuccess?.({ username: form.username });
      const from = location.state?.from || "/dashboard";
      navigate(from, { replace: true });
    } catch (e2) {
      setErr(e2.message || "Authentication failed.");
    } finally {
      setBusy(false);
    }
  }

  const Wrap = variant === "full" ? FullWrap : React.Fragment;

  return (
    <Wrap>
      <section className="auth-page">
        <div className="auth-shell single">
          {/* ===== LOGIN CARD ===== */}
          <form className="auth-card wide" onSubmit={handleLogin} noValidate>
            <h1 className="auth-title">Sign in</h1>

            {/* Username Field */}
            <label className="auth-field">
              <span>Username <b aria-hidden="true">*</b></span>
              <input
                value={form.username}
                onChange={(e) => onChange("username", e.target.value)}
                placeholder="admin or user"
                autoComplete="username"
                required
              />
            </label>

            {/* Password Field */}
            <label className="auth-field">
              <span>Password <b aria-hidden="true">*</b></span>
              <div className="pw-row">
                <input
                  type={showPw ? "text" : "password"}
                  value={form.password}
                  onChange={(e) => onChange("password", e.target.value)}
                  placeholder="Enter password"
                  autoComplete="current-password"
                  required
                  minLength={6}
                />
                <button
                  type="button"
                  className="pw-toggle"
                  onClick={() => setShowPw((s) => !s)}
                >
                  {showPw ? "Hide" : "Show"}
                </button>
              </div>
            </label>

            {/* Remember + Forgot Row */}
            <div className="auth-row">
              <label className="auth-check">
                <input
                  type="checkbox"
                  checked={form.remember}
                  onChange={(e) => onChange("remember", e.target.checked)}
                />
                <span>Remember me</span>
              </label>
              <button type="button" className="link-btn">
                Forgot password?
              </button>
            </div>

            {/* Error */}
            {err && (
              <div className="auth-error" role="alert">
                {err}
              </div>
            )}

            {/* Submit */}
            <button className="auth-btn" disabled={busy} type="submit">
              {busy ? "Please wait…" : "Sign in"}
            </button>

            {/* Footer / Signup Option */}
            <div className="auth-switch">
              {allowSignup ? (
                <>Need access? Contact your administrator.</>
              ) : (
                <>No account? Ask an administrator to provision access.</>
              )}
            </div>
          </form>
        </div>
      </section>
    </Wrap>
  );
}

function FullWrap({ children }) {
  return <div className="auth-wrap--light">{children}</div>;
}
