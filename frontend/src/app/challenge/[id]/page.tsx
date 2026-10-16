"use client";
// app/challenge/[id]/page.tsx
// Split-pane code workspace:
//   Left  – Problem info, visible test cases, concept tags
//   Right – Monaco editor + Run & Submit button + feedback panel

import { useEffect, useState, useCallback, Suspense } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { getChallenge, submitCode } from "@/lib/api";
import CodeEditor from "@/components/CodeEditor";
import SubmissionFeedback from "@/components/SubmissionFeedback";
import type { Challenge, SubmissionResponse, VisibleTestCase } from "@/types";
import {
  ArrowLeft,
  Code2,
  Play,
  Loader2,
  Tag,
  FlaskConical,
  CheckCheck,
} from "lucide-react";

// ── Hardcoded demo learner — replace with auth context in production ────────
const DEMO_LEARNER_ID = "00000000-0000-0000-0000-000000000001";

// ── Difficulty badge ───────────────────────────────────────────────────────

const DIFF_STYLES: Record<string, string> = {
  Easy:   "border-emerald-500/40 bg-emerald-500/10 text-emerald-400",
  Medium: "border-amber-500/40  bg-amber-500/10  text-amber-400",
  Hard:   "border-rose-500/40   bg-rose-500/10   text-rose-400",
};

// ── Test case display ──────────────────────────────────────────────────────

function TestCaseCard({ tc, index }: { tc: VisibleTestCase; index: number }) {
  return (
    <div className="rounded-lg border border-slate-700/60 bg-slate-800/40 overflow-hidden text-xs">
      <div className="flex items-center gap-2 border-b border-slate-700/60 bg-slate-800/60 px-3 py-2">
        <FlaskConical className="h-3.5 w-3.5 text-slate-500" />
        <span className="font-medium text-slate-400">Test Case {index + 1}</span>
      </div>
      <div className="p-3 space-y-2">
        <div>
          <span className="text-slate-500">Input: </span>
          <code className="font-mono text-violet-300">
            {JSON.stringify(tc.input_args)}
          </code>
        </div>
        <div>
          <span className="text-slate-500">Expected: </span>
          <code className="font-mono text-emerald-300">
            {JSON.stringify(tc.expected_output)}
          </code>
        </div>
      </div>
    </div>
  );
}

// ── Inner component (useParams must be inside Suspense) ────────────────────

