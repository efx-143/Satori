"use client";
// app/challenge/[id]/page.tsx
// Phase 5: The Code Workspace (Challenge Page) — MXESA [26] Neo-Brutalist Theme

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
  Award,
  Clock,
  Terminal,
} from "lucide-react";

// Demo pseudonymous learner ID
const DEMO_LEARNER_ID = "00000000-0000-0000-0000-000000000001";

const DIFF_BADGES: Record<string, string> = {
  Easy: "bg-[#E8E6DB] text-black border-2 border-black shadow-[2px_2px_0px_#000]",
  Medium: "bg-[#E5A83B] text-black border-2 border-black shadow-[2px_2px_0px_#000]",
  Hard: "bg-[#DE6557] text-black border-2 border-black shadow-[2px_2px_0px_#000]",
};

// ── Visible Test Case Card (MXESA Neo-Brutalist Card) ──────────────────────

function TestCaseCard({ tc, index }: { tc: VisibleTestCase; index: number }) {
  return (
    <div className="border-2 border-black bg-[#1A1A1A] overflow-hidden text-xs shadow-[3px_3px_0px_#000]">
      <div className="flex items-center justify-between border-b-2 border-black bg-black px-3 py-1.5 font-mono">
        <div className="flex items-center gap-2">
          <FlaskConical className="h-3.5 w-3.5 text-[#DE6557]" />
          <span className="font-bold text-white text-[11px] uppercase tracking-wider">
            VISIBLE TEST #{index + 1}
          </span>
        </div>
        <span className="text-[10px] text-[#E5A83B] font-bold">PUBLIC</span>
      </div>
      <div className="p-3 space-y-2.5">
        <div>
          <span className="font-mono text-[10px] text-slate-400 uppercase tracking-wider block mb-1">
            Input Arguments:
          </span>
          <code className="block border border-black bg-[#141414] px-2.5 py-1.5 font-mono text-[#9BBBDD] text-xs overflow-x-auto shadow-inner">
            {JSON.stringify(tc.input_args)}
          </code>
        </div>
        <div>
          <span className="font-mono text-[10px] text-slate-400 uppercase tracking-wider block mb-1">
            Expected Output:
          </span>
          <code className="block border border-black bg-[#141414] px-2.5 py-1.5 font-mono text-[#E5A83B] text-xs overflow-x-auto font-bold shadow-inner">
            {JSON.stringify(tc.expected_output)}
          </code>
        </div>
      </div>
    </div>
  );
}

// ── Inner Page Component ──────────────────────────────────────────────────

