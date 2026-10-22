import { useState } from "react";
import { api } from "./api.js";

function CutDemo() {
  return (
    <div className="demo" aria-label="A long link being cut down to a short one">
      <p className="demo-long">
        <span>https://shop.example.com/</span>
        <span className="demo-cut">collections/mens/running-shoes/trail?color=blue&size=42&utm_source=newsletter&utm_campaign=autumn-sale</span>
      </p>
      <span className="demo-slash" aria-hidden="true" />
      <p className="demo-short">kata.link/<b>x7Kp2Qa</b></p>
    </div>
  );
}

export default function Landing({ onAuth }) {
  const [mode, setMode] = useState("register");
  const [form, setForm] = useState({ name: "", email: "", password: "", confirm_password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const data = mode === "register" ? await api.register(form) : await api.login({ email: form.email, password: form.password });
      onAuth(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const isRegister = mode === "register";

  return (
    <main className="landing">
      <section className="hero">
        <p className="brand">Kata</p>
        <h1>Long links, cut short.</h1>
        <p className="lead">Make a short link in seconds, choose your own name for it, and see how many people click, from where, on what.</p>
        <CutDemo />
      </section>

      <section className="auth" aria-labelledby="auth-title">
        <h2 id="auth-title">{isRegister ? "Create your account" : "Welcome back"}</h2>
        <form onSubmit={submit}>
          {isRegister && (
            <label>Name<input value={form.name} onChange={set("name")} autoComplete="name" required /></label>
          )}
          <label>Email<input type="email" value={form.email} onChange={set("email")} autoComplete="email" required /></label>
          <label>Password<input type="password" value={form.password} onChange={set("password")} minLength={8}
            autoComplete={isRegister ? "new-password" : "current-password"} required />
            {isRegister && <small>At least 8 characters</small>}
          </label>
          {isRegister && (
            <label>Confirm password<input type="password" value={form.confirm_password} onChange={set("confirm_password")} autoComplete="new-password" required /></label>
          )}
          {error && <p className="error" role="alert">{error}</p>}
          <button className="btn primary" disabled={busy}>{busy ? "One moment…" : isRegister ? "Create account" : "Sign in"}</button>
        </form>
        <p className="switch">
          {isRegister ? "Already have an account?" : "New to Kata?"}{" "}
          <button className="link" onClick={() => { setMode(isRegister ? "login" : "register"); setError(""); }}>
            {isRegister ? "Sign in" : "Create an account"}
          </button>
        </p>
      </section>
    </main>
  );
}
