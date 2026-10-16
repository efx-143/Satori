"use client";
// components/SubmissionFeedback.tsx
// Phase 5: Feedback & Hint UI Component — MXESA [26] Neo-Brutalist Theme
// Handles response from POST /api/v1/submissions:
//   1. Displays canonical outcome: passed, wrong_output, runtime_error, timeout
//   2. Displays plain-language AI explanation
//   3. Hint System: "Stuck? Get a Hint" calling POST /api/v1/hints/<sub_id>
//      revealing the 3 progressive hints ONE BY ONE per click (never all at once)
//   4. Highlights recurring mistake alerts with "Practice Next" recommendation

import { useState } from "react";
import { useRouter } from "next/navigation";
import type { SubmissionResponse, HintResponse, RecurringTag } from "@/types";
import { generateHints } from "@/lib/api";
import {
  CheckCircle2,
  XCircle,
  Clock,
  Zap,
  Lightbulb,
  ChevronRight,
  RotateCcw,
  Trophy,
  AlertTriangle,
  Loader2,
  Sparkles,
  Info,
  Terminal,
} from "lucide-react";

// ── Outcome Badges & Styles (MXESA Neo-Brutalist Theme) ───────────────────

interface OutcomeStyle {
  icon: typeof CheckCircle2;
  label: string;
  badgeClass: string;
}

const OUTCOME_CONFIG: Record<string, OutcomeStyle> = {
  passed: {
    icon: CheckCircle2,
    label: "ALL TESTS PASSED",
    badgeClass: "bg-[#E8E6DB] text-black border-2 border-black shadow-[4px_4px_0px_#000]",
  },
  wrong_output: {
    icon: XCircle,
    label: "WRONG OUTPUT",
    badgeClass: "bg-[#DE6557] text-black border-2 border-black shadow-[4px_4px_0px_#000]",
  },
  failed: {
    icon: XCircle,
    label: "WRONG OUTPUT",
    badgeClass: "bg-[#DE6557] text-black border-2 border-black shadow-[4px_4px_0px_#000]",
  },
  runtime_error: {
    icon: Zap,
    label: "RUNTIME ERROR",
    badgeClass: "bg-[#E5A83B] text-black border-2 border-black shadow-[4px_4px_0px_#000]",
  },
  error: {
    icon: Zap,
    label: "RUNTIME ERROR",
    badgeClass: "bg-[#E5A83B] text-black border-2 border-black shadow-[4px_4px_0px_#000]",
  },
  timeout: {
    icon: Clock,
    label: "EXECUTION TIMEOUT",
    badgeClass: "bg-[#DE6557] text-black border-2 border-black shadow-[4px_4px_0px_#000]",
  },
};

const MISTAKE_LABELS: Record<string, string> = {
  off_by_one: "Off-by-one indexing error",
  unhandled_short_input: "Unhandled empty/short input",
  print_not_return: "print() instead of return",
  boundary_comparison: "Boundary comparison (< vs <=)",
  mutates_input: "Mutates input argument in-place",
};

const HINT_TIER_NAMES = [
  "Hint 1: Conceptual Direction",
  "Hint 2: Execution & Edge Trace",
  "Hint 3: Targeted Guardrail",
];

// ── Test Progress Bar ──────────────────────────────────────────────────────

