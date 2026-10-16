"use client";
import { useCallback, useEffect, useRef, useState } from "react";
export type Setup = {
  id: string;
  name: string;
  region: string;
  plan: string;
  owner_email: string;
  allowed_domain: string;
  revision: number;
};
export type Proposal = {
  id: string;
  email: string;
  role: string;
  setup_revision: number;
  revision: number;
  status: string;
  decision_actor: string | null;
};
export type Invitation = {
  id: string;
  proposal_id: string;
  email: string;
  role: string;
};
export type Workspace = {
  setup: Setup;
  invite_proposals: Proposal[];
  invitations: Invitation[];
};
const api =
  process.env.NEXT_PUBLIC_ONBOARDING_API_URL || "http://localhost:8125";
function problem(value: unknown, status: number): string {
  if (value && typeof value === "object" && "detail" in value) {
    const d = value.detail;
    if (typeof d === "string")
      return (
        (
          {
            owner_required:
              "Enter the current workspace owner's email to make this change.",
            stale_setup_revision:
              "Workspace details changed. Review the current name and try again.",
            proposal_not_current:
              "This proposal changed. Review the current invitation queue.",
            setup_changed:
              "Workspace details changed after this proposal. Reject it and ask the copilot for a fresh proposal.",
            revision_exhausted:
              "This workspace has reached its revision limit. Use a fresh workspace to change the name.",
            already_invited: "This address already has a committed invitation.",
          } as Record<string, string>
        )[d] ?? d
      );
    if (Array.isArray(d))
      return d
        .map((row) =>
          row && typeof row === "object"
            ? `${Array.isArray(row.loc) ? row.loc.filter((v: unknown) => v !== "body").join(".") : "Request"}: ${row.type === "string_pattern_mismatch" ? "Enter a valid .example email address" : typeof row.msg === "string" ? row.msg : "invalid value"}`
            : "Invalid request",
        )
        .join("; ");
  }
  return `Action failed (HTTP ${status})`;
}
function valid(value: unknown): value is Workspace {
  if (!value || typeof value !== "object") return false;
  const v = value as Partial<Workspace>;
  return (
    !!v.setup &&
    typeof v.setup.name === "string" &&
    Number.isSafeInteger(v.setup.revision) &&
    v.setup.revision > 0 &&
    typeof v.setup.owner_email === "string" &&
    Array.isArray(v.invite_proposals) &&
    Array.isArray(v.invitations)
  );
}
export function useWorkspace() {
  const [workspace, setWorkspace] = useState<Workspace | null>(null),
    [draft, setDraft] = useState({ value: "", revision: 0, dirty: false }),
    [actor, setActorValue] = useState(""),
    [busy, setBusy] = useState(false),
    [available, setAvailable] = useState(false),
    [readError, setReadError] = useState(""),
    [actionError, setActionError] = useState("");
  const sequence = useRef(0),
    activeRead = useRef<AbortController | null>(null),
    inflight = useRef(false),
    mounted = useRef(true),
    actorEdited = useRef(false);
  const refresh = useCallback(async () => {
    const current = ++sequence.current;
    activeRead.current?.abort();
    const controller = new AbortController();
    activeRead.current = controller;
    try {
      const response = await fetch(`${api}/workspace`, {
        cache: "no-store",
        signal: controller.signal,
      });
      if (!response.ok)
        throw Error(
          "Workspace API unavailable. Your changes have not been confirmed.",
        );
      const state: unknown = await response.json();
      if (!valid(state)) throw Error("Workspace API returned invalid state.");
      if (!mounted.current || current !== sequence.current) return;
      setWorkspace(state);
      if (!actorEdited.current) setActorValue(state.setup.owner_email);
      setAvailable(true);
      setReadError("");
      setDraft((previous) =>
        previous.dirty
          ? previous
          : {
              value: state.setup.name,
              revision: state.setup.revision,
              dirty: false,
            },
      );
    } catch (error) {
      if (
        controller.signal.aborted ||
        !mounted.current ||
        current !== sequence.current
      )
        return;
      setAvailable(false);
      setReadError(
        error instanceof Error ? error.message : "Could not load workspace",
      );
    }
  }, []);
  useEffect(() => {
    mounted.current = true;
    void refresh();
    const timer = window.setInterval(() => void refresh(), 3000);
    return () => {
      mounted.current = false;
      window.clearInterval(timer);
      activeRead.current?.abort();
    };
  }, [refresh]);
  const post = async (
    url: string,
    method: string,
    body: object,
    onSuccess?: () => void,
  ) => {
    if (inflight.current || !available) return;
    inflight.current = true;
    setBusy(true);
    ++sequence.current;
    activeRead.current?.abort();
    try {
      const response = await fetch(`${api}${url}`, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!response.ok) {
        let data: unknown;
        try {
          data = await response.json();
        } catch {}
        throw Error(problem(data, response.status));
      }
      setActionError("");
      onSuccess?.();
      await refresh();
    } catch (error) {
      if (mounted.current)
        setActionError(
          error instanceof Error ? error.message : "Action failed",
        );
      await refresh();
    } finally {
      inflight.current = false;
      if (mounted.current) setBusy(false);
    }
  };
  const nameConflict =
    !!workspace && draft.dirty && draft.revision !== workspace.setup.revision;
  return {
    workspace,
    name: draft.value,
    actor,
    setActor: (value: string) => {
      actorEdited.current = true;
      setActorValue(value);
    },
    busy,
    available,
    error: [actionError, readError].filter(Boolean).join(" "),
    nameConflict,
    setName: (value: string) =>
      setDraft((previous) => ({ ...previous, value, dirty: true })),
    adoptCurrent: () =>
      workspace &&
      setDraft({
        value: workspace.setup.name,
        revision: workspace.setup.revision,
        dirty: false,
      }),
    saveName: () =>
      workspace &&
      !nameConflict &&
      post(
        "/workspace/name",
        "PATCH",
        { name: draft.value, revision: draft.revision, actor },
        () => setDraft((previous) => ({ ...previous, dirty: false })),
      ),
    decide: (p: Proposal, decision: "approve" | "reject") =>
      post(`/proposals/${p.id}/decision`, "POST", {
        revision: p.revision,
        decision,
        actor,
      }),
  };
}
