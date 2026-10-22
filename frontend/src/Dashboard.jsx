import { useCallback, useEffect, useState } from "react";
import { api } from "./api.js";

const host = (u) => { try { return new URL(u).host; } catch { return u; } };
const shortDate = (d) => new Date(d).toLocaleDateString(undefined, { month: "short", day: "numeric" });

function status(link) {
  if (!link.is_active) return { text: "Paused", cls: "off" };
  if (link.expires_at && new Date(link.expires_at) <= new Date()) return { text: "Expired", cls: "off" };
  return { text: "Live", cls: "on" };
}

function CreateForm({ onCreated }) {
  const empty = { original_url: "", custom_code: "", title: "", expires: "" };
  const [f, setF] = useState(empty);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const link = await api.createLink({
        original_url: f.original_url.trim(),
        custom_code: f.custom_code.trim() || null,
        title: f.title.trim() || null,
        expires_at: f.expires ? new Date(f.expires + "T23:59:59").toISOString() : null,
      });
      setF(empty);
      onCreated(link);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="create" onSubmit={submit}>
      <label className="grow">Paste a long link
        <input type="url" placeholder="https://" value={f.original_url} onChange={set("original_url")} required />
      </label>
      <label>Custom name <span className="opt">(optional)</span>
        <input placeholder="summer-sale" value={f.custom_code} onChange={set("custom_code")} />
      </label>
      <label>Label <span className="opt">(optional)</span>
        <input placeholder="Autumn campaign" value={f.title} onChange={set("title")} />
      </label>
      <label>Expires <span className="opt">(optional)</span>
        <input type="date" value={f.expires} onChange={set("expires")} min={new Date().toISOString().slice(0, 10)} />
      </label>
      <button className="btn primary" disabled={busy}>{busy ? "Cutting…" : "Shorten link"}</button>
      {error && <p className="error full" role="alert">{error}</p>}
    </form>
  );
}

function Bars({ data }) {
  const max = Math.max(1, ...data.map((d) => d.clicks));
  const w = 100 / data.length;
  return (
    <svg className="chart" viewBox="0 0 100 40" preserveAspectRatio="none" role="img"
      aria-label={`Clicks per day, last ${data.length} days`}>
      {data.map((d, i) => {
        const h = (d.clicks / max) * 36;
        return (
          <rect key={d.date} x={i * w + w * 0.15} y={40 - Math.max(h, d.clicks ? 1 : 0.6)} width={w * 0.7}
            height={Math.max(h, d.clicks ? 1 : 0.6)} className={d.clicks ? "bar" : "bar zero"}>
            <title>{`${shortDate(d.date)}: ${d.clicks} click${d.clicks === 1 ? "" : "s"}`}</title>
          </rect>
        );
      })}
    </svg>
  );
}

function Breakdown({ title, rows, total }) {
  return (
    <div className="breakdown">
      <h4>{title}</h4>
      {rows.length === 0 ? <p className="muted">No data yet</p> : rows.map((r) => (
        <div className="brow" key={r.name}>
          <span className="bname">{r.name}</span>
          <span className="btrack"><span style={{ width: `${(r.clicks / Math.max(total, 1)) * 100}%` }} /></span>
          <span className="bnum">{r.clicks}</span>
        </div>
      ))}
    </div>
  );
}

function Detail({ link, onChanged, onDeleted }) {
  const [stats, setStats] = useState(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setStats(null);
    setError("");
    api.stats(link.code).then(setStats).catch((e) => setError(e.message));
  }, [link.code, link.total_clicks]);

  async function copy() {
    await navigator.clipboard.writeText(link.short_url);
    setCopied(true);
    setTimeout(() => setCopied(false), 1600);
  }

  async function toggle() {
    try { onChanged(await api.updateLink(link.code, { is_active: !link.is_active })); }
    catch (e) { setError(e.message); }
  }

  async function remove() {
    if (!window.confirm(`Delete ${link.short_url}? It will stop working and its stats are lost.`)) return;
    try { await api.deleteLink(link.code); onDeleted(link.code); }
    catch (e) { setError(e.message); }
  }

  const st = status(link);
  return (
    <aside className="detail" aria-live="polite">
      <p className={`pill ${st.cls}`}>{st.text}</p>
      <h3 className="short">{link.short_url.replace(/^https?:\/\//, "")}</h3>
      <p className="dest" title={link.original_url}>Goes to {link.original_url}</p>
      <div className="actions">
        <button className="btn primary" onClick={copy}>{copied ? "Copied" : "Copy link"}</button>
        <button className="btn" onClick={toggle}>{link.is_active ? "Pause link" : "Resume link"}</button>
        <button className="btn danger" onClick={remove}>Delete</button>
      </div>
      {error && <p className="error" role="alert">{error}</p>}

      {stats && (
        <>
          <p className="total"><b>{stats.total_clicks}</b> click{stats.total_clicks === 1 ? "" : "s"} in total</p>
          <Bars data={stats.clicks_per_day} />
          <div className="axis"><span>{shortDate(stats.clicks_per_day[0].date)}</span><span>Today</span></div>
          <div className="breakdowns">
            <Breakdown title="Devices" rows={stats.devices} total={stats.total_clicks} />
            <Breakdown title="Where clicks came from" rows={stats.referrers} total={stats.total_clicks} />
          </div>
        </>
      )}
    </aside>
  );
}

export default function Dashboard({ user, onSignOut }) {
  const [links, setLinks] = useState(null);
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const data = await api.links();
      setLinks(data);
      setSelected((s) => s ?? data[0]?.code ?? null);
    } catch (e) { setError(e.message); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const current = links?.find((l) => l.code === selected);
  const replace = (l) => setLinks((ls) => ls.map((x) => (x.code === l.code ? { ...x, ...l, total_clicks: x.total_clicks } : x)));
  const totalClicks = links?.reduce((n, l) => n + l.total_clicks, 0) ?? 0;

  return (
    <div className="dash">
      <header className="top">
        <p className="brand">Kata</p>
        <div className="who">
          <span>{user.name}</span>
          <button className="link" onClick={onSignOut}>Sign out</button>
        </div>
      </header>

      <CreateForm onCreated={(l) => { setLinks((ls) => [l, ...(ls || [])]); setSelected(l.code); }} />
      {error && <p className="error" role="alert">{error}</p>}

      <div className="cols">
        <section aria-label="Your links">
          <h2>Your links {links && <span className="muted">{links.length} links, {totalClicks} clicks</span>}</h2>
          {links === null ? <p className="muted">Loading your links…</p>
            : links.length === 0 ? <p className="empty">No links yet. Paste a long link above and press Shorten link.</p>
            : (
              <ul className="list">
                {links.map((l) => (
                  <li key={l.code}>
                    <button className={`row ${l.code === selected ? "active" : ""}`} onClick={() => setSelected(l.code)}>
                      <span className="rname">{l.title || host(l.original_url)}</span>
                      <span className="rshort">{l.short_url.replace(/^https?:\/\//, "")}</span>
                      <span className="rclicks">{l.total_clicks}<small> clicks</small></span>
                      <span className={`dot ${status(l).cls}`} title={status(l).text} />
                    </button>
                  </li>
                ))}
              </ul>
            )}
        </section>

        {current && (
          <Detail link={current} onChanged={replace}
            onDeleted={(code) => { setLinks((ls) => ls.filter((l) => l.code !== code)); setSelected(null); setTimeout(load, 0); }} />
        )}
      </div>
    </div>
  );
}