function ChallengePageInner() {
  const { id } = useParams<{ id: string }>();

  const [challenge, setChallenge]   = useState<Challenge | null>(null);
  const [loadError, setLoadError]   = useState<string | null>(null);
  const [code, setCode]             = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [result, setResult]         = useState<SubmissionResponse | null>(null);
  const [hintsUsed, setHintsUsed]   = useState(0);

  // ── Load challenge ─────────────────────────────────────────────────────
  useEffect(() => {
    if (!id) return;
    getChallenge(id)
      .then((ch) => {
        setChallenge(ch);
        setCode(ch.starter_code);
      })
      .catch((e) => setLoadError(e.message));
  }, [id]);

  // ── Submit handler ─────────────────────────────────────────────────────
  const handleSubmit = useCallback(async () => {
    if (!challenge || submitting) return;
    setSubmitting(true);
    setSubmitError(null);
    setResult(null);
    try {
      const res = await submitCode({
        learner_id:   DEMO_LEARNER_ID,
        challenge_id: challenge.id,
        code,
        hints_used:   hintsUsed,
      });
      setResult(res);
    } catch (e: unknown) {
      setSubmitError(e instanceof Error ? e.message : "Submission failed.");
    } finally {
      setSubmitting(false);
    }
  }, [challenge, code, hintsUsed, submitting]);

  // ── Keyboard shortcut: Ctrl/Cmd + Enter ───────────────────────────────
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") handleSubmit();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [handleSubmit]);

  // ── Loading / error states ─────────────────────────────────────────────
  if (loadError) {
    return (
      <div className="flex h-screen items-center justify-center bg-[#0a0a0f]">
        <div className="text-center space-y-3">
          <p className="text-rose-400 text-lg">{loadError}</p>
          <Link href="/" className="text-sm text-violet-400 hover:underline">
            ← Back to challenges
          </Link>
        </div>
      </div>
    );
  }

  if (!challenge) {
    return (
      <div className="flex h-screen items-center justify-center bg-[#0a0a0f]">
        <Loader2 className="h-8 w-8 animate-spin text-violet-500" />
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col bg-[#0a0a0f] text-slate-200 overflow-hidden">
      {/* ── Top nav bar ─────────────────────────────────────────────────── */}
      <header className="flex h-12 flex-shrink-0 items-center gap-4 border-b border-white/5 bg-slate-900/80 px-5 backdrop-blur">
        <Link
          href="/"
          className="flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-200 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          Challenges
        </Link>
        <div className="h-4 w-px bg-slate-700" />
        <Code2 className="h-4 w-4 text-violet-400" />
        <span className="font-semibold text-slate-200">{challenge.title}</span>
        <span
          className={`ml-1 rounded border px-2 py-0.5 text-xs ${
            DIFF_STYLES[challenge.difficulty] ?? ""
          }`}
        >
          {challenge.difficulty}
        </span>
        <div className="ml-auto flex items-center gap-2 text-xs text-slate-500">
          <CheckCheck className="h-3.5 w-3.5" />
          <span>Ctrl + Enter to submit</span>
        </div>
      </header>

      {/* ── Split pane ──────────────────────────────────────────────────── */}
      <div className="flex flex-1 overflow-hidden">
        {/* ── LEFT: Problem info ─────────────────────────────────────────── */}
        <aside className="flex w-[380px] flex-shrink-0 flex-col overflow-y-auto border-r border-white/5 bg-slate-900/40">
          <div className="flex-1 space-y-5 p-5">
            {/* Description */}
            <div>
              <h1 className="mb-3 text-lg font-bold text-slate-100">
                {challenge.title}
              </h1>
              <p className="text-sm leading-relaxed text-slate-400 whitespace-pre-line">
                {challenge.description}
              </p>
            </div>

            {/* Concept tags */}
            <div>
              <div className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-slate-500">
                <Tag className="h-3 w-3" /> Concepts
              </div>
              <div className="flex flex-wrap gap-2">
                {challenge.concept_tags.map((tag) => (
                  <span
                    key={tag}
                    className="rounded-full border border-violet-500/30 bg-violet-500/10 px-3 py-1 text-xs text-violet-300"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </div>

            {/* Function signature */}
            <div>
              <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
                Signature
              </div>
              <code className="block rounded-lg border border-slate-700 bg-slate-800/60 px-3 py-2 text-xs font-mono text-violet-300">
                {challenge.function_signature}
              </code>
            </div>

            {/* XP & time limit */}
            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-lg border border-white/5 bg-white/3 p-3 text-center">
                <p className="text-xs text-slate-500">XP Reward</p>
                <p className="font-bold text-violet-400">+{challenge.xp_reward}</p>
              </div>
              <div className="rounded-lg border border-white/5 bg-white/3 p-3 text-center">
                <p className="text-xs text-slate-500">Time Limit</p>
                <p className="font-bold text-slate-300">{challenge.time_limit_seconds}s</p>
              </div>
            </div>

            {/* Visible test cases */}
            <div>
              <div className="mb-3 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-slate-500">
                <FlaskConical className="h-3 w-3" /> Sample Test Cases
              </div>
              <div className="space-y-2">
                {challenge.visible_test_cases.map((tc, i) => (
                  <TestCaseCard key={tc.id} tc={tc} index={i} />
                ))}
              </div>
              <p className="mt-2 text-xs text-slate-600">
                + hidden test cases to check edge cases
              </p>
            </div>
          </div>
        </aside>

        {/* ── RIGHT: Editor + feedback ──────────────────────────────────── */}
        <main className="flex flex-1 flex-col overflow-hidden">
          {/* Editor takes remaining height above feedback */}
          <div className={`flex-1 overflow-hidden transition-all duration-300 ${result ? "h-1/2" : "h-full"}`}>
            <CodeEditor value={code} onChange={setCode} />
          </div>

          {/* Submit bar */}
          <div className="flex items-center gap-3 border-t border-white/5 bg-slate-900/60 px-5 py-3">
            {submitError && (
              <p className="text-xs text-rose-400">{submitError}</p>
            )}
            <div className="ml-auto flex items-center gap-3">
              <span className="text-xs text-slate-600">
                {code.split("\n").length} lines
              </span>
              <button
                onClick={handleSubmit}
                disabled={submitting}
                id="run-submit-btn"
                className="flex items-center gap-2 rounded-lg bg-gradient-to-r from-violet-600 to-indigo-600 px-6 py-2.5 text-sm font-semibold text-white shadow-lg shadow-violet-500/20 transition-all hover:from-violet-500 hover:to-indigo-500 hover:shadow-violet-500/30 disabled:opacity-60"
              >
                {submitting ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Running…
                  </>
                ) : (
                  <>
                    <Play className="h-4 w-4" />
                    Run &amp; Submit
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Feedback panel — slides in below editor when result arrives */}
          {result && (
            <div className="h-1/2 overflow-y-auto border-t border-white/5 bg-slate-900/60 p-5">
              <SubmissionFeedback
                result={result}
                onReset={() => {
                  setResult(null);
                  setCode(challenge.starter_code);
                  setHintsUsed(0);
                }}
              />
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

// ── Default export wraps in Suspense ─────────────────────────────────────────

export default function ChallengePage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-screen items-center justify-center bg-[#0a0a0f]">
          <Loader2 className="h-8 w-8 animate-spin text-violet-500" />
        </div>
      }
    >
      <ChallengePageInner />
    </Suspense>
  );
}
