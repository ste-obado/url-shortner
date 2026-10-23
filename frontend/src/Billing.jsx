import { useEffect, useRef, useState } from "react";
import { api } from "./api.js";

const kes = (n) => `KES ${n.toLocaleString()}`;
const fmtDate = (d) => new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(d) ? d : d + "Z")
  .toLocaleDateString(undefined, { day: "numeric", month: "long", year: "numeric" });
const limitText = (n) => (n ? `Up to ${n} links` : "Unlimited links");

const OUTCOME = {
  cancelled: "You cancelled the M-Pesa request. Nothing was charged. Choose a plan to try again.",
  failed: "The payment didn't go through. Nothing was charged. Check your M-Pesa balance and try again.",
  expired: "We didn't hear back from M-Pesa, so this attempt was closed. If you were charged, try again and we'll find it.",
  review: "We received your payment but need to check it by hand. Your plan will be activated once we do. Please keep your M-Pesa message.",
};

export default function Billing({ bill, onRefresh, onClose }) {
  const [plans, setPlans] = useState([]);
  const [choice, setChoice] = useState(null);
  const [phone, setPhone] = useState("");
  const [phase, setPhase] = useState(bill.pending_payment_id ? "waiting" : "idle"); // idle | sending | waiting | done
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const timer = useRef(null);

  useEffect(() => { api.plans().then(setPlans).catch(() => {}); }, []);
  useEffect(() => { if (bill.pending_payment_id) poll(bill.pending_payment_id); return stop; }, []); // eslint-disable-line

  const stop = () => clearInterval(timer.current);

  function poll(paymentId) {
    stop();
    const started = Date.now();
    timer.current = setInterval(async () => {
      try {
        const p = await api.payment(paymentId);
        if (p.status === "pending") {
          if (Date.now() - started > 120000) {
            stop();
            setPhase("done");
            setMessage("Still waiting for M-Pesa. If you've paid, your plan will switch on within a minute. Reopen this panel to check.");
          }
          return;
        }
        stop();
        setPhase("done");
        if (p.status === "success") { setMessage(`Payment received${p.receipt ? ` (${p.receipt})` : ""}. Your ${p.plan} plan is active.`); onRefresh(); }
        else setMessage(OUTCOME[p.status] || "The payment did not complete.");
      } catch { /* network blip: keep polling */ }
    }, 4000);
  }

  async function pay(e) {
    e.preventDefault();
    setError("");
    setPhase("sending");
    try {
      const p = await api.checkout({ plan: choice, phone });
      setPhase("waiting");
      poll(p.id);
    } catch (err) {
      setError(err.message);
      setPhase("idle");
    }
  }

  const paid = plans.filter((p) => p.id !== "free");
  const chosen = plans.find((p) => p.id === choice);
  const rank = { free: 0, pro: 1, enterprise: 2 };

  return (
    <section className="billing" aria-label="Plans and billing">
      <div className="billing-head">
        <h2>Your plan: {bill.plan_name}</h2>
        <button className="link" onClick={onClose}>Close</button>
      </div>
      {bill.expires_at && <p className="muted">Active until {fmtDate(bill.expires_at)}. Paying again adds 30 days on top.</p>}

      {phase === "waiting" && (
        <p className="notice" role="status">Check your phone and enter your M-Pesa PIN. This page updates by itself.</p>
      )}
      {phase === "done" && <p className="notice" role="status">{message}</p>}

      <ul className="plans">
        {paid.map((p) => {
          const lower = rank[p.id] < rank[bill.plan];
          return (
            <li key={p.id} className={choice === p.id ? "picked" : ""}>
              <div>
                <h3>{p.name}</h3>
                <p className="muted">{limitText(p.link_limit)}, 30 days</p>
              </div>
              <p className="price">{kes(p.price)}<small> / month</small></p>
              <button className="btn" disabled={lower || phase === "waiting" || phase === "sending"} onClick={() => { setChoice(p.id); setError(""); }}>
                {lower ? "You have a higher plan" : bill.plan === p.id ? "Renew" : "Choose"}
              </button>
            </li>
          );
        })}
      </ul>
      <p className="muted free-note">Free plan: {limitText(plans.find((p) => p.id === "free")?.link_limit)}.</p>

      {chosen && phase !== "waiting" && (
        <form className="pay" onSubmit={pay}>
          <label>M-Pesa phone number
            <input type="tel" inputMode="tel" placeholder="0712345678" value={phone} onChange={(e) => setPhone(e.target.value)} required />
          </label>
          <button className="btn primary" disabled={phase === "sending"}>
            {phase === "sending" ? "Sending prompt…" : `Pay ${kes(chosen.price)} with M-Pesa`}
          </button>
          {error && <p className="error full" role="alert">{error}</p>}
        </form>
      )}
    </section>
  );
}
