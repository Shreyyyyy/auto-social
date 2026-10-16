"use client";
import {useCallback, useEffect, useState} from "react";
import ReactMarkdown from "react-markdown";
import JobPanel from "@/components/JobPanel";
import {Job} from "@/lib/api";

type Video = {id: string; title: string; channel: string; views: number; duration: number; why_competitor?: string;
  analysis?: {hook_words?: string; hook_type?: string; why_it_worked?: string[] | string; steal?: string[] | string; avoid?: string} | null};
type Data = {updated?: string; source?: string; min_views?: number; videos: Video[]; playbook?: string | null; api_key: boolean; youtube_connected?: boolean};

const fmt = (n: number) => n >= 1e7 ? `${(n / 1e7).toFixed(1)} Cr` : n >= 1e5 ? `${(n / 1e5).toFixed(1)} L` : n.toLocaleString("en-IN");
const list = (x?: string[] | string) => (Array.isArray(x) ? x : x ? [x] : []);

export default function Competitors() {
  const [d, setD] = useState<Data | null>(null);
  const [err, setErr] = useState("");
  const load = useCallback(() => fetch("/api/competitors", {cache: "no-store"}).then((r) => r.json()).then(setD).catch(() => {}), []);
  useEffect(() => { load(); }, [load]);
  const onDone = useCallback((_: Job) => load(), [load]);
  const refresh = async () => {
    setErr("");
    const r = await fetch("/api/competitors/refresh", {method: "POST"});
    if (!r.ok) setErr((await r.json()).detail || "could not start");
  };

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="label text-case-400">Competitors</p>
          <h1 className="mt-1 text-3xl font-bold tracking-tight">What's winning in your niche</h1>
          <p className="mt-2 max-w-2xl text-sm text-zinc-400">
            Most-viewed Hindi/Hinglish AI & tech explainer Shorts ({(d?.min_views ?? 1e6).toLocaleString("en-IN")}+ views), filtered to real competitors,
            watched by Gemini. The playbook below is used by every new script.</p>
          <p className="mt-1 text-xs text-zinc-500">{d?.updated ? `Updated ${d.updated} · ${d.source}` : "Not researched yet"}{d && !d.api_key && " · connect YouTube for official data"}</p>
        </div>
        <div className="flex gap-2">
          <button className="btn-ghost" onClick={async () => { setErr(""); await fetch("/api/youtube/connect", {method: "POST"}); setErr("A Google sign-in page opened in your browser - choose your account and click Allow (read-only)."); }}>
            {d?.youtube_connected ? "✅ YouTube connected (read-only)" : "▶ Connect YouTube (read-only)"}</button>
          <button className="btn-primary" onClick={refresh}>🔎 Refresh research</button>
        </div>
      </header>
      {err && <p className="rounded-xl bg-red-500/10 p-3 text-sm text-red-300">{err}</p>}
      <JobPanel onDone={onDone} kind="competitors" />

      {d?.playbook && <div className="card prose-pack p-5"><ReactMarkdown>{d.playbook}</ReactMarkdown></div>}

      <div className="grid gap-4 md:grid-cols-2">
        {(d?.videos || []).map((v, i) => (
          <div key={v.id} className="card flex gap-4 p-4">
            <a href={`https://www.youtube.com/shorts/${v.id}`} target="_blank" className="relative shrink-0">
              <img src={`https://i.ytimg.com/vi/${v.id}/hqdefault.jpg`} alt="" className="h-40 w-28 rounded-lg object-cover" />
              <span className="absolute left-1 top-1 rounded bg-black/70 px-1.5 font-mono text-[11px]">#{i + 1}</span>
            </a>
            <div className="min-w-0 flex-1 space-y-2">
              <p className="line-clamp-2 text-sm font-semibold leading-snug">{v.title}</p>
              <div className="flex flex-wrap gap-1.5">
                <span className="chip bg-case-500/15 text-case-400">👁 {fmt(v.views)}</span>
                <span className="chip bg-white/10 text-zinc-300">{v.channel}</span>
                <span className="chip bg-white/10 text-zinc-400">{v.duration}s</span>
              </div>
              {v.analysis ? <>
                {v.analysis.hook_words && <p className="text-xs text-zinc-300"><span className="text-zinc-500">Hook:</span> “{v.analysis.hook_words}”</p>}
                <ul className="list-disc space-y-0.5 pl-4 text-xs text-zinc-400">{list(v.analysis.why_it_worked).slice(0, 3).map((w, k) => <li key={k}>{w}</li>)}</ul>
                {list(v.analysis.steal)[0] && <p className="text-xs text-emerald-300/90">Steal: {list(v.analysis.steal)[0]}</p>}
              </> : <p className="text-xs text-zinc-500">{v.why_competitor}</p>}
            </div>
          </div>))}
      </div>
    </div>
  );
}
