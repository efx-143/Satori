// lib/api.ts
// Typed API client for the Debug Dojo Flask backend.
// All functions throw on non-2xx responses with a human-readable message.

import type {
  Challenge,
  SubmissionResponse,
  HintResponse,
  DashboardData,
} from "@/types";

const BASE = (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/$/, "");

async function apiFetch<T>(
  path: string,
  init?: RequestInit
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });

  if (!res.ok) {
    let msg = `API error ${res.status}`;
    try {
      const body = await res.json();
      msg = body.message ?? body.error ?? msg;
    } catch {}
    throw new Error(msg);
  }

  return res.json() as Promise<T>;
}

// ── Challenges ─────────────────────────────────────────────────────────────

export const getChallenge = (id: string) =>
  apiFetch<Challenge>(`/api/v1/challenges/${id}`);

export const listChallenges = (params?: {
  difficulty?: string;
  concept?: string;
  page?: number;
}) => {
  const qs = new URLSearchParams(
    Object.entries(params ?? {}).filter(([, v]) => v != null) as string[][]
  ).toString();
  return apiFetch<{ challenges: Challenge[]; total: number }>(
    `/api/v1/challenges/${qs ? `?${qs}` : ""}`
  );
};

// ── Submissions ────────────────────────────────────────────────────────────

export interface SubmitPayload {
  learner_id: string;
  challenge_id: string;
  code: string;
  hints_used: number;
}

export const submitCode = (payload: SubmitPayload) =>
  apiFetch<SubmissionResponse>("/api/v1/submissions/", {
    method: "POST",
    body: JSON.stringify(payload),
  });

// ── Hints ──────────────────────────────────────────────────────────────────

export const generateHints = (submissionId: string) =>
  apiFetch<HintResponse>(`/api/v1/hints/${submissionId}`, {
    method: "POST",
    body: JSON.stringify({}),
  });

// ── Dashboard ──────────────────────────────────────────────────────────────

export const getDashboard = (learnerId: string) =>
  apiFetch<DashboardData>(`/api/v1/learners/${learnerId}/dashboard`);

// ── Learner registration ───────────────────────────────────────────────────

export const registerLearner = (username: string, email?: string) =>
  apiFetch<{ id: string; username: string }>("/api/v1/learners/", {
    method: "POST",
    body: JSON.stringify({ username, email }),
  });
