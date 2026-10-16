"use client";
// components/MasteryChart.tsx
// Radar chart + progress bars for concept mastery.
// Uses recharts for the radar view and custom bars for the list view.

import { useState } from "react";
import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import type { MasteryRecord } from "@/types";

interface Props {
  mastery: MasteryRecord[];
  weakestTopics: string[];
}

// Max items shown in radar (too many makes it unreadable)
const MAX_RADAR_ITEMS = 8;

const LEVEL_LABELS: [number, string, string][] = [
  [80, "Expert",     "text-emerald-400"],
  [60, "Proficient", "text-violet-400"],
  [40, "Developing", "text-amber-400"],
  [0,  "Novice",     "text-rose-400"],
];

function getLevel(score: number): { label: string; color: string } {
  for (const [threshold, label, color] of LEVEL_LABELS) {
    if (score >= threshold) return { label, color };
  }
  return { label: "Novice", color: "text-rose-400" };
}

// Custom tooltip for the radar
function RadarTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  const lvl = getLevel(d.mastery_score);
  return (
    <div className="rounded-lg border border-violet-500/30 bg-slate-900/95 px-3 py-2 text-xs shadow-xl">
      <p className="font-semibold text-slate-200 capitalize">{d.concept_tag}</p>
      <p className={`${lvl.color} font-medium`}>
        {d.mastery_score.toFixed(1)} / 100 · {lvl.label}
      </p>
    </div>
  );
}

export default function MasteryChart({ mastery, weakestTopics }: Props) {
  const [view, setView] = useState<"radar" | "bars">("radar");

  if (mastery.length === 0) {
    return (
      <div className="flex h-48 items-center justify-center rounded-xl border border-dashed border-slate-700 text-sm text-slate-500">
        No mastery data yet. Submit some challenges to see your progress!
      </div>
    );
  }

  const radarData = mastery
    .slice(0, MAX_RADAR_ITEMS)
    .map((m) => ({
      concept_tag:   m.concept_tag,
      mastery_score: Math.round(m.mastery_score),
    }));

  return (
    <div className="space-y-4">
      {/* View toggle */}
      <div className="flex gap-1 rounded-lg border border-slate-700 bg-slate-800/60 p-1 w-fit">
        {(["radar", "bars"] as const).map((v) => (
          <button
            key={v}
            onClick={() => setView(v)}
            className={`rounded px-4 py-1.5 text-xs font-medium capitalize transition-all ${
              view === v
                ? "bg-violet-600 text-white shadow"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            {v === "radar" ? "🕸 Radar" : "📊 Bars"}
          </button>
        ))}
      </div>

      {view === "radar" ? (
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart data={radarData} margin={{ top: 8, right: 24, bottom: 8, left: 24 }}>
              <PolarGrid stroke="#334155" />
              <PolarAngleAxis
                dataKey="concept_tag"
                tick={{ fill: "#94a3b8", fontSize: 11 }}
              />
              <Radar
                name="Mastery"
                dataKey="mastery_score"
                stroke="#8b5cf6"
                fill="#8b5cf6"
                fillOpacity={0.25}
                strokeWidth={2}
              />
              <Tooltip content={<RadarTooltip />} />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className="space-y-3">
          {mastery.map((m) => {
            const lvl = getLevel(m.mastery_score);
            const isWeak = weakestTopics.includes(m.concept_tag);
            return (
              <div key={m.concept_tag} className="space-y-1.5">
                <div className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <span className="capitalize text-slate-300 font-medium">
                      {m.concept_tag}
                    </span>
                    {isWeak && (
                      <span className="rounded border border-rose-500/30 bg-rose-500/10 px-1.5 py-0.5 text-[10px] text-rose-400">
                        Needs work
                      </span>
                    )}
                  </div>
                  <span className={`font-mono ${lvl.color}`}>
                    {m.mastery_score.toFixed(1)} · {lvl.label}
                  </span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-slate-700">
                  <div
                    className="h-full rounded-full transition-all duration-700"
                    style={{
                      width: `${Math.min(100, m.mastery_score)}%`,
                      background: `linear-gradient(90deg, #8b5cf6, ${
                        m.mastery_score >= 80
                          ? "#10b981"
                          : m.mastery_score >= 40
                          ? "#a78bfa"
                          : "#f43f5e"
                      })`,
                    }}
                  />
                </div>
                <div className="flex justify-between text-[10px] text-slate-600">
                  <span>{m.correct_attempts}/{m.attempts} solved</span>
                  <span>
                    {m.attempts > 0
                      ? `${Math.round((m.correct_attempts / m.attempts) * 100)}% accuracy`
                      : "No attempts"}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
