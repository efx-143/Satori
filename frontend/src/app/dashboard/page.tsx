"use client";
// app/dashboard/page.tsx
// Phase 5: Learner Dashboard — MXESA [26] Neo-Brutalist Theme
// Fetches from GET /api/v1/learners/<id>/dashboard:
//   1. Displays "Concept Mastery" as clean, high-contrast brutalist progress bars
//   2. Recurring Mistakes Alert: shows any mistake_tags flagged as "recurring"
//      with a "Practice Next" button linking to the exact challenge targeting that mistake.

import { useEffect, useState, Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { getDashboard } from "@/lib/api";
import type {
  DashboardData,
  MasteryRecord,
  RecentSubmission,
  RecurringTag,
} from "@/types";
import {
  Flame,
  Trophy,
  Target,
  BookOpen,
  ChevronRight,
  AlertTriangle,
  Loader2,
  CheckCircle2,
  XCircle,
  Clock,
  Zap,
  TrendingUp,
  LayoutDashboard,
  ShieldAlert,
  ArrowRight,
  Check,
  Terminal,
} from "lucide-react";

// Default pseudonymous learner ID
const DEFAULT_LEARNER_ID = "00000000-0000-0000-0000-000000000001";

const MISTAKE_DESCRIPTIONS: Record<
  string,
  { label: string; explanation: string; remedy: string }
> = {
  off_by_one: {
    label: "Off-by-one indexing error",
    explanation:
      "Loop counters or slice endpoints reach one element too far or terminate early.",
    remedy: "Trace range() endpoints and 0-indexed bounds carefully.",
  },
  unhandled_short_input: {
    label: "Unhandled short or empty input",
    explanation:
      "Program raises IndexError or computes inaccurate sum when list length < k or empty.",
    remedy: "Add explicit length check guardrails at function entry.",
  },
  print_not_return: {
    label: "Printed output instead of returning value",
    explanation:
      "Invoked print() instead of return statement, passing None back to test harness.",
    remedy: "Always return the computed result object.",
  },
  boundary_comparison: {
    label: "Incorrect boundary comparison",
    explanation:
      "Used strict comparison (< or >) instead of inclusive comparison (<= or >=).",
    remedy: "Check pass/fail boundary thresholds (e.g., mark >= 40).",
  },
  mutates_input: {
    label: "Mutates caller's input argument",
    explanation:
      "Mutated list in-place (e.g. pop, sort, del) violating pure function expectations.",
    remedy: "Operate on a shallow slice copy or use non-destructive operations.",
  },
};

const OUTCOME_ICONS: Record<string, React.ReactNode> = {
  passed: <CheckCircle2 className="h-4 w-4 text-emerald-600 stroke-[2.5]" />,
  wrong_output: <XCircle className="h-4 w-4 text-[#DE6557] stroke-[2.5]" />,
  failed: <XCircle className="h-4 w-4 text-[#DE6557] stroke-[2.5]" />,
  runtime_error: <Zap className="h-4 w-4 text-[#E5A83B] stroke-[2.5]" />,
  error: <Zap className="h-4 w-4 text-[#E5A83B] stroke-[2.5]" />,
  timeout: <Clock className="h-4 w-4 text-orange-600 stroke-[2.5]" />,
};

// ── Gamification Stat Card (MXESA Neo-Brutalist Card) ──────────────────────

function StatCard({
  icon,
  label,
  value,
  sub,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  sub?: string;
}) {
  return (
    <div className="border-2 border-black bg-white text-black p-5 space-y-2 shadow-[4px_4px_0px_#000] hover:translate-x-[-1px] hover:translate-y-[-1px] transition-all">
      <div className="flex items-center justify-between">
        <span className="font-mono text-[10px] font-bold uppercase tracking-wider text-slate-600">
          {label}
        </span>
        <span>{icon}</span>
      </div>
      <p className="text-3xl font-black text-black tracking-tight font-mono">
        {value}
      </p>
      {sub && (
        <p className="font-mono text-[11px] text-slate-500 font-medium">{sub}</p>
      )}
    </div>
  );
}

// ── Concept Mastery Progress Bar (MXESA Neo-Brutalist Track) ──────────────

function ConceptProgressBar({ item }: { item: MasteryRecord }) {
  const score = Math.round(item.mastery_score);

  let tierLabel = "DEVELOPING";
  let tierBadge = "bg-[#DE6557] text-black border border-black";
  let barColor = "bg-[#DE6557]";

  if (score >= 80) {
    tierLabel = "MASTERED";
    tierBadge = "bg-[#E5A83B] text-black border border-black";
    barColor = "bg-[#E5A83B]";
  } else if (score >= 50) {
    tierLabel = "PROFICIENT";
    tierBadge = "bg-[#9BBBDD] text-black border border-black";
    barColor = "bg-[#9BBBDD]";
  }

  return (
    <div className="border-2 border-black bg-white text-black p-4 space-y-2.5 shadow-[3px_3px_0px_#000]">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="font-mono font-bold text-sm uppercase text-black">
            {item.concept_tag}
          </span>
          <span className={`px-2 py-0.5 font-mono text-[10px] font-bold ${tierBadge}`}>
            {tierLabel}
          </span>
        </div>

        <div className="flex items-center gap-3 font-mono">
          <span className="text-[11px] text-slate-600 font-medium">
            {item.correct_attempts}/{item.attempts} SOLVED
          </span>
          <span className="text-sm font-black text-black">{score}%</span>
        </div>
      </div>

      {/* Neo-brutalist Progress Track & Bar */}
      <div className="h-3.5 w-full border-2 border-black bg-[#141414] overflow-hidden">
        <div
          className={`h-full ${barColor} transition-all duration-700 ease-out`}
          style={{ width: `${Math.max(4, score)}%` }}
        />
      </div>
    </div>
  );
}

// ── Inner Dashboard Content ────────────────────────────────────────────────

function DashboardContent() {
  const searchParams = useSearchParams();
  const learnerId = searchParams.get("learner_id") || DEFAULT_LEARNER_ID;

  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    getDashboard(learnerId)
      .then((res) => {
        setData(res);
        setError(null);
      })
      .catch((err) => {
        setError(
          err instanceof Error
            ? err.message
            : "Failed to load dashboard data."
        );
      })
      .finally(() => setLoading(false));
  }, [learnerId]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#141414]">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-[#DE6557]" />
          <span className="font-mono text-xs font-bold text-slate-300">
            FETCHING LEARNER TELEMETRY…
          </span>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#141414]">
        <div className="text-center space-y-4 p-8 border-2 border-black bg-[#E8E6DB] text-black max-w-md shadow-brutal-red">
          <p className="font-mono text-sm font-bold text-[#8B2019]">
            {error ?? "DASHBOARD UNAVAILABLE"}
          </p>
          <Link
            href="/"
            className="btn-terracotta inline-flex items-center gap-1.5 px-4 py-2 text-xs"
          >
            ← BACK TO CHALLENGES
          </Link>
        </div>
      </div>
    );
  }

  const { learner, stats, mastery, weakest_topics, recent_submissions } = data;
  const recurringMistakes: RecurringTag[] = data.recurring_mistakes ?? [];

  return (
    <div className="min-h-screen bg-[#141414] text-[#F0EFEA] font-sans selection:bg-[#DE6557] selection:text-black">
      {/* ── Top Header ────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-30 border-b-2 border-black bg-[#141414]/95 px-6 py-4 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between">
          <div className="flex items-center gap-3">
            <Link
              href="/"
              className="text-2xl font-black tracking-tight text-white font-mono hover:text-[#DE6557] transition-colors"
            >
              DEBUG DOJO <span className="text-[#DE6557]">[26]</span>
            </Link>
            <div className="h-4 w-px bg-slate-700 mx-1" />
            <span className="font-mono text-xs text-slate-400 uppercase hidden sm:inline">
              LEARNER DOSSIER
            </span>
          </div>

          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1.5 bg-black text-[#E5A83B] px-3 py-1 font-mono text-xs font-bold border-2 border-black shadow-[2px_2px_0px_#000]">
              <Flame className="h-3.5 w-3.5 text-[#E5A83B]" />
              <span>{stats.streak_days} DAY STREAK</span>
            </div>

            <div className="flex items-center gap-2">
              <div className="h-8 w-8 bg-[#DE6557] border-2 border-black flex items-center justify-center font-mono text-xs font-black text-black shadow-[2px_2px_0px_#000]">
                {learner.display_name.charAt(0).toUpperCase()}
              </div>
              <span className="font-mono text-xs font-bold text-white hidden sm:inline">
                {learner.display_name}
              </span>
            </div>
          </div>
        </div>
      </header>

      {/* ── Main Container ────────────────────────────────────────────── */}
      <main className="mx-auto max-w-6xl space-y-10 px-6 py-10">
        {/* Welcome Section */}
        <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-6 border-b-2 border-black pb-8">
          <div className="space-y-2">
            {/* 3-color swatch */}
            <div className="flex items-center gap-2 mb-1">
              <div className="flex h-1.5 w-8 border border-black">
                <div className="w-1/3 bg-[#DE6557]" />
                <div className="w-1/3 bg-[#E5A83B]" />
                <div className="w-1/3 bg-[#9BBBDD]" />
              </div>
              <p className="font-mono text-[10px] font-bold tracking-widest uppercase text-[#DE6557]">
                ID: {learner.id}
              </p>
            </div>
            <h1 className="text-3xl sm:text-5xl font-black uppercase tracking-tight text-white">
              Welcome, {learner.display_name}.
            </h1>
            <p className="text-xs sm:text-sm text-slate-300 font-sans max-w-xl">
              Forensic practice records: concept mastery scores evolve dynamically
              with each sandboxed execution run.
            </p>
          </div>

          <Link
            href="/"
            className="btn-terracotta px-5 py-2.5 text-xs tracking-wider flex items-center gap-2 self-start sm:self-auto"
          >
            <BookOpen className="h-4 w-4" />
            <span>CHALLENGE REPOSITORY</span>
          </Link>
        </div>

        {/* ── Stat Cards Grid (MXESA Committee Style) ─────────────────── */}
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <StatCard
            icon={<Trophy className="h-5 w-5 text-[#E5A83B]" />}
            label="TOTAL XP"
            value={stats.xp_points.toLocaleString()}
            sub="Earned on clean passes"
          />
          <StatCard
            icon={<Flame className="h-5 w-5 text-[#DE6557]" />}
            label="DAY STREAK"
            value={`${stats.streak_days}D`}
            sub="Consecutive practice"
          />
          <StatCard
            icon={<Target className="h-5 w-5 text-[#9BBBDD]" />}
            label="PASS RATE"
            value={`${Math.round(stats.pass_rate * 100)}%`}
            sub={`${stats.passed_submissions}/${stats.total_submissions} passed`}
          />
          <StatCard
            icon={<TrendingUp className="h-5 w-5 text-black" />}
            label="SUBMISSIONS"
            value={stats.total_submissions}
            sub="Sandboxed runs"
          />
        </div>

        {/* ── RECURRING MISTAKES ALERT (CRITICAL SECTION) ───────────────── */}
        {recurringMistakes.length > 0 ? (
          <section className="border-2 border-black bg-[#DE6557]/15 p-6 space-y-6 shadow-brutal-red">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b-2 border-black pb-4">
              <div className="flex items-center gap-3">
                <div className="bg-black text-[#DE6557] p-2 border-2 border-black shadow-[2px_2px_0px_#000]">
                  <ShieldAlert className="h-6 w-6 stroke-[2.5]" />
                </div>
                <div>
                  <h2 className="font-mono text-base font-black uppercase tracking-wider text-white">
                    RECURRING MISTAKE ALERT
                  </h2>
                  <p className="font-mono text-xs text-[#DE6557] font-bold uppercase tracking-wider">
                    FLAGGED: PATTERN OCCURS ACROSS 2+ DISTINCT CHALLENGES
                  </p>
                </div>
              </div>

              <span className="badge-black self-start sm:self-auto">
                {recurringMistakes.length} PATTERN(S) ACTIVE
              </span>
            </div>

            <div className="grid gap-5 md:grid-cols-2">
              {recurringMistakes.map((item) => {
                const meta = MISTAKE_DESCRIPTIONS[item.tag] ?? {
                  label: item.tag.replace(/_/g, " "),
                  explanation: "A repeating structural code pattern.",
                  remedy: "Review edge cases and loop bounds.",
                };

                return (
                  <div
                    key={item.tag}
                    className="flex flex-col justify-between border-2 border-black bg-white text-black p-5 shadow-[5px_5px_0px_#8B2019]"
                  >
                    <div className="space-y-2.5">
                      <div className="flex items-center justify-between">
                        <span className="badge-black">
                          #{item.tag}
                        </span>
                        <span className="font-mono text-[11px] font-bold text-slate-800">
                          SEEN IN {item.occurrences} CHALLENGES
                        </span>
                      </div>

                      <h3 className="text-xl font-black text-black tracking-tight uppercase">
                        {meta.label}
                      </h3>
                      <p className="text-xs font-sans text-slate-700 leading-relaxed">
                        {meta.explanation}
                      </p>
                    </div>

                    <div className="pt-4 border-t-2 border-black/10 mt-4 space-y-3">
                      <p className="font-mono text-[11px] font-bold text-[#8B2019]">
                        💡 REMEDY: {meta.remedy}
                      </p>

                      {item.suggested_challenge_id && (
                        <Link
                          href={`/challenge/${item.suggested_challenge_id}`}
                          id={`practice-next-${item.tag}`}
                          className="btn-terracotta w-full py-2.5 text-xs flex items-center justify-between px-3"
                        >
                          <div className="flex items-center gap-1.5 truncate">
                            <span>PRACTICE NEXT:</span>
                            <span className="font-black text-black truncate">
                              {item.suggested_challenge_title ??
                                item.suggested_challenge_id}
                            </span>
                          </div>
                          <ArrowRight className="h-3.5 w-3.5 flex-shrink-0" />
                        </Link>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        ) : (
          <section className="border-2 border-black bg-[#E8E6DB] text-black p-6 flex flex-col sm:flex-row items-center justify-between gap-4 shadow-brutal-sm">
            <div className="flex items-center gap-3">
              <div className="bg-black text-white p-2 border border-black shadow-[2px_2px_0px_#000]">
                <Check className="h-5 w-5 stroke-[3]" />
              </div>
              <div>
                <h3 className="font-mono text-sm font-black uppercase tracking-wider text-black">
                  CLEAN DIAGNOSTIC RECORD
                </h3>
                <p className="text-xs text-slate-700 font-sans">
                  No recurring mistake patterns detected! You haven&apos;t repeated
                  the same bug across multiple challenges.
                </p>
              </div>
            </div>
            <Link
              href="/"
              className="btn-dark px-4 py-2 text-xs font-mono"
            >
              SOLVE MORE →
            </Link>
          </section>
        )}

        {/* ── CONCEPT MASTERY (PROGRESS BARS ON CREAM CARD) ──────────── */}
        <section className="border-2 border-black bg-[#E8E6DB] text-black p-6 sm:p-8 space-y-6 shadow-brutal-red">
          <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 border-b-2 border-black pb-4">
            <div>
              <p className="font-mono text-xs font-bold uppercase tracking-widest text-[#141414]">
                SKILL MATRIX
              </p>
              <h2 className="text-2xl sm:text-3xl font-black uppercase tracking-tight text-black mt-0.5">
                Concept Mastery <span className="text-[#DE6557]">Estimates.</span>
              </h2>
            </div>

            {weakest_topics.length > 0 && (
              <div className="bg-black text-[#E5A83B] px-3 py-1 font-mono text-xs font-bold border border-black self-start sm:self-auto shadow-[2px_2px_0px_#000]">
                WEAKEST TOPIC: #{weakest_topics[0].toUpperCase()}
              </div>
            )}
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            {mastery && mastery.length > 0 ? (
              mastery.map((item) => (
                <ConceptProgressBar
                  key={item.id || item.concept_tag}
                  item={item}
                />
              ))
            ) : (
              <div className="col-span-2 py-8 text-center font-mono text-xs text-slate-600 font-bold">
                NO CONCEPT ATTEMPTS LOGGED YET. SUBMIT A CHALLENGE TO INITIALIZE.
              </div>
            )}
          </div>
        </section>

        {/* ── Recent Submissions Table (Brutalist White Card) ──────────── */}
        <section className="border-2 border-black bg-white text-black p-6 sm:p-8 space-y-5 shadow-brutal">
          <div className="flex items-center justify-between border-b-2 border-black pb-4">
            <h2 className="font-mono text-lg font-black uppercase tracking-wider text-black">
              RECENT SUBMISSIONS LOG
            </h2>
            <Link
              href="/"
              className="font-mono text-xs font-bold text-[#DE6557] hover:underline"
            >
              BROWSE ALL CHALLENGES →
            </Link>
          </div>

          {recent_submissions.length === 0 ? (
            <div className="py-8 text-center font-mono text-xs text-slate-500 font-bold">
              NO SUBMISSIONS RECORDED YET.
            </div>
          ) : (
            <div className="divide-y-2 border-t-2 border-b-2 border-black divide-black">
              {recent_submissions.map((sub: RecentSubmission) => (
                <div
                  key={sub.id}
                  className="flex items-center justify-between py-3.5 text-xs font-mono"
                >
                  <div className="flex items-center gap-3">
                    {OUTCOME_ICONS[sub.outcome] ?? (
                      <XCircle className="h-4 w-4 text-slate-500" />
                    )}
                    <Link
                      href={`/challenge/${sub.challenge_id}`}
                      className="font-bold text-black uppercase hover:text-[#DE6557] transition-colors"
                    >
                      {sub.challenge_id.replace(/-/g, " ")}
                    </Link>
                  </div>

                  <div className="flex items-center gap-4">
                    <span className="font-bold text-slate-700">
                      {sub.passed_tests}/{sub.total_tests} TESTS
                    </span>
                    {sub.xp_awarded > 0 && (
                      <span className="badge-black">
                        +{sub.xp_awarded} XP
                      </span>
                    )}
                    <Link
                      href={`/challenge/${sub.challenge_id}`}
                      className="btn-terracotta px-3 py-1 text-[11px]"
                    >
                      OPEN
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-[#141414]">
          <Loader2 className="h-8 w-8 animate-spin text-[#DE6557]" />
        </div>
      }
    >
      <DashboardContent />
    </Suspense>
  );
}
