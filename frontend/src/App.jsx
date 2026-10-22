import { useState } from "react";
import { session } from "./api.js";
import Landing from "./Landing.jsx";
import Dashboard from "./Dashboard.jsx";

export default function App() {
  const [auth, setAuth] = useState(session.get());

  const signIn = (data) => { session.set(data); setAuth(data); };
  const signOut = () => { session.clear(); setAuth(null); };

  return auth ? <Dashboard user={auth.user} onSignOut={signOut} /> : <Landing onAuth={signIn} />;
}
