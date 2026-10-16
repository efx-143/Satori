"use client";
// app/dashboard/page.tsx
// Learner dashboard: XP, streak, concept mastery chart,
// recurring mistake alerts, and recent submission history.

import { useEffect, useState } from "react";
import Link from "next/link";
import { getDashboard } from "@/lib/api";
import MasteryChart from "@/components/MasteryChart";
import type { DashboardData, RecentSubmission } from "@/types";
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
} from "lucide-react";

// ── Hardcoded demo learner — replace with auth context ─────────────────────
const DEMO_LEARNER_ID = "00000000-0000-0000-0000-000000000001";

const MISTAKE_LABELS: Record<string, string> = {
  off_by_one:            "Off-by-one error",
  unhandled_short_input: "Unhandled short/empty input",
  print_not_return:      "print() instead of return",
  boundary_comparison:   "Incorrect boundary comparison",
  mutates_input:         "Mutates the input argument",
};

const OUTCOME_ICON: Record<string, React.ReactNode> = {
  passed:  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />,
  failed:  <XCircle      className="h-3.5 w-3.5 text-rose-400" />,
  error:   <Zap          className="h-3.5 w-3.5 text-amber-400" />,
  timeout: <Clock        className="h-3.5 w-3.5 text-orange-400" />,
};

// ── Stat card ──────────────────────────────────────────────────────────────

function StatCard({
  icon,
  label,
  value,
  sub,
  accent,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  sub?: string;
  accent?: string;
}) {
  return (
    <div className="rounded-2xl border border-white/5 bg-white/3 p-5 space-y-3 backdrop-blur hover:border-violet-500/20 transition-all">
      <div className="flex items-center justify-between">
        <span className="text-sm text-slate-500">{label}</span>
        <span className={`${accent ?? "text-violet-400"}`}>{icon}</span>
      </div>
      <p className={`text-3xl font-bold ${accent ?? "text-slate-100"}`}>
        {value}
      </p>
      {sub && <p className="text-xs text-slate-600">{sub}</p>}
    </div>
  );
}

// ── Recent submission row ──────────────────────────────────────────────────

function SubmissionRow({ sub }: { sub: RecentSubmission }) {
  const date = new Date(sub.submitted_at);
  const timeAgo = formatTimeAgo(date);
  return (
    <Link
      href={`/challenge/${sub.challenge_id}`}
      className="flex items-center gap-3 rounded-lg border border-white/5 bg-white/2 px-4 py-3 text-sm hover:bg-white/5 hover:border-violet-500/20 transition-all group"
    >
      <span className="flex-shrink-0">{OUTCOME_ICON[sub.outcome]}</span>
      <span className="flex-1 font-medium text-slate-300 group-hover:text-slate-100 transition-colors truncate">
        {sub.challenge_id.replace(/-/g, " ")}
      </span>
      <span className="text-xs text-slate-600">{timeAgo}</span>
      {sub.xp_awarded > 0 && (
        <span className="rounded-full border border-violet-500/30 bg-violet-500/10 px-2 py-0.5 text-xs text-violet-400">
          +{sub.xp_awarded} XP
        </span>
      )}
      <ChevronRight className="h-4 w-4 text-slate-700 group-hover:text-slate-500 transition-colors" />
    </Link>
  );
}

function formatTimeAgo(date: Date): string {
  const diff = Date.now() - date.getTime();
  const mins  = Math.floor(diff / 60000);
  const hours = Math.floor(mins / 60);
  const days  = Math.floor(hours / 24);
  if (days > 0)  return `${days}d ago`;
  if (hours > 0) return `${hours}h ago`;
  if (mins > 0)  return `${mins}m ago`;
  return "just now";
}

// ── XP progress bar towards next level ────────────────────────────────────

const LEVELS = [0, 100, 250, 500, 1000, 2000, 5000];

