"use client";
import {useEffect, useRef, useState} from "react";
import {api, Job, stagesFor, stageOf} from "@/lib/api";

// Live progress of the running job: stage stepper + log. Polls the API; calls onDone once when the job finishes.
export default function JobPanel({onDone, kind}: {onDone?: (job: Job) => void; kind?: string | string[]}) {
  const [job, setJob] = useState<Job | null>(null);
  const done = useRef<string | null>(null);
  const logRef = useRef<HTMLPreElement>(null);

  const kinds = kind ? [kind].flat() : null;
  const kindKey = kinds?.join(",");
  useEffect(() => {
    const ks = kindKey?.split(",");
    let alive = true;
    const tick = async () => {
      try {
        const j = await api.currentJob();
        if (!alive) return;
        setJob(j);
        if (j && j.status !== "running" && done.current !== j.id && (!ks || ks.includes(j.kind))) { done.current = j.id; onDone?.(j); }
      } catch {}
    };
    tick();
    const t = setInterval(tick, 1500);
    return () => { alive = false; clearInterval(t); };
  }, [onDone, kindKey]);

  useEffect(() => { logRef.current?.scrollTo({top: logRef.current.scrollHeight}); }, [job?.log]);

  if (!job || (kinds && !kinds.includes(job.kind) && job.status !== "running")) return null;
  const stages = stagesFor(job.kind), stage = stageOf(job.log, stages), mins = Math.floor(((job.ended || Date.now() / 1000) - job.started) / 60);
  const run = job.status === "running";
  return (
    <div className={`${run ? "card-glow" : "card"} p-5 sm:p-7`}>
      <div className="mb-6 flex items-center justify-between gap-4">
        <div className="flex min-w-0 items-center gap-4">
          <span className="relative grid h-12 w-12 shrink-0 place-items-center">
            {run && <span className="absolute inset-0 animate-ping rounded-full bg-case-500/30" />}
            <span className={`relative grid h-12 w-12 place-items-center rounded-full border text-xl ${run ? "border-case-400/50 bg-case-500/20" : job.status === "done" ? "border-emerald-400/40 bg-emerald-500/15" : "border-red-400/40 bg-red-500/15"}`}>
              {run ? "⚡" : job.status === "done" ? "✓" : "✕"}</span>
          </span>
          <div className="min-w-0">
            <p className="label">{run ? "Working on" : job.status === "done" ? "Finished" : "Failed"}</p>
            <p className="truncate font-display text-lg font-semibold sm:text-xl">{job.label}</p>
          </div>
        </div>
        <span className={`chip shrink-0 ${run ? "bg-amber-500/15 text-amber-300" : job.status === "done" ? "bg-emerald-500/15 text-emerald-300" : "bg-red-500/15 text-red-300"}`}>
          {run && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-amber-300" />}
          {job.status} · {mins} min
        </span>
      </div>
      {!["playlist", "script", "competitors"].includes(job.kind) && (
        <ol className={`mb-6 grid gap-2 ${stages.length > 6 ? "grid-cols-7" : "grid-cols-6"}`}>
          {stages.map((s, i) => {
            const ok = i < stage || job.status === "done", now = i === stage && run;
            return (
              <li key={s.key} className="text-center">
                <div className="relative mb-2 h-2 overflow-hidden rounded-full bg-white/[0.07]">
                  <div className={`absolute inset-0 rounded-full transition-all duration-700 ${ok ? "bg-gradient-to-r from-neon-cyan to-case-400 shadow-[0_0_12px] shadow-neon-cyan"
                    : now ? "animate-shimmer bg-[linear-gradient(90deg,transparent,#a78bfa,#f472b6,transparent)] bg-[length:200%_100%]" : "opacity-0"}`} />
                </div>
                <span className={`text-xs ${ok ? "text-zinc-200" : now ? "font-semibold text-white" : "text-zinc-500"}`}>{s.label}</span>
              </li>
            );
          })}
        </ol>
      )}
      {job.error && <p className="mb-3 rounded-2xl border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-300">{job.error}</p>}
      <pre ref={logRef} className="max-h-72 overflow-auto rounded-2xl border border-white/5 bg-black/50 p-4 font-mono text-xs leading-relaxed text-zinc-400">
        <span className="text-case-400">❯ </span>{job.log || "starting..."}{run && <span className="ml-0.5 inline-block h-3.5 w-2 animate-pulse bg-neon-cyan align-middle" />}</pre>
    </div>
  );
}
