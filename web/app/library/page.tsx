"use client";
import Link from "next/link";
import {useEffect, useState} from "react";
import {StatusChip} from "@/components/ReelView";
import {api, RunSummary} from "@/lib/api";

export default function Library() {
  const [runs, setRuns] = useState<RunSummary[] | null>(null);
  const [filter, setFilter] = useState("all");
  useEffect(() => { api.runs().then(setRuns).catch(() => setRuns([])); }, []);
  const shown = (runs || []).filter((r) => filter === "all" || r.status === filter);
  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="label text-case-400">Library</p>
          <h1 className="mt-1 text-3xl font-bold tracking-tight">Every reel you've made</h1>
        </div>
        <div className="flex gap-1 rounded-xl bg-white/5 p-1">
          {["all", "awaiting approval", "approved", "queued"].map((f) => (
            <button key={f} onClick={() => setFilter(f)} className={`rounded-lg px-3 py-1.5 text-xs font-medium capitalize ${filter === f ? "bg-white/10 text-white" : "text-zinc-400"}`}>{f}</button>))}
        </div>
      </header>
      {!runs ? <div className="card h-64 animate-pulse" /> : (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          {shown.map((r) => (
            <div key={r.id} className="card group relative overflow-hidden transition hover:border-case-400/40">
              <button
                type="button"
                title="Delete reel"
                onClick={async (e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  if (!window.confirm(`Delete reel "${r.title || r.id}"?`)) return;
                  try {
                    await api.deleteRun(r.id);
                    setRuns((prev) => prev ? prev.filter((x) => x.id !== r.id) : []);
                  } catch (err: any) {
                    alert(err.message);
                  }
                }}
                className="absolute right-2 top-2 z-10 rounded-lg bg-black/60 p-2 text-zinc-400 opacity-0 shadow-lg backdrop-blur transition hover:bg-red-500/20 hover:text-red-300 group-hover:opacity-100"
              >
                🗑️
              </button>
              <Link href={`/reel/${r.id}`} className="block">
                {r.cover ? <img src={r.cover} alt="" className="aspect-[9/16] w-full object-cover transition group-hover:scale-[1.02]" />
                  : <div className="grid aspect-[9/16] place-items-center bg-zinc-800 text-3xl">🎬</div>}
                <div className="space-y-2 p-3">
                  <p className="line-clamp-2 text-sm font-semibold leading-snug">{r.title}</p>
                  <div className="flex flex-wrap items-center gap-1.5"><StatusChip s={r.status} />
                    {r.verdict && <span className={`chip ${r.verdict === "post" ? "bg-emerald-500/15 text-emerald-300" : "bg-white/10 text-zinc-400"}`}>review: {r.verdict}</span>}</div>
                </div>
              </Link>
            </div>))}
        </div>)}
    </div>
  );
}
