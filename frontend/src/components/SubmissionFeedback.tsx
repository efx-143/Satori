"use client";
// components/SubmissionFeedback.tsx
// Handles the full judging response: outcome badge, AI explanation,
// test case results, and a progressive 3-hint ladder revealed one at a time.

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
} from "lucide-react";

// ── Outcome config ────────────────────────────────────────────────────────

const OUTCOME_CONFIG = {
  passed: {
    icon: CheckCircle2,
    label: "All Tests Passed!",
    color: "text-emerald-400",
    bg: "bg-emerald-500/10 border-emerald-500/30",
    glow: "shadow-[0_0_20px_rgba(16,185,129,0.15)]",
  },
  failed: {
    icon: XCircle,
    label: "Wrong Output",
    color: "text-rose-400",
    bg: "bg-rose-500/10 border-rose-500/30",
    glow: "shadow-[0_0_20px_rgba(244,63,94,0.15)]",
  },
  error: {
    icon: Zap,
    label: "Runtime Error",
    color: "text-amber-400",
    bg: "bg-amber-500/10 border-amber-500/30",
    glow: "shadow-[0_0_20px_rgba(245,158,11,0.15)]",
  },
  timeout: {
    icon: Clock,
    label: "Time Limit Exceeded",
    color: "text-orange-400",
    bg: "bg-orange-500/10 border-orange-500/30",
    glow: "shadow-[0_0_20px_rgba(249,115,22,0.15)]",
  },
} as const;

const MISTAKE_LABELS: Record<string, string> = {
  off_by_one:            "Off-by-one error",
  unhandled_short_input: "Unhandled short/empty input",
  print_not_return:      "print() instead of return",
  boundary_comparison:   "Incorrect boundary comparison",
  mutates_input:         "Mutates the input argument",
};

// ── Sub-components ────────────────────────────────────────────────────────

function OutcomeBadge({ outcome }: { outcome: keyof typeof OUTCOME_CONFIG }) {
  const cfg = OUTCOME_CONFIG[outcome];
  const Icon = cfg.icon;
  return (
    <div className={`flex items-center gap-3 rounded-xl border p-4 ${cfg.bg} ${cfg.glow}`}>
      <Icon className={`h-7 w-7 flex-shrink-0 ${cfg.color}`} />
      <span className={`text-xl font-bold ${cfg.color}`}>{cfg.label}</span>
    </div>
  );
}