function XPBar({ xp }: { xp: number }) {
  const levelIdx = LEVELS.findLastIndex((l) => xp >= l);
  const level    = levelIdx + 1;
  const current  = LEVELS[levelIdx] ?? 0;
  const next     = LEVELS[levelIdx + 1] ?? LEVELS[LEVELS.length - 1];
  const pct      = next === current ? 100 : Math.round(((xp - current) / (next - current)) * 100);

  return (
    <div className="space-y-1.5">
      <div className="flex justify-between text-xs text-slate-500">
        <span>Level {level}</span>
        <span>{xp} / {next} XP</span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-slate-700">
        <div
          className="h-full rounded-full bg-gradient-to-r from-violet-500 to-pink-500 transition-all duration-700"
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="text-xs text-slate-600 text-right">
        {next - xp} XP to Level {level + 1}
      </p>
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const [data, setData]     = useState<DashboardData | null>(null);
  const [error, setError]   = useState<string | null>(null);

  useEffect(() => {
    getDashboard(DEMO_LEARNER_ID)
      .then(setData)
      .catch((e) => setError(e.message));
  }, []);

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#0a0a0f]">
        <div className="text-center space-y-3">
          <p className="text-rose-400">{error}</p>
          <Link href="/" className="text-sm text-violet-400 hover:underline">
            ← Back
          </Link>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#0a0a0f]">
        <Loader2 className="h-8 w-8 animate-spin text-violet-500" />
      </div>
    );
  }

  const { learner, stats, mastery, weakest_topics, recent_submissions } = data;

  // Collect recurring mistakes from recent submissions
  // (In real app this would come from a dedicated endpoint;
  //  here we derive it from recent_submissions for demo.)
  // We show a static note — the real recurring data is in SubmissionFeedback.

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-slate-200">
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-10 border-b border-white/5 bg-slate-900/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center gap-4 px-6 py-4">
          <LayoutDashboard className="h-5 w-5 text-violet-400" />
          <span className="font-bold text-lg bg-gradient-to-r from-violet-400 to-pink-400 bg-clip-text text-transparent">
            Debug Dojo
          </span>
          <nav className="ml-8 flex items-center gap-6 text-sm text-slate-500">
            <Link href="/"         className="hover:text-slate-200 transition-colors">Challenges</Link>
            <Link href="/dashboard" className="text-slate-200 font-medium">Dashboard</Link>
          </nav>
          <div className="ml-auto flex items-center gap-3">
            <div className="flex items-center gap-1.5 rounded-full border border-amber-500/30 bg-amber-500/10 px-3 py-1 text-xs text-amber-400">
              <Flame className="h-3 w-3" />
              {stats.streak_days} day streak
            </div>
            <div className="h-8 w-8 rounded-full bg-gradient-to-br from-violet-500 to-pink-500 flex items-center justify-center text-xs font-bold">
              {learner.display_name.charAt(0).toUpperCase()}
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl space-y-8 px-6 py-8">
        {/* ── Welcome row ─────────────────────────────────────────────── */}
        <div className="flex items-end justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-100">
              Welcome back, {learner.display_name} 👋
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              Keep going — you&apos;re on a {stats.streak_days}-day streak!
            </p>
          </div>
          <Link
            href="/"
            className="flex items-center gap-2 rounded-lg bg-violet-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-violet-500 transition-all shadow-lg shadow-violet-500/20"
          >
            <BookOpen className="h-4 w-4" />
            Practice Now
          </Link>
        </div>

        {/* ── Stat cards ──────────────────────────────────────────────── */}
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <StatCard
            icon={<Trophy className="h-5 w-5" />}
            label="Total XP"
            value={stats.xp_points.toLocaleString()}
            accent="text-violet-400"
          />
          <StatCard
            icon={<Flame className="h-5 w-5" />}
            label="Streak"
            value={`${stats.streak_days}d`}
            sub="Keep it going!"
            accent="text-amber-400"
          />
          <StatCard
            icon={<Target className="h-5 w-5" />}
            label="Pass Rate"
            value={`${Math.round(stats.pass_rate * 100)}%`}
            sub={`${stats.passed_submissions}/${stats.total_submissions} solved`}
            accent="text-emerald-400"
          />
          <StatCard
            icon={<TrendingUp className="h-5 w-5" />}
            label="Challenges"
            value={stats.total_submissions}
            sub="total submissions"
            accent="text-blue-400"
          />
        </div>

        {/* ── XP level bar ────────────────────────────────────────────── */}
        <div className="rounded-2xl border border-white/5 bg-white/3 p-5">
          <p className="mb-3 text-sm font-semibold text-slate-400">
            XP Progress
          </p>
          <XPBar xp={stats.xp_points} />
        </div>

        {/* ── Two column: mastery + recent ────────────────────────────── */}
        <div className="grid gap-6 lg:grid-cols-2">
          {/* Concept Mastery */}
          <div className="rounded-2xl border border-white/5 bg-white/3 p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="font-semibold text-slate-200">Concept Mastery</h2>
              {weakest_topics.length > 0 && (
                <span className="text-xs text-slate-500">
                  Weak: {weakest_topics.slice(0, 2).join(", ")}
                </span>
              )}
            </div>
            <MasteryChart mastery={mastery} weakestTopics={weakest_topics} />
          </div>

          {/* Recent submissions */}
          <div className="rounded-2xl border border-white/5 bg-white/3 p-6 space-y-4">
            <h2 className="font-semibold text-slate-200">Recent Submissions</h2>
            {recent_submissions.length === 0 ? (
              <div className="flex h-48 items-center justify-center rounded-xl border border-dashed border-slate-700 text-sm text-slate-500">
                No submissions yet. Start coding!
              </div>
            ) : (
              <div className="space-y-2">
                {recent_submissions.map((s) => (
                  <SubmissionRow key={s.id} sub={s} />
                ))}
              </div>
            )}
            <Link
              href="/"
              className="block text-center text-xs text-violet-400 hover:text-violet-300 transition-colors"
            >
              View all challenges →
            </Link>
          </div>
        </div>

        {/* ── Weak areas callout ───────────────────────────────────────── */}
        {weakest_topics.length > 0 && (
          <div className="rounded-2xl border border-amber-500/20 bg-amber-500/5 p-6 space-y-4">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-amber-400" />
              <h2 className="font-semibold text-amber-300">
                Areas to Strengthen
              </h2>
            </div>
            <p className="text-sm text-slate-400">
              Your mastery scores are lowest in these concepts. Focus here to
              level up faster.
            </p>
            <div className="flex flex-wrap gap-3">
              {weakest_topics.map((topic) => (
                <Link
                  key={topic}
                  href={`/?concept=${topic}`}
                  className="flex items-center gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-2.5 text-sm text-amber-300 hover:bg-amber-500/20 transition-all"
                >
                  <Target className="h-4 w-4" />
                  Practice{" "}
                  <span className="font-semibold capitalize">{topic}</span>
                  <ChevronRight className="h-3.5 w-3.5 ml-1" />
                </Link>
              ))}
            </div>
          </div>
        )}

        {/* ── Mistake taxonomy awareness ───────────────────────────────── */}
        <div className="rounded-2xl border border-white/5 bg-white/3 p-6 space-y-4">
          <h2 className="font-semibold text-slate-200">
            Common Mistake Patterns
          </h2>
          <p className="text-sm text-slate-500">
            Mistakes detected by our AST analyser across your submissions. If
            a pattern is marked &quot;recurring&quot;, you&apos;ll see a{" "}
            <span className="text-rose-400">Practice Next</span> button on
            the challenge page after submitting.
          </p>
          <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
            {Object.entries(MISTAKE_LABELS).map(([tag, label]) => (
              <div
                key={tag}
                className="flex items-center gap-2 rounded-lg border border-white/5 bg-white/2 px-3 py-2"
              >
                <span className="h-2 w-2 rounded-full bg-violet-500/60 flex-shrink-0" />
                <span className="text-xs text-slate-400">{label}</span>
              </div>
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}
