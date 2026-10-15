"use client";

import { CopilotChat } from "@copilotkit/react-core/v2";
import { useCallback, useEffect, useState } from "react";

type Setup = { id: string; name: string; region: string; plan: string; owner_email: string; allowed_domain: string; revision: number };
type Proposal = { id: string; email: string; role: string; setup_revision: number; revision: number; status: string; decision_actor: string | null };
type Invitation = { id: string; proposal_id: string; email: string; role: string };
type Workspace = { setup: Setup; invite_proposals: Proposal[]; invitations: Invitation[] };
const api = process.env.NEXT_PUBLIC_ONBOARDING_API_URL || "http://localhost:8125";

export default function Page() {
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [name, setName] = useState("");
  const [actor, setActor] = useState("owner@acme.example");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const response = await fetch(`${api}/workspace`, { cache: "no-store" });
      if (!response.ok) throw new Error("Workspace API unavailable");
      const state: Workspace = await response.json();
      setWorkspace(state);
      setName((current) => current || state.setup.name);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not load workspace"); }
  }, []);
  useEffect(() => { void refresh(); const timer = window.setInterval(() => void refresh(), 3000); return () => window.clearInterval(timer); }, [refresh]);

  async function post(url: string, method: string, body: object) {
    setBusy(true);
    try {
      const response = await fetch(`${api}${url}`, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      if (!response.ok) { const problem = await response.json(); throw new Error(problem.detail || "Action failed"); }
      setError("");
      await refresh();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Action failed"); await refresh(); }
    finally { setBusy(false); }
  }

  const pending = workspace?.invite_proposals.filter((item) => item.status === "pending") || [];
  const decided = workspace?.invite_proposals.filter((item) => item.status !== "pending") || [];
  return <main className="app-shell">
    <header className="topbar"><div className="brand"><span className="brand-symbol">A</span> ACME <span className="brand-light">/ SETUP</span></div><span className="topbar-mid">TEAM WORKSPACE / 2026</span><span className="environment">SYNTHETIC ENVIRONMENT</span></header>
    <div className="content">
      <section className="hero"><div className="eyebrow">ONBOARDING / {workspace?.setup.id || "WS-101"}</div><h1>Set up your team,<br/><em>with control.</em></h1><p>Complete the workspace details, review each proposed invite, and keep the member list exact.</p></section>
      {error && <div className="error" role="alert">{error}</div>}
      <div className="grid">
        <div className="main-column">
          <section className="card setup-card"><div className="section-head"><div><span className="step">01 / FOUNDATION</span><h2>Workspace details</h2></div><span className="pill">REV {workspace?.setup.revision ?? "–"}</span></div>
            <div className="setup-body"><div className="field"><label htmlFor="workspace-name">Workspace name</label><div className="name-row"><input id="workspace-name" value={name} onChange={(event) => setName(event.target.value)} placeholder="e.g. Acme North"/><button disabled={!workspace || busy} onClick={() => workspace && void post("/workspace/name", "PATCH", { name, revision: workspace.setup.revision, actor })}>Save name</button></div><small>Required before the copilot can propose invitations.</small></div>
              <div className="facts"><div><span>REGION</span><strong>{workspace?.setup.region || "—"}</strong></div><div><span>PLAN</span><strong>{workspace?.setup.plan || "—"}</strong></div><div><span>ALLOWED DOMAIN</span><strong>@{workspace?.setup.allowed_domain || "—"}</strong></div></div></div></section>
          <section className="card members-card"><div className="section-head"><div><span className="step">02 / PEOPLE</span><h2>Team members</h2></div><span className="pill">{workspace?.invitations.length ?? 0} INVITED</span></div><div className="members-list"><div className="member"><span className="avatar">OC</span><div><strong>{workspace?.setup.owner_email || "owner@acme.example"}</strong><small>Workspace owner</small></div><span className="member-status">ACTIVE</span></div>{workspace?.invitations.map((invite) => <div className="member" key={invite.id}><span className="avatar invited">{invite.email.slice(0, 2).toUpperCase()}</span><div><strong>{invite.email}</strong><small>{invite.role} · {invite.id}</small></div><span className="member-status">INVITED</span></div>)}{!workspace?.invitations.length && <div className="empty-members">Approved invitations appear here. Proposals alone do not add members.</div>}</div></section>
        </div>
        <aside className="side-column"><section className="card review-card"><div className="section-head"><div><span className="step">03 / REVIEW</span><h2>Invitation queue</h2></div><span className="pill amber">{pending.length} PENDING</span></div><div className="review-body"><label htmlFor="actor">Acting as</label><input id="actor" value={actor} onChange={(event) => setActor(event.target.value)} /><p className="hint">Only the workspace owner can approve or reject. This is a local demo identity.</p>{pending.length === 0 && <p className="quiet">No invites waiting for review. Ask the copilot to propose a teammate after setup is complete.</p>}{pending.map((proposal) => <div className="proposal" key={proposal.id}><div className="proposal-meta"><span>{proposal.id}</span><span>{proposal.role.toUpperCase()}</span></div><strong>{proposal.email}</strong><small>Created from setup revision {proposal.setup_revision}</small><div className="actions"><button className="secondary" disabled={busy} onClick={() => void post(`/proposals/${proposal.id}/decision`, "POST", { revision: proposal.revision, decision: "reject", actor })}>Reject</button><button disabled={busy} onClick={() => void post(`/proposals/${proposal.id}/decision`, "POST", { revision: proposal.revision, decision: "approve", actor })}>Approve invite</button></div></div>)}{decided.length > 0 && <div className="history"><span className="step">DECISIONS</span>{decided.map((proposal) => <p key={proposal.id}>{proposal.email} <strong>{proposal.status}</strong></p>)}</div>}</div></section>
          <section className="card copilot-card"><div className="copilot-intro"><span className="step">ASSISTANT / GOOGLE ADK</span><h2>Onboarding copilot</h2><p>Ask about requirements or propose an invite. Decisions stay in this review queue.</p></div><div className="chat-wrap"><CopilotChat agentId="onboarding_agent" className="chat" /></div></section></aside>
      </div><footer>ACME SETUP / LOCAL DEMONSTRATION <span>NO EXTERNAL INVITATIONS ARE SENT</span></footer>
    </div>
  </main>;
}
