// app/page.tsx
// Challenge list page — the home / lobby of Debug Dojo.
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { listChallenges } from "@/lib/api";
import type { Challenge } from "@/types";
import { Code2, Search, Filter, Loader2, ChevronRight, Zap } from "lucide-react";

const DIFF_STYLES: Record<string, string> = {
  Easy:   "border-emerald-500/40 bg-emerald-500/10 text-emerald-400",
  Medium: "border-amber-500/40  bg-amber-500/10  text-amber-400",
  Hard:   "border-rose-500/40   bg-rose-500/10   text-rose-400",
};

const DIFFICULTIES = ["All", "Easy", "Medium", "Hard"];

export default function HomePage() {
  const [challenges, setChallenges] = useState<Challenge[]>([]);
  const [total, setTotal]           = useState(0);
  const [loading, setLoading]       = useState(true);
  const [search, setSearch]         = useState("");
  const [diff, setDiff]             = useState("All");

  useEffect(() => {
    setLoading(true);
    listChallenges({ difficulty: diff === "All" ? undefined : diff })
      .then((r) => { setChallenges(r.challenges); setTotal(r.total); })
      .finally(() => setLoading(false));
  }, [diff]);

  const filtered = search.trim()
    ? challenges.filter((c) =>
        c.title.toLowerCase().includes(search.toLowerCase()) ||
        c.concept_tags.some((t) => t.toLowerCase().includes(search.toLowerCase()))
      )
    : challenges;

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-slate-200">
      {/* Header */}
      <header className="border-b border-white/5 bg-slate-900/80 backdrop-blur sticky top-0 z-10">
        <div className="mx-auto flex max-w-5xl items-center gap-4 px-6 py-4">
          <Code2 className="h-6 w-6 text-violet-400" />
          <span className="text-lg font-bold bg-gradient-to-r from-violet-400 to-pink-400 bg-clip-text text-transparent">
            Debug Dojo
          </span>
          <nav className="ml-8 flex gap-6 text-sm text-slate-500">
            <Link href="/"          className="text-slate-200 font-medium">Challenges</Link>
            <Link href="/dashboard" className="hover:text-slate-200 transition-colors">Dashboard</Link>
          </nav>
          <div className="ml-auto flex items-center gap-2 text-xs text-slate-500">
            <Zap className="h-3.5 w-3.5 text-violet-400" />
            {total} challenges
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="relative border-b border-white/5 bg-gradient-to-br from-violet-950/40 via-slate-900/20 to-transparent">
        <div className="mx-auto max-w-5xl px-6 py-16 text-center">
          <h1 className="text-4xl font-extrabold tracking-tight text-white sm:text-5xl">
            Master Python,{" "}
            <span className="bg-gradient-to-r from-violet-400 to-pink-400 bg-clip-text text-transparent">
              One Bug at a Time
            </span>
          </h1>
          <p className="mx-auto mt-4 max-w-xl text-slate-400">
            Solve real coding challenges, get AI-powered explanations, and track
            your mastery across every concept.
          </p>
        </div>
      </section>

      {/* Filters */}
      <div className="mx-auto max-w-5xl px-6 py-6 flex flex-wrap items-center gap-4">
        <div className="relative flex-1 min-w-48">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by title or concept…"
            className="w-full rounded-lg border border-slate-700 bg-slate-800/60 pl-9 pr-4 py-2.5 text-sm text-slate-200 placeholder:text-slate-600 focus:border-violet-500 focus:outline-none"
          />
        </div>
        <div className="flex items-center gap-1 rounded-lg border border-slate-700 bg-slate-800/60 p-1">
          <Filter className="mx-2 h-3.5 w-3.5 text-slate-500" />
          {DIFFICULTIES.map((d) => (
            <button
              key={d}
              onClick={() => setDiff(d)}
              className={`rounded px-3 py-1.5 text-xs font-medium transition-all ${
                diff === d
                  ? "bg-violet-600 text-white"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              {d}
            </button>
          ))}
        </div>
      </div>

      {/* Challenge grid */}
      <main className="mx-auto max-w-5xl px-6 pb-16">
        {loading ? (
          <div className="flex justify-center py-20">
            <Loader2 className="h-8 w-8 animate-spin text-violet-500" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center gap-3 py-20 text-slate-500">
            <Code2 className="h-10 w-10 opacity-30" />
            <p>No challenges match your filters.</p>
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2">
            {filtered.map((c) => (
              <Link
                key={c.id}
                href={`/challenge/${c.id}`}
                className="group rounded-2xl border border-white/5 bg-white/3 p-5 hover:border-violet-500/30 hover:bg-white/5 transition-all duration-200 hover:shadow-[0_0_20px_rgba(139,92,246,0.08)]"
              >
                <div className="flex items-start justify-between gap-3">
                  <h2 className="font-semibold text-slate-200 group-hover:text-white transition-colors line-clamp-2">
                    {c.title}
                  </h2>
                  <span className={`flex-shrink-0 rounded border px-2 py-0.5 text-xs ${DIFF_STYLES[c.difficulty]}`}>
                    {c.difficulty}
                  </span>
                </div>
                <p className="mt-2 text-sm text-slate-500 line-clamp-2">
                  {c.description.split("\n")[0]}
                </p>
                <div className="mt-4 flex flex-wrap gap-1.5">
                  {c.concept_tags.map((t) => (
                    <span
                      key={t}
                      className="rounded-full border border-violet-500/20 bg-violet-500/5 px-2.5 py-0.5 text-xs text-violet-400"
                    >
                      {t}
                    </span>
                  ))}
                </div>
                <div className="mt-4 flex items-center justify-between">
                  <span className="text-xs text-slate-600">+{c.xp_reward} XP</span>
                  <ChevronRight className="h-4 w-4 text-slate-600 group-hover:text-violet-400 group-hover:translate-x-0.5 transition-all" />
                </div>
              </Link>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