function ChallengePageInner() {
  const { id } = useParams<{ id: string }>();

  const [challenge, setChallenge] = useState<Challenge | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [code, setCode] = useState<string>("");
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [result, setResult] = useState<SubmissionResponse | null>(null);
  const [hintsUsed, setHintsUsed] = useState<number>(0);

  // Load challenge from backend
  useEffect(() => {
    if (!id) return;
    getChallenge(id)
      .then((ch) => {
        setChallenge(ch);
        setCode(ch.starter_code);
      })
      .catch((err) => {
        setLoadError(
          err instanceof Error ? err.message : "Failed to load challenge."
        );
      });
  }, [id]);

  // Submit code to backend judging loop
  const handleSubmit = useCallback(async () => {
    if (!challenge || submitting) return;
    setSubmitting(true);
    setSubmitError(null);
    setResult(null);

    try {
      const res = await submitCode({
        learner_id: DEMO_LEARNER_ID,
        challenge_id: challenge.id,
        code,
        hints_used: hintsUsed,
      });
      setResult(res);
    } catch (err: unknown) {
      setSubmitError(
        err instanceof Error
          ? err.message
          : "Submission failed. Please try again."
      );
    } finally {
      setSubmitting(false);
    }
  }, [challenge, code, hintsUsed, submitting]);

  // Keyboard shortcut: Ctrl/Cmd + Enter
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
        e.preventDefault();
        handleSubmit();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleSubmit]);

  // Loading state
  if (!challenge && !loadError) {
    return (
      <div className="flex h-screen items-center justify-center bg-[#141414]">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-[#DE6557]" />
          <span className="font-mono text-xs font-bold text-slate-300">
            LOADING DOJO WORKSPACE…
          </span>
        </div>
      </div>
    );
  }

  // Load error state
  if (loadError || !challenge) {
    return (
      <div className="flex h-screen items-center justify-center bg-[#141414]">
        <div className="text-center space-y-4 p-8 border-2 border-black bg-[#E8E6DB] text-black max-w-md shadow-brutal-red">
          <p className="font-mono text-sm font-bold text-[#8B2019]">
            {loadError ?? "CHALLENGE NOT FOUND"}
          </p>
          <Link
            href="/"
            className="btn-terracotta inline-flex items-center gap-1.5 px-4 py-2 text-xs"
          >
            <ArrowLeft className="h-3.5 w-3.5" /> BACK TO CHALLENGES
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col bg-[#141414] text-[#F0EFEA] overflow-hidden font-sans selection:bg-[#DE6557] selection:text-black">
      {/* ── Top Navigation Bar ────────────────────────────────────────── */}
      <header className="flex h-14 flex-shrink-0 items-center justify-between border-b-2 border-black bg-[#141414] px-5 z-20">
        <div className="flex items-center gap-4">
          <Link
            href="/"
            className="btn-dark px-3 py-1 text-xs flex items-center gap-1.5"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            <span>BACK</span>
          </Link>
          <div className="h-4 w-px bg-slate-700" />
          <div className="flex items-center gap-2.5">
            <span className="font-mono font-bold text-xs text-white uppercase hidden sm:inline">
              DEBUG DOJO <span className="text-[#DE6557]">[26]</span>
            </span>
            <span className="text-slate-500 hidden sm:inline">/</span>
            <span className="font-black text-sm text-white">
              {challenge.title}
            </span>
            <span
              className={`px-2 py-0.5 text-[10px] font-mono font-bold uppercase ${
                DIFF_BADGES[challenge.difficulty] ?? ""
              }`}
            >
              {challenge.difficulty}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-4 text-xs font-mono">
          <div className="hidden sm:flex items-center gap-1 text-slate-400">
            <CheckCheck className="h-3.5 w-3.5 text-[#DE6557]" />
            <span>Ctrl + Enter to run</span>
          </div>
          <Link
            href="/dashboard"
            className="btn-terracotta px-3 py-1 text-xs"
          >
            DASHBOARD
          </Link>
        </div>
      </header>

      {/* ── Main Split-Pane Workspace ─────────────────────────────────── */}
      <div className="flex flex-1 overflow-hidden">
        {/* ── LEFT PANE: Problem Info ────────────────────────────────── */}
        <aside className="flex w-[420px] flex-shrink-0 flex-col overflow-y-auto border-r-2 border-black bg-[#141414]">
          <div className="flex-1 space-y-6 p-6">
            {/* Title & Metadata */}
            <div>
              {/* 3-color swatch */}
              <div className="flex items-center gap-2 mb-2">
                <div className="flex h-1.5 w-8 border border-black">
                  <div className="w-1/3 bg-[#DE6557]" />
                  <div className="w-1/3 bg-[#E5A83B]" />
                  <div className="w-1/3 bg-[#9BBBDD]" />
                </div>
                <span className="font-mono text-[10px] font-bold uppercase tracking-wider text-[#DE6557]">
                  PROBLEM ID: {challenge.id}
                </span>
              </div>
              <h1 className="text-2xl font-black uppercase tracking-tight text-white">
                {challenge.title}
              </h1>
              <p className="mt-3 text-xs leading-relaxed text-slate-300 font-sans whitespace-pre-line">
                {challenge.description}
              </p>
            </div>

            {/* Concept Tags */}
            <div className="space-y-2">
              <span className="font-mono text-[11px] font-bold uppercase tracking-wider text-slate-400 block">
                CONCEPT TAGS
              </span>
              <div className="flex flex-wrap gap-1.5">
                {challenge.concept_tags.map((tag) => (
                  <span
                    key={tag}
                    className="border border-black bg-[#1A1A1A] text-[#DE6557] px-2.5 py-0.5 font-mono text-[10px] font-bold shadow-[2px_2px_0px_#000]"
                  >
                    #{tag}
                  </span>
                ))}
              </div>
            </div>

            {/* Function Signature */}
            <div className="space-y-1.5">
              <span className="font-mono text-[11px] font-bold uppercase tracking-wider text-slate-400 block">
                FUNCTION SIGNATURE
              </span>
              <code className="block border-2 border-black bg-[#1A1A1A] px-3 py-2 text-xs font-mono text-[#E5A83B] font-bold shadow-[3px_3px_0px_#000]">
                {challenge.function_signature}
              </code>
            </div>

            {/* Metrics */}
            <div className="grid grid-cols-2 gap-3">
              <div className="border-2 border-black bg-[#1A1A1A] p-3 text-center shadow-[3px_3px_0px_#000]">
                <p className="font-mono text-[10px] text-slate-400 uppercase font-bold">
                  XP REWARD
                </p>
                <p className="font-mono text-sm font-bold text-[#DE6557] mt-0.5">
                  +{challenge.xp_reward} XP
                </p>
              </div>
              <div className="border-2 border-black bg-[#1A1A1A] p-3 text-center shadow-[3px_3px_0px_#000]">
                <p className="font-mono text-[10px] text-slate-400 uppercase font-bold">
                  TIME LIMIT
                </p>
                <p className="font-mono text-sm font-bold text-[#9BBBDD] mt-0.5">
                  {challenge.time_limit_seconds}s Timeout
                </p>
              </div>
            </div>

            {/* 3 Visible Test Cases */}
            <div className="space-y-3 pt-2">
              <div className="flex items-center justify-between border-b-2 border-black pb-2">
                <span className="font-mono text-xs font-bold uppercase tracking-wider text-white">
                  VISIBLE TESTS ({challenge.visible_test_cases.length})
                </span>
                <span className="font-mono text-[10px] text-slate-400">
                  Hidden tests evaluated on submit
                </span>
              </div>

              <div className="space-y-3">
                {challenge.visible_test_cases.map((tc, index) => (
                  <TestCaseCard key={tc.id || index} tc={tc} index={index} />
                ))}
              </div>
            </div>
          </div>
        </aside>

        {/* ── RIGHT PANE: Code Editor & Actions ───────────────────────── */}
        <main className="flex flex-1 flex-col overflow-hidden bg-[#141414]">
          {/* Editor Container */}
          <div
            className={`flex-1 overflow-hidden transition-all duration-300 ${
              result ? "h-1/2" : "h-full"
            }`}
          >
            <CodeEditor value={code} onChange={setCode} language="python" />
          </div>

          {/* Action Bar */}
          <div className="flex items-center justify-between border-t-2 border-black bg-[#141414] px-5 py-3">
            <div className="flex items-center gap-3">
              <span className="font-mono text-xs text-slate-400">
                {code.split("\n").length} lines · Python 3.11 Sandbox
              </span>
              {submitError && (
                <span className="font-mono text-xs text-[#DE6557] font-bold">
                  {submitError}
                </span>
              )}
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={handleSubmit}
                disabled={submitting}
                id="run-submit-button"
                className="btn-terracotta px-6 py-2.5 text-xs tracking-wider flex items-center gap-2"
              >
                {submitting ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    <span>RUNNING SANDBOX…</span>
                  </>
                ) : (
                  <>
                    <Play className="h-3.5 w-3.5 fill-current" />
                    <span>RUN &amp; SUBMIT</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Feedback & Hint UI Panel */}
          {result && (
            <div className="h-1/2 overflow-y-auto border-t-2 border-black bg-[#141414] p-6 transition-all">
              <SubmissionFeedback
                result={result}
                onReset={() => {
                  setResult(null);
                  setCode(challenge.starter_code);
                  setHintsUsed(0);
                }}
                onHintUsed={(count) => setHintsUsed(count)}
              />
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

export default function ChallengePage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-screen items-center justify-center bg-[#141414]">
          <Loader2 className="h-8 w-8 animate-spin text-[#DE6557]" />
        </div>
      }
    >
      <ChallengePageInner />
    </Suspense>
  );
}
