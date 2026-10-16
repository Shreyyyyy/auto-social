"use client";
import {useEffect, useRef, useState} from "react";
import {api, Job, STAGES, stageOf} from "@/lib/api";

// Live progress of the running job: stage stepper + log. Polls the API; calls onDone once when the job finishes.
export default function JobPanel({onDone, kind}: {onDone?: (job: Job) => void; kind?: string}) {
  const [job, setJob] = useState<Job | null>(null);
  const done = useRef<string | null>(null);
  const logRef = useRef<HTMLPreElement>(null);

  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const j = await api.currentJob();
        if (!alive) return;
        setJob(j);
        if (j && j.status !== "running" && done.current !== j.id && (!kind || j.kind === kind)) { done.current = j.id; onDone?.(j); }
      } catch {}
    };
    tick();
    const t = setInterval(tick, 1500);
    return () => { alive = false; clearInterval(t); };
  }, [onDone, kind]);

  useEffect(() => { logRef.current?.scrollTo({top: logRef.current.scrollHeight}); }, [job?.log]);

  if (!job || (kind && job.kind !== kind && job.status !== "running")) return null;
  const stage = stageOf(job.log), mins = Math.floor(((job.ended || Date.now() / 1000) - job.started) / 60);
  return (
    <div className="card p-5">
      <div className="mb-4 flex items-center justify-between gap-4">
        <div className="min-w-0">
          <p className="label">{job.status === "running" ? "Working on" : job.status === "done" ? "Finished" : "Failed"}</p>
          <p className="truncate font-semibold">{job.label}</p>
        </div>
        <span className={`chip ${job.status === "running" ? "bg-amber-500/15 text-amber-300" : job.status === "done" ? "bg-emerald-500/15 text-emerald-300" : "bg-red-500/15 text-red-300"}`}>
          {job.status === "running" && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-amber-300" />}
          {job.status} · {mins} min
        </span>
      </div>
      {!["playlist", "script", "competitors"].includes(job.kind) && (
        <ol className="mb-4 grid grid-cols-6 gap-2">
          {STAGES.map((s, i) => (
            <li key={s.key} className="text-center">
              <div className={`mb-1 h-1.5 rounded-full ${i < stage || job.status === "done" ? "bg-emerald-400" : i === stage ? "animate-pulse bg-amber-400" : "bg-white/10"}`} />
              <span className={`text-[11px] ${i <= stage ? "text-zinc-200" : "text-zinc-500"}`}>{s.label}</span>
            </li>
          ))}
        </ol>
      )}
      {job.error && <p className="mb-3 rounded-xl bg-red-500/10 p-3 text-sm text-red-300">{job.error}</p>}
      <pre ref={logRef} className="max-h-64 overflow-auto rounded-xl bg-black/40 p-3 font-mono text-[11.5px] leading-relaxed text-zinc-400">{job.log || "starting..."}</pre>
    </div>
  );
}
