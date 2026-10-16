// app/page.tsx
// Challenge list page — MXESA [26] Neo-Brutalist Theme for Debug Dojo
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { listChallenges } from "@/lib/api";
import type { Challenge } from "@/types";
import {
  Code2,
  Search,
  Filter,
  Loader2,
  ChevronRight,
  Zap,
  Terminal,
  Shield,
  ArrowRight,
  Flame,
  Award,
} from "lucide-react";

const DIFFICULTIES = ["All", "Easy", "Medium", "Hard"];

export default function HomePage() {
  const [challenges, setChallenges] = useState<Challenge[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [diff, setDiff] = useState("All");

  useEffect(() => {
    setLoading(true);
    listChallenges({ difficulty: diff === "All" ? undefined : diff })
      .then((r) => {
        setChallenges(r.challenges);
        setTotal(r.total);
      })
      .finally(() => setLoading(false));
  }, [diff]);

  const filtered = search.trim()
    ? challenges.filter(
        (c) =>
          c.title.toLowerCase().includes(search.toLowerCase()) ||
          c.concept_tags.some((t) =>
            t.toLowerCase().includes(search.toLowerCase())
          )
      )
    : challenges;

  return (
    <div className="min-h-screen bg-[#141414] text-[#F0EFEA] font-sans selection:bg-[#DE6557] selection:text-black">
      {/* ── Top Navigation Bar ────────────────────────────────────────── */}
      <header className="sticky top-0 z-30 border-b-2 border-black bg-[#141414]/95 px-6 py-4 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between">
          {/* Logo in MXESA [26] style */}
          <Link href="/" className="flex items-center gap-2 group">
            <span className="text-2xl font-black tracking-tight text-white group-hover:text-[#DE6557] transition-colors font-mono">
              DEBUG DOJO <span className="text-[#DE6557]">[26]</span>
            </span>
          </Link>

          {/* Nav links */}
          <nav className="hidden md:flex items-center gap-8 text-xs font-mono tracking-wider text-slate-300">
            <Link
              href="/"
              className="text-[#DE6557] font-bold border-b-2 border-[#DE6557] pb-0.5"
            >
              CHALLENGES
            </Link>
            <Link
              href="/dashboard"
              className="hover:text-white transition-colors"
            >
              DASHBOARD
            </Link>
            <a
              href="#curriculum"
              className="hover:text-white transition-colors"
            >
              TAXONOMY
            </a>
          </nav>

          {/* Action button */}
          <div className="flex items-center gap-3">
            <Link
              href="/dashboard"
              className="btn-terracotta px-4 py-1.5 text-xs tracking-wider"
            >
              LEARNER DASHBOARD
            </Link>
          </div>
        </div>
      </header>

      {/* ── Hero Section (with MXESA industrial vibe & pixel accents) ─── */}
      <section className="relative overflow-hidden border-b-2 border-black bg-[#141414] px-6 py-20 lg:py-24">
        {/* Pixel / Geometric corner accents inspired by MXESA */}
        <div className="pointer-events-none absolute left-4 top-4 hidden sm:flex flex-col gap-1 opacity-70">
          <div className="flex gap-1">
            <div className="h-4 w-4 bg-[#DE6557]" />
            <div className="h-4 w-4 bg-[#DE6557]" />
            <div className="h-4 w-4 bg-[#DE6557]" />
          </div>
          <div className="flex gap-1 ml-4">
            <div className="h-4 w-4 bg-white" />
            <div className="h-4 w-4 bg-white" />
          </div>
          <div className="flex gap-1 ml-8">
            <div className="h-4 w-4 bg-[#E5A83B]" />
          </div>
        </div>

        <div className="pointer-events-none absolute right-4 top-4 hidden sm:flex flex-col items-end gap-1 opacity-70">
          <div className="flex gap-1">
            <div className="h-4 w-4 bg-white" />
            <div className="h-4 w-4 bg-white" />
            <div className="h-4 w-4 bg-white" />
          </div>
          <div className="flex gap-1 mr-4">
            <div className="h-4 w-4 bg-[#DE6557]" />
            <div className="h-4 w-4 bg-[#DE6557]" />
          </div>
          <div className="flex gap-1 mr-8">
            <div className="h-4 w-4 bg-[#DE6557]" />
          </div>
        </div>

        <div className="mx-auto max-w-4xl text-center space-y-6 relative z-10">
          {/* Overline with 3-Color Swatch pill */}
          <div className="inline-flex flex-col items-center gap-2">
            <div className="flex h-2 w-12 border border-black shadow-[2px_2px_0px_#000]">
              <div className="w-1/3 bg-[#DE6557]" />
              <div className="w-1/3 bg-[#E5A83B]" />
              <div className="w-1/3 bg-[#9BBBDD]" />
            </div>
            <p className="font-mono text-[11px] font-bold tracking-widest uppercase text-[#DE6557]">
              EST. 2026 • DI-01 DEBUG DOJO • MMIT HACKATHON
            </p>
          </div>

          {/* Giant Hero Headline */}
          <div className="space-y-1">
            <h1 className="text-4xl sm:text-6xl lg:text-7xl font-black uppercase tracking-tight text-white leading-tight">
              DEBUG DOJO 2026:
            </h1>
            <p className="text-3xl sm:text-5xl lg:text-6xl font-black tracking-tight text-[#9BBBDD] leading-tight">
              Forensics belongs to everyone.
            </p>
          </div>

          {/* Subtitle */}
          <p className="mx-auto max-w-2xl text-sm sm:text-base text-slate-300 leading-relaxed font-sans">
            Bring true algorithmic problem-solving to life. A forensic practice
            environment bridging runtime telemetry, AST mistake categorization,
            sandboxed execution, and progressive scaffolding without giving away
            answers.
          </p>

          {/* Hero Action Buttons */}
          <div className="flex flex-wrap items-center justify-center gap-4 pt-4">
            <a
              href="#curriculum"
              className="btn-terracotta px-6 py-3 text-xs tracking-wider"
            >
              EXPLORE DOJO CHALLENGES
            </a>
            <Link
              href="/dashboard"
              className="btn-dark px-6 py-3 text-xs tracking-wider border-white/60"
            >
              LEARNER INTELLIGENCE
            </Link>
          </div>

          {/* Bottom badge pill */}
          <div className="pt-4 flex flex-col items-center gap-2">
            <span className="font-mono text-[10px] tracking-widest text-slate-400 uppercase">
              HARDENED DOCKER SANDBOX · SECCOMP · RLIMITS
            </span>
            <div className="inline-flex items-center gap-2 bg-white text-black px-3 py-1 font-mono text-xs font-bold border-2 border-black shadow-[3px_3px_0px_#000]">
              <Terminal className="h-3.5 w-3.5" />
              <span>Python 3.11 · Nobody UID Execution</span>
            </div>
          </div>
        </div>
      </section>

      {/* ── Editorial Warm Cream Section: The Challenge Curriculum ─────── */}
      <section id="curriculum" className="bg-[#E8E6DB] text-[#141414] px-6 py-16 sm:py-20 border-b-2 border-black">
        <div className="mx-auto max-w-6xl space-y-10">
          {/* Section Header (MXESA Style) */}
          <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-6 border-b-2 border-black pb-8">
            <div>
              <p className="font-mono text-xs font-bold uppercase tracking-widest text-[#141414]">
                THE PROBLEM ARCHIVE
              </p>
              <h2 className="text-3xl sm:text-5xl font-black uppercase tracking-tight text-[#141414] mt-1">
                The Forensic <span className="text-[#DE6557]">Curriculum.</span>
              </h2>
            </div>
            <p className="text-xs sm:text-sm font-sans max-w-md text-slate-700 leading-relaxed">
              Curated challenges covering loops, boundary conditions, slicing,
              and inputs. Every submission undergoes isolated multi-test evaluation
              with AST pattern diagnosis.
            </p>
          </div>

          {/* Filters Bar in Neo-Brutalist styling */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
            {/* Search Input */}
            <div className="relative flex-1">
              <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-black" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search challenges by title, concept or keyword…"
                className="w-full border-2 border-black bg-white pl-10 pr-4 py-2.5 text-xs font-mono font-medium text-black placeholder:text-slate-500 shadow-[3px_3px_0px_#000] focus:outline-none focus:bg-[#FFFDF7]"
              />
            </div>

            {/* Difficulty Filter Buttons */}
            <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0">
              {DIFFICULTIES.map((d) => (
                <button
                  key={d}
                  onClick={() => setDiff(d)}
                  className={`border-2 border-black px-3.5 py-2 font-mono text-xs font-bold transition-all ${
                    diff === d
                      ? "bg-[#DE6557] text-black shadow-[3px_3px_0px_#000] translate-x-[-1px] translate-y-[-1px]"
                      : "bg-white text-black shadow-[2px_2px_0px_#000] hover:bg-[#F0EFEA]"
                  }`}
                >
                  {d.toUpperCase()}
                </button>
              ))}
            </div>
          </div>

          {/* Challenge Cards Grid (Formatted exactly like MXESA Committee Cards) */}
          {loading ? (
            <div className="flex flex-col items-center justify-center py-24 gap-3">
              <Loader2 className="h-8 w-8 animate-spin text-[#DE6557]" />
              <span className="font-mono text-xs font-bold text-black">
                FETCHING CHALLENGE SPECIFICATIONS…
              </span>
            </div>
          ) : filtered.length === 0 ? (
            <div className="border-2 border-black bg-white p-12 text-center space-y-3 shadow-[5px_5px_0px_#000]">
              <Code2 className="mx-auto h-8 w-8 text-[#DE6557]" />
              <h3 className="font-mono text-base font-bold text-black">
                NO MATCHING CHALLENGES FOUND
              </h3>
              <p className="text-xs text-slate-600 max-w-sm mx-auto">
                No challenges matched your query. Reset your search or difficulty
                filters.
              </p>
            </div>
          ) : (
            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {filtered.map((c) => (
                <div
                  key={c.id}
                  className="flex flex-col justify-between border-2 border-black bg-white p-6 shadow-brutal-red hover:shadow-[7px_7px_0px_#8B2019] transition-all hover:translate-x-[-1px] hover:translate-y-[-1px]"
                >
                  <div className="space-y-4">
                    {/* Top Black Badge */}
                    <div className="flex items-center justify-between">
                      <span className="badge-black">
                        {c.difficulty}
                      </span>
                      <span className="font-mono text-xs font-bold text-slate-800">
                        +{c.xp_reward} XP
                      </span>
                    </div>

                    {/* Challenge Title */}
                    <div>
                      <h3 className="text-2xl font-black tracking-tight text-black line-clamp-1">
                        {c.title}
                      </h3>
                      <p className="mt-2 text-xs font-sans text-slate-600 line-clamp-2 leading-relaxed">
                        {c.description.split("\n")[0]}
                      </p>
                    </div>

                    {/* Concept Tags in Monospace Pills */}
                    <div className="flex flex-wrap gap-1.5 pt-1">
                      {c.concept_tags.map((t) => (
                        <span
                          key={t}
                          className="border border-black bg-[#E8E6DB] px-2 py-0.5 font-mono text-[10px] font-bold text-black"
                        >
                          #{t}
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Card Action */}
                  <div className="pt-6 border-t-2 border-black/10 mt-6 flex items-center justify-between">
                    <span className="font-mono text-[11px] text-slate-500">
                      {c.time_limit_seconds}s limit
                    </span>
                    <Link
                      href={`/challenge/${c.id}`}
                      className="btn-terracotta px-4 py-2 text-xs tracking-wider flex items-center gap-1.5"
                    >
                      <span>SOLVE NOW</span>
                      <ArrowRight className="h-3 w-3" />
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* ── Footer ───────────────────────────────────────────────────── */}
      <footer className="border-t-2 border-black bg-[#141414] px-6 py-10 text-center font-mono text-xs text-slate-400">
        <div className="mx-auto max-w-5xl flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className="font-bold text-white">DEBUG DOJO [26]</span>
            <span>— DI-01 Forensic Practice Environment</span>
          </div>
          <div className="flex items-center gap-4 text-[11px]">
            <Link href="/" className="hover:text-white transition-colors">
              CHALLENGES
            </Link>
            <Link href="/dashboard" className="hover:text-white transition-colors">
              DASHBOARD
            </Link>
            <span className="text-[#DE6557]">MMIT 2026</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