function TestProgress({
  passed,
  total,
}: {
  passed: number;
  total: number;
}) {
  const pct = total > 0 ? Math.round((passed / total) * 100) : 0;
  return (
    <div className="space-y-2">
      <div className="flex justify-between text-sm">
        <span className="text-slate-400">Tests passed</span>
        <span className="font-mono font-semibold text-slate-200">
          {passed} / {total}
        </span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-slate-700">
        <div
          className="h-full rounded-full bg-gradient-to-r from-violet-500 to-emerald-500 transition-all duration-700"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

// Progressive hint display
function HintLadder({
  submissionId,
  hintsUsedCount,
  onHintRevealed,
}: {
  submissionId: string;
  hintsUsedCount: number;
  onHintRevealed: () => void;
}) {
  const [hints, setHints] = useState<string[]>([]);
  const [revealed, setRevealed] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const MAX_HINTS = 3;

  async function fetchHints() {
    if (hints.length === 0) {
      setLoading(true);
      setError(null);
      try {
        const res: HintResponse = await generateHints(submissionId);
        const arr = [res.hint_1, res.hint_2, res.hint_3].filter(Boolean) as string[];
        setHints(arr);
        setRevealed(1);
        onHintRevealed();
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Failed to load hint.");
      } finally {
        setLoading(false);
      }
    } else if (revealed < hints.length) {
      setRevealed((r) => r + 1);
      onHintRevealed();
    }
  }

  const allRevealed = hints.length > 0 && revealed >= hints.length;
  const btnLabel = loading
    ? "Getting hint…"
    : hints.length === 0
    ? "💡 Get Hint 1"
    : revealed < hints.length
    ? `💡 Reveal Hint ${revealed + 1}`
    : "No more hints";

  return (
    <div className="space-y-3">
      {/* Revealed hints */}
      {hints.slice(0, revealed).map((hint, i) => (
        <div
          key={i}
          className="flex gap-3 rounded-lg border border-violet-500/20 bg-violet-500/5 p-4 animate-in slide-in-from-bottom-2 duration-300"
        >
          <div className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-violet-500/20 text-xs font-bold text-violet-400">
            {i + 1}
          </div>
          <p className="text-sm leading-relaxed text-slate-300">{hint}</p>
        </div>
      ))}

      {error && (
        <p className="text-sm text-rose-400">{error}</p>
      )}

      {/* Hint counter warning */}
      {hintsUsedCount > 0 && (
        <p className="text-xs text-slate-500">
          ⚠️ Using hints reduces XP reward. Currently used: {hintsUsedCount}
        </p>
      )}

      {!allRevealed && (
        <button
          onClick={fetchHints}
          disabled={loading}
          className="flex w-full items-center justify-center gap-2 rounded-lg border border-violet-500/30 bg-violet-500/10 px-4 py-3 text-sm font-medium text-violet-300 transition-all hover:bg-violet-500/20 hover:border-violet-400/50 disabled:opacity-50"
        >
          <Lightbulb className="h-4 w-4" />
          {btnLabel}
        </button>
      )}
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────

interface Props {
  result: SubmissionResponse;
  onReset: () => void;
}

export default function SubmissionFeedback({ result, onReset }: Props) {
  const router = useRouter();
  const [hintsUsed, setHintsUsed] = useState(0);
  const [showHints, setShowHints] = useState(false);

  const cfg = OUTCOME_CONFIG[result.outcome] ?? OUTCOME_CONFIG.error;
  const isPassed = result.outcome === "passed";
  const recurringTags = result.recurring?.recurring_tags ?? [];

  return (
    <div className="flex flex-col gap-4">
      {/* ── Outcome banner ─────────────────────────────────────────────── */}
      <OutcomeBadge outcome={result.outcome} />

      {/* ── Stats row ──────────────────────────────────────────────────── */}
      <div className="grid grid-cols-3 gap-3">
        <div className="rounded-lg border border-white/5 bg-white/3 p-3 text-center">
          <p className="text-xs text-slate-500">XP Earned</p>
          <p className="text-lg font-bold text-violet-400">
            +{result.xp_awarded}
          </p>
        </div>
        <div className="rounded-lg border border-white/5 bg-white/3 p-3 text-center">
          <p className="text-xs text-slate-500">Total XP</p>
          <p className="text-lg font-bold text-slate-200">
            {result.new_total_xp}
          </p>
        </div>
        <div className="rounded-lg border border-white/5 bg-white/3 p-3 text-center">
          <p className="text-xs text-slate-500">Time</p>
          <p className="text-lg font-bold text-slate-200">
            {result.execution_ms != null
              ? `${result.execution_ms.toFixed(0)}ms`
              : "—"}
          </p>
        </div>
      </div>

      {/* ── Test progress ───────────────────────────────────────────────── */}
      <TestProgress
        passed={result.passed_tests}
        total={result.total_tests}
      />

      {/* ── AI Explanation ──────────────────────────────────────────────── */}
      {result.explanation && !isPassed && (
        <div className="rounded-xl border border-slate-700/50 bg-slate-800/40 p-4 space-y-2">
          <p className="text-sm font-semibold text-slate-300">
            🤖 AI Explanation
          </p>
          <p className="text-sm font-medium text-slate-200">
            {result.explanation.summary}
          </p>
          <p className="text-sm leading-relaxed text-slate-400 whitespace-pre-line">
            {result.explanation.body}
          </p>
        </div>
      )}

      {/* ── Mistake tags ────────────────────────────────────────────────── */}
      {result.mistake_tags.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {result.mistake_tags.map((tag) => (
            <span
              key={tag}
              className="rounded-full border border-amber-500/30 bg-amber-500/10 px-3 py-1 text-xs text-amber-400"
            >
              {MISTAKE_LABELS[tag] ?? tag}
            </span>
          ))}
        </div>
      )}

      {/* ── Recurring mistake alert ─────────────────────────────────────── */}
      {recurringTags.length > 0 && (
        <div className="rounded-xl border border-rose-500/30 bg-rose-500/5 p-4 space-y-3">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-rose-400" />
            <p className="text-sm font-semibold text-rose-300">
              Recurring Pattern Detected
            </p>
          </div>
          {recurringTags.map((rt: RecurringTag) => (
            <div key={rt.tag} className="space-y-2">
              <p className="text-xs text-slate-400">
                <span className="font-medium text-rose-300">
                  {MISTAKE_LABELS[rt.tag] ?? rt.tag}
                </span>{" "}
                appeared in {rt.occurrences} other challenge(s).
              </p>
              {rt.suggested_challenge_id && (
                <button
                  onClick={() =>
                    router.push(`/challenge/${rt.suggested_challenge_id}`)
                  }
                  className="flex items-center gap-2 rounded-lg border border-violet-500/40 bg-violet-500/10 px-3 py-2 text-xs font-medium text-violet-300 hover:bg-violet-500/20 transition-all"
                >
                  <ChevronRight className="h-3 w-3" />
                  Practice Next:{" "}
                  <span className="font-semibold">
                    {rt.suggested_challenge_title}
                  </span>
                  <span className="ml-auto rounded border border-violet-500/20 px-1.5 py-0.5 text-[10px]">
                    {rt.suggested_challenge_difficulty}
                  </span>
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {/* ── Mastery updates ─────────────────────────────────────────────── */}
      {result.mastery_updates.length > 0 && (
        <div className="rounded-xl border border-white/5 bg-white/3 p-4 space-y-2">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            Mastery Updated
          </p>
          {result.mastery_updates.map((m) => (
            <div key={m.concept_tag} className="flex items-center gap-3">
              <span className="w-24 truncate text-xs text-slate-400">
                {m.concept_tag}
              </span>
              <div className="flex-1 h-1.5 rounded-full bg-slate-700 overflow-hidden">
                <div
                  className="h-full rounded-full bg-violet-500 transition-all duration-700"
                  style={{ width: `${Math.min(100, m.new_score)}%` }}
                />
              </div>
              <span
                className={`text-xs font-mono ${
                  m.delta > 0 ? "text-emerald-400" : "text-rose-400"
                }`}
              >
                {m.delta > 0 ? "+" : ""}
                {m.delta.toFixed(1)}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* ── Hints section ───────────────────────────────────────────────── */}
      {!isPassed && (
        <div className="rounded-xl border border-slate-700/50 bg-slate-800/40 p-4 space-y-3">
          <button
            onClick={() => setShowHints((s) => !s)}
            className="flex w-full items-center justify-between text-sm font-medium text-slate-300"
          >
            <span className="flex items-center gap-2">
              <Lightbulb className="h-4 w-4 text-violet-400" />
              Stuck? Get progressive hints
            </span>
            <ChevronRight
              className={`h-4 w-4 text-slate-500 transition-transform ${
                showHints ? "rotate-90" : ""
              }`}
            />
          </button>
          {showHints && (
            <HintLadder
              submissionId={result.submission_id}
              hintsUsedCount={hintsUsed}
              onHintRevealed={() => setHintsUsed((n) => n + 1)}
            />
          )}
        </div>
      )}

      {/* ── Pass celebration ────────────────────────────────────────────── */}
      {isPassed && (
        <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4 text-center">
          <Trophy className="mx-auto h-8 w-8 text-emerald-400 mb-2" />
          <p className="text-sm text-emerald-300 font-medium">
            Excellent work! You solved it
            {hintsUsed === 0 ? " without any hints 🔥" : ` with ${hintsUsed} hint${hintsUsed > 1 ? "s" : ""}`}.
          </p>
        </div>
      )}

      {/* ── Actions ─────────────────────────────────────────────────────── */}
      <div className="flex gap-3 pt-1">
        <button
          onClick={onReset}
          className="flex flex-1 items-center justify-center gap-2 rounded-lg border border-slate-600 bg-slate-800 px-4 py-2.5 text-sm text-slate-300 hover:bg-slate-700 transition-all"
        >
          <RotateCcw className="h-4 w-4" />
          Try Again
        </button>
        <button
          onClick={() => router.push("/dashboard")}
          className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-violet-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-violet-500 transition-all"
        >
          Dashboard
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
