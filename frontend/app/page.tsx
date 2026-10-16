"use client";

import { useState } from "react";
import { OnboardingChat } from "./onboarding-chat";
import { useWorkspace } from "./use-workspace";

export default function Page() {
  const {
    workspace,
    name,
    setName,
    actor,
    setActor,
    error,
    busy,
    available,
    nameConflict,
    adoptCurrent,
    saveName,
    decide,
  } = useWorkspace();
  const [query, setQuery] = useState("");
  const matches = (item: { email: string; role: string; id: string }) =>
    `${item.email} ${item.role} ${item.id}`
      .toLowerCase()
      .includes(query.toLowerCase());
  const pending =
    workspace?.invite_proposals.filter((item) => item.status === "pending") ||
    [];
  const decided =
    workspace?.invite_proposals.filter((item) => item.status !== "pending") ||
    [];
  const visiblePending = pending.filter(matches);
  const visibleDecided = decided.filter(matches);
  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-symbol">A</span> ACME{" "}
          <span className="brand-light">/ SETUP</span>
        </div>
        <span className="topbar-mid">TEAM WORKSPACE / 2026</span>
        <span className="environment">SYNTHETIC ENVIRONMENT</span>
      </header>
      <div className="content">
        <section className="hero">
          <div className="eyebrow">
            ONBOARDING / {workspace?.setup.id || "LOADING"}
          </div>
          <h1>
            Set up your team,
            <br />
            <em>with control.</em>
          </h1>
          <p>
            Complete the workspace details, review each proposed invite, and
            keep the member list exact.
          </p>
        </section>
        {error && (
          <div className="error" role="alert">
            {error}
          </div>
        )}
        <div className="grid">
          <div className="main-column">
            <section className="card setup-card">
              <div className="section-head">
                <div>
                  <span className="step">01 / FOUNDATION</span>
                  <h2>Workspace details</h2>
                </div>
                <span className="pill">
                  REV {workspace?.setup.revision ?? "–"}
                </span>
              </div>
              <div className="setup-body">
                <div className="field">
                  <label htmlFor="workspace-name">Workspace name</label>
                  <div className="name-row">
                    <input
                      id="workspace-name"
                      disabled={busy || !available}
                      value={name}
                      onChange={(event) => setName(event.target.value)}
                      placeholder="e.g. Acme North"
                    />
                    <button
                      disabled={
                        !workspace || busy || !available || nameConflict
                      }
                      onClick={() => void saveName()}
                    >
                      Save name
                    </button>
                  </div>
                  <small>
                    Required before the copilot can propose invitations.
                  </small>
                  {nameConflict && (
                    <p className="form-conflict" role="status">
                      The workspace changed while you were editing. Current
                      saved name: <strong>{workspace?.setup.name}</strong>.{" "}
                      <button
                        className="secondary"
                        disabled={busy}
                        onClick={adoptCurrent}
                      >
                        Use current name
                      </button>
                    </p>
                  )}
                </div>
                <div className="facts">
                  <div>
                    <span>REGION</span>
                    <strong>{workspace?.setup.region || "—"}</strong>
                  </div>
                  <div>
                    <span>PLAN</span>
                    <strong>{workspace?.setup.plan || "—"}</strong>
                  </div>
                  <div>
                    <span>ALLOWED DOMAIN</span>
                    <strong>@{workspace?.setup.allowed_domain || "—"}</strong>
                  </div>
                </div>
              </div>
            </section>
            <section className="card members-card">
              <div className="section-head">
                <div>
                  <span className="step">02 / PEOPLE</span>
                  <h2>Team members</h2>
                </div>
                <span className="pill">
                  {workspace?.invitations.length ?? 0} INVITED
                </span>
              </div>
              <div className="members-list">
                {workspace && (
                  <div className="member">
                    <span className="avatar">OC</span>
                    <div>
                      <strong>
                        {workspace?.setup.owner_email || "owner@acme.example"}
                      </strong>
                      <small>Workspace owner</small>
                    </div>
                    <span className="member-status">ACTIVE</span>
                  </div>
                )}
                {!workspace && (
                  <p role="status">Loading committed workspace state…</p>
                )}
                {workspace?.invitations.map((invite) => (
                  <div className="member" key={invite.id}>
                    <span className="avatar invited">
                      {invite.email.slice(0, 2).toUpperCase()}
                    </span>
                    <div>
                      <strong>{invite.email}</strong>
                      <small>
                        {invite.role} · {invite.id}
                      </small>
                    </div>
                    <span className="member-status">INVITED</span>
                  </div>
                ))}
                {!workspace?.invitations.length && (
                  <div className="empty-members">
                    Approved invitations appear here. Proposals alone do not add
                    members.
                  </div>
                )}
              </div>
            </section>
          </div>
          <aside className="side-column">
            <section className="card review-card">
              <div className="section-head">
                <div>
                  <span className="step">03 / REVIEW</span>
                  <h2>Invitation queue</h2>
                </div>
                <span className="pill amber">{pending.length} PENDING</span>
              </div>
              <div className="review-body">
                <label htmlFor="actor">Acting as</label>
                <input
                  id="actor"
                  value={actor}
                  disabled={busy || !available}
                  onChange={(event) => setActor(event.target.value)}
                />
                <p className="hint">
                  Only the workspace owner can approve or reject. This is a
                  local demo identity.
                </p>
                {(pending.length > 0 || decided.length > 0) && (
                  <div className="queue-filter">
                    <label htmlFor="invitation-filter">Find invitation</label>
                    <input
                      id="invitation-filter"
                      value={query}
                      onChange={(event) => setQuery(event.target.value)}
                      placeholder="Email, role or proposal ID"
                    />
                  </div>
                )}
                {pending.length === 0 && (
                  <p className="quiet">
                    No invites waiting for review. Ask the copilot to propose a
                    teammate after setup is complete.
                  </p>
                )}
                {query &&
                  visiblePending.length === 0 &&
                  visibleDecided.length === 0 && (
                    <p className="quiet">No invitations match this filter.</p>
                  )}
                {visiblePending.map((proposal) => (
                  <div className="proposal" key={proposal.id}>
                    <div className="proposal-meta">
                      <span>{proposal.id}</span>
                      <span>{proposal.role.toUpperCase()}</span>
                    </div>
                    <strong>{proposal.email}</strong>
                    <small>
                      Created from setup revision {proposal.setup_revision}
                    </small>
                    <div className="actions">
                      <button
                        className="secondary"
                        disabled={busy || !available}
                        onClick={() => void decide(proposal, "reject")}
                      >
                        Reject
                      </button>
                      <button
                        disabled={busy || !available}
                        onClick={() => void decide(proposal, "approve")}
                      >
                        Approve invite
                      </button>
                    </div>
                  </div>
                ))}
                {visibleDecided.length > 0 && (
                  <div className="history">
                    <span className="step">DECISIONS</span>
                    {visibleDecided.map((proposal) => (
                      <p key={proposal.id}>
                        {proposal.email} <strong>{proposal.status}</strong>
                      </p>
                    ))}
                  </div>
                )}
              </div>
            </section>
            <section className="card copilot-card">
              <div className="copilot-intro">
                <span className="step">ASSISTANT / GOOGLE ADK</span>
                <h2>Onboarding copilot</h2>
                <p>
                  Ask about requirements or propose an invite. Decisions stay in
                  this review queue.
                </p>
              </div>
              <div className="chat-wrap">
                <OnboardingChat />
              </div>
            </section>
          </aside>
        </div>
        <footer>
          ACME SETUP / LOCAL DEMONSTRATION{" "}
          <span>NO EXTERNAL INVITATIONS ARE SENT</span>
        </footer>
      </div>
    </main>
  );
}