function TestProgress({ passed, total }: { passed: number; total: number }) {
  const pct = total > 0 ? Math.round((passed / total) * 100) : 0;
  return (
    <div className="space-y-1.5 border-2 border-black bg-[#1A1A1A] p-4 shadow-[3px_3px_0px_#000]">
      <div className="flex items-center justify-between text-xs font-mono">
        <span className="font-bold text-slate-300 uppercase tracking-wider">
          TEST RUNS PASSED
        </span>
        <span className="font-bold text-[#DE6557]">
          {passed} / {total} ({pct}%)
        </span>
      </div>
      <div className="h-3 w-full border-2 border-black bg-[#141414] overflow-hidden">
        <div
          className={`h-full transition-all duration-700 ${
            pct === 100 ? "bg-[#E5A83B]" : pct > 50 ? "bg-[#9BBBDD]" : "bg-[#DE6557]"
          }`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

// ── Progressive Hint Ladder ────────────────────────────────────────────────

interface HintLadderProps {
  submissionId: string;
  onHintRevealed?: (count: number) => void;
}

function ProgressiveHintLadder({
  submissionId,
  onHintRevealed,
}: HintLadderProps) {
  const [hints, setHints] = useState<string[]>([]);
  const [revealedCount, setRevealedCount] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const MAX_HINTS = 3;

  async function handleGetHint() {
    if (loading || revealedCount >= MAX_HINTS) return;

    if (hints.length === 0) {
      setLoading(true);
      setError(null);
      try {
        const res: HintResponse = await generateHints(submissionId);
        const ladder = [res.hint_1, res.hint_2, res.hint_3].filter(
          Boolean
        ) as string[];

        if (ladder.length === 0) {
          setError("No hints available for this submission.");
          return;
        }

        setHints(ladder);
        setRevealedCount(1);
        onHintRevealed?.(1);
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Failed to load hint.");
      } finally {
        setLoading(false);
      }
    } else {
      const nextCount = Math.min(revealedCount + 1, hints.length);
      setRevealedCount(nextCount);
      onHintRevealed?.(nextCount);
    }
  }

  const allRevealed = hints.length > 0 && revealedCount >= hints.length;

  const getButtonLabel = () => {
    if (loading) return "ANALYZING RECURRING MISTAKES…";
    if (revealedCount === 0) return "STUCK? GET A HINT";
    if (revealedCount === 1) return "STUCK? GET HINT 2 (OF 3)";
    if (revealedCount === 2) return "STUCK? GET FINAL HINT (3 OF 3)";
    return "ALL 3 HINTS REVEALED";
  };

  return (
    <div className="space-y-4 border-2 border-black bg-[#1A1A1A] p-5 shadow-[4px_4px_0px_#000]">
      <div className="flex items-center justify-between border-b-2 border-black pb-3">
        <div className="flex items-center gap-2">
          <Lightbulb className="h-4 w-4 text-[#DE6557]" />
          <h4 className="font-mono text-xs font-bold uppercase tracking-wider text-white">
            PROGRESSIVE HINT LADDER
          </h4>
        </div>
        <span className="badge-black">
          {revealedCount} / {MAX_HINTS} REVEALED
        </span>
      </div>

      <p className="text-xs text-slate-300 font-sans leading-relaxed">
        Hints point you in the right direction without leaking code. Each step is
        more concrete than the last.
      </p>

      {/* ── Revealed Hints (one-by-one only) ───────────────────────────── */}
      {revealedCount > 0 && (
        <div className="space-y-3 pt-1">
          {hints.slice(0, revealedCount).map((hint, idx) => (
            <div
              key={idx}
              className="border-2 border-black bg-[#E8E6DB] text-black p-4 shadow-[3px_3px_0px_#8B2019] space-y-1.5 transition-all animate-in"
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-[11px] font-bold uppercase tracking-wider text-[#8B2019]">
                  {HINT_TIER_NAMES[idx] ?? `Hint ${idx + 1}`}
                </span>
                <span className="bg-black text-white px-2 py-0.5 font-mono text-[10px] font-bold">
                  STEP #{idx + 1}
                </span>
              </div>
              <p className="text-xs leading-relaxed font-sans text-slate-900 font-medium">
                {hint}
              </p>
            </div>
          ))}
        </div>
      )}

      {error && (
        <p className="font-mono text-xs text-[#DE6557] font-bold">{error}</p>
      )}

      {/* ── Hint Trigger Button ────────────────────────────────────────── */}
      <div className="pt-2">
        <button
          onClick={handleGetHint}
          disabled={loading || allRevealed}
          id="get-hint-button"
          className={`w-full py-3 text-xs tracking-wider flex items-center justify-center gap-2 transition-all ${
            allRevealed
              ? "border-2 border-black bg-[#292825] text-slate-500 font-mono font-bold cursor-not-allowed shadow-none"
              : "btn-terracotta"
          }`}
        >
          {loading ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin text-black" />
              <span>CONSULTING AI TUTOR…</span>
            </>
          ) : (
            <>
              <Lightbulb className="h-4 w-4" />
              <span>{getButtonLabel()}</span>
            </>
          )}
        </button>

        {revealedCount > 0 && !allRevealed && (
          <p className="mt-2 font-mono text-[10px] text-slate-400 text-center uppercase tracking-wider">
            ⚠️ Passes with fewer hints yield greater mastery points.
          </p>
        )}
      </div>
    </div>
  );
}

// ── Main SubmissionFeedback Component ──────────────────────────────────────

interface SubmissionFeedbackProps {
  result: SubmissionResponse;
  onReset?: () => void;
  onHintUsed?: (count: number) => void;
}

export default function SubmissionFeedback({
  result,
  onReset,
  onHintUsed,
}: SubmissionFeedbackProps) {
  const router = useRouter();

  const outcomeKey = result.outcome ?? "error";
  const cfg = OUTCOME_CONFIG[outcomeKey] ?? OUTCOME_CONFIG.error;
  const OutcomeIcon = cfg.icon;
  const isPassed = result.outcome === "passed";

  const recurringTags: RecurringTag[] =
    result.recurring?.recurring_tags ?? [];

  const explanationSummary =
    typeof result.explanation === "object" && result.explanation !== null
      ? result.explanation.summary
      : "";
  const explanationBody =
    typeof result.explanation === "object" && result.explanation !== null
      ? result.explanation.body
      : typeof result.explanation === "string"
      ? result.explanation
      : "";

  return (
    <div className="flex flex-col gap-5 text-[#F0EFEA]">
      {/* ── 1. Outcome Header Banner (Brutalist Banner) ─────────────────── */}
      <div
        className={`flex items-center justify-between p-4 ${cfg.badgeClass} transition-all`}
      >
        <div className="flex items-center gap-3">
          <OutcomeIcon className="h-6 w-6 flex-shrink-0 text-black stroke-[2.5]" />
          <div>
            <h3 className="font-mono text-base font-black tracking-wider uppercase text-black">
              {cfg.label}
            </h3>
            <p className="text-[11px] font-mono text-slate-900 font-bold uppercase tracking-wide">
              {isPassed
                ? "All tests passed · AST clean"
                : "Diagnostics generated · Sandbox contained run safely"}
            </p>
          </div>
        </div>

        {isPassed && result.xp_awarded > 0 && (
          <div className="bg-black text-white px-3 py-1 font-mono text-xs font-bold border border-black shadow-[2px_2px_0px_#000]">
            +{result.xp_awarded} XP
          </div>
        )}
      </div>

      {/* ── 2. Test Execution Progress ─────────────────────────────────── */}
      <TestProgress passed={result.passed_tests} total={result.total_tests} />

      {/* ── 3. Plain-Language AI Explanation ───────────────────────────── */}
      {(explanationSummary || explanationBody) && (
        <div className="border-2 border-black bg-[#1A1A1A] p-5 shadow-[4px_4px_0px_#000] space-y-2.5">
          <div className="flex items-center justify-between border-b-2 border-black pb-2">
            <span className="font-mono text-[11px] font-bold uppercase tracking-wider text-[#DE6557]">
              AI FORENSIC EXPLANATION
            </span>
            <span className="font-mono text-[10px] text-slate-400 uppercase">
              PLAIN LANGUAGE AUTOPSY
            </span>
          </div>

          {explanationSummary && (
            <p className="font-mono text-xs font-bold text-white">
              {explanationSummary}
            </p>
          )}

          {explanationBody && (
            <p className="text-xs leading-relaxed text-slate-300 font-sans whitespace-pre-line">
              {explanationBody}
            </p>
          )}
        </div>
      )}

      {/* ── 4. Detected AST Mistake Tags ───────────────────────────────── */}
      {result.mistake_tags && result.mistake_tags.length > 0 && (
        <div className="space-y-2">
          <span className="font-mono text-[11px] font-bold uppercase tracking-wider text-slate-400 block">
            DIAGNOSED CODE PATTERNS
          </span>
          <div className="flex flex-wrap gap-2">
            {result.mistake_tags.map((tag) => (
              <span
                key={tag}
                className="border-2 border-black bg-[#E5A83B] text-black px-2.5 py-1 font-mono text-xs font-bold shadow-[2px_2px_0px_#000]"
              >
                #{MISTAKE_LABELS[tag] ?? tag}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* ── 5. Recurring Mistake Alert with Practice Next ──────────────── */}
      {recurringTags.length > 0 && (
        <div className="border-2 border-black bg-[#DE6557]/15 p-5 shadow-brutal-red space-y-4">
          <div className="flex items-center justify-between border-b-2 border-black pb-2">
            <div className="flex items-center gap-2 text-[#DE6557]">
              <AlertTriangle className="h-4 w-4 flex-shrink-0" />
              <h4 className="font-mono text-xs font-bold uppercase tracking-wider text-white">
                RECURRING MISTAKE FLAGGED
              </h4>
            </div>
            <span className="badge-black">RECURRENCE RULE TRIGGERED</span>
          </div>

          {recurringTags.map((rt: RecurringTag) => (
            <div
              key={rt.tag}
              className="space-y-3 border-2 border-black bg-[#141414] p-4 text-white shadow-[3px_3px_0px_#000]"
            >
              <p className="text-xs text-slate-300 font-sans leading-relaxed">
                <span className="font-bold text-[#DE6557] font-mono">
                  #{rt.tag}
                </span>{" "}
                has now appeared in{" "}
                <span className="font-bold text-white">
                  {rt.occurrences} separate challenges
                </span>
                .
              </p>

              {rt.suggested_challenge_id && (
                <button
                  onClick={() =>
                    router.push(`/challenge/${rt.suggested_challenge_id}`)
                  }
                  id="practice-next-btn"
                  className="btn-terracotta w-full py-2.5 text-xs flex items-center justify-between px-3"
                >
                  <div className="flex items-center gap-1.5 truncate">
                    <span>PRACTICE TARGETED FIX:</span>
                    <span className="font-black text-black truncate">
                      {rt.suggested_challenge_title ?? rt.suggested_challenge_id}
                    </span>
                  </div>
                  <ChevronRight className="h-4 w-4 flex-shrink-0" />
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {/* ── 6. Progressive Hint Ladder (for failing submissions) ────────── */}
      {!isPassed && (
        <ProgressiveHintLadder
          submissionId={result.submission_id}
          onHintRevealed={onHintUsed}
        />
      )}

      {/* ── 7. Clean Pass Celebration ──────────────────────────────────── */}
      {isPassed && (
        <div className="border-2 border-black bg-[#E8E6DB] text-black p-6 text-center space-y-3 shadow-brutal-red">
          <Trophy className="mx-auto h-8 w-8 text-black" />
          <h4 className="font-mono text-base font-black uppercase tracking-wider">
            CHALLENGE SOLVED CLEANLY
          </h4>
          <p className="text-xs text-slate-800 font-medium font-sans max-w-sm mx-auto">
            Forensic analysis passed all constraints. Concept mastery estimates
            have been recorded.
          </p>
        </div>
      )}

      {/* ── 8. Bottom Action Controls ─────────────────────────────────── */}
      <div className="flex items-center gap-4 pt-2">
        {onReset && (
          <button
            onClick={onReset}
            className="btn-dark flex-1 py-3 text-xs flex items-center justify-center gap-2"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            <span>RESET CODE</span>
          </button>
        )}

        <button
          onClick={() => router.push("/dashboard")}
          className="btn-terracotta flex-1 py-3 text-xs flex items-center justify-center gap-2"
        >
          <span>VIEW DASHBOARD</span>
          <ChevronRight className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}
