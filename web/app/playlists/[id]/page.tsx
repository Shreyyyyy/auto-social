"use client";
import Link from "next/link";
import {use, useCallback, useEffect, useState} from "react";
import JobPanel from "@/components/JobPanel";
import {StatusChip} from "@/components/ReelView";
import {api, Job, Playlist} from "@/lib/api";

const VIS: Record<string, string> = {none: "🎥", define: "📖", diagram: "🧩", flow: "➡️", chart: "📊", chat: "💬", recap: "📌", brand: "☕", counter: "🔢", compare: "⚖️", stamp: "✅", list: "📋", quote: "💡"};

export default function PlaylistPage({params}: {params: Promise<{id: string}>}) {
  const {id} = use(params);
  const [pl, setPl] = useState<Playlist | null>(null);
  const [open, setOpen] = useState<number | null>(null);
  const [err, setErr] = useState("");
  const load = useCallback(() => api.playlist(id).then(setPl).catch((e) => setErr(e.message)), [id]);
  useEffect(() => { load(); }, [load]);
  const onDone = useCallback((_: Job) => load(), [load]);
  const go = async (fn: () => Promise<Job>) => { setErr(""); try { await fn(); } catch (e: any) { setErr(e.message); } };
  if (!pl) return <div className="card h-96 animate-pulse" />;
  const next = pl.episodes.find((e) => !e.run);

  return (
    <div className="space-y-6">
      <header>
        <Link href="/playlists" className="text-sm text-zinc-400 hover:text-white">← Playlists</Link>
        <h1 className="mt-2 text-3xl font-bold tracking-tight">{pl.name}</h1>
        <p className="mt-2 text-sm text-zinc-400">{pl.made}/{pl.episodes.length} videos made · {next ? `next up: case #${next.n}` : "all done 🎉"}</p>
      </header>
      {err && <p className="rounded-xl bg-red-500/10 p-3 text-sm text-red-300">{err}</p>}
      <JobPanel onDone={onDone} />

      <ol className="space-y-3">
        {pl.episodes.map((e) => (
          <li key={e.n} className={`card overflow-hidden ${next?.n === e.n ? "border-case-400/40" : ""}`}>
            <div className="flex items-start gap-4 p-5">
              {e.cover ? <img src={e.cover} alt="" className="h-28 w-16 shrink-0 rounded-lg border border-white/10 object-cover" />
                : <div className="grid h-28 w-16 shrink-0 place-items-center rounded-lg bg-cork/30 font-mono text-lg font-bold text-cork">#{e.n}</div>}
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-xs text-case-400">CASE #{String(e.n).padStart(2, "0")}</span>
                  {e.era && <span className="text-xs text-zinc-500">{e.era}</span>}
                  <StatusChip s={e.run ? (e.status === "posted" ? "queued" : e.status === "generated" ? "awaiting approval" : e.status) : e.script.length ? "scripted" : "planned"} />
                </div>
                <p className="mt-1 font-semibold leading-snug">{e.title}</p>
                {e.hook && <p className="mt-1 text-sm text-zinc-400">“{e.hook}”</p>}
                <div className="mt-3 flex flex-wrap gap-2">
                  {e.run ? <Link href={`/reel/${e.run}`} className="btn-ghost">🎬 Open video</Link>
                    : <button className="btn-primary" onClick={() => go(() => api.runEpisode(id, e.n))}>▶ Run case #{e.n}</button>}
                  {e.run && <button className="btn-ghost" onClick={() => go(() => api.runEpisode(id, e.n))}>↻ Remake</button>}
                  {e.script.length > 0 && <button className="btn-ghost" onClick={() => setOpen(open === e.n ? null : e.n)}>{open === e.n ? "Hide script" : "Read script"}</button>}
                  {!e.run && <button className="btn-ghost" onClick={() => go(() => api.rewriteScript(id, e.n))}>✏️ {e.script.length ? "Rewrite" : "Write"} script</button>}
                </div>
              </div>
            </div>
            {open === e.n && (
              <ol className="space-y-2 border-t border-white/10 bg-black/20 p-5">
                {e.script.map((l, i) => (
                  <li key={i} className="flex gap-3 text-sm">
                    <span className="w-6 shrink-0 font-mono text-zinc-500">{i + 1}</span>
                    <span className="w-5 shrink-0">{VIS[l.visual] || "•"}</span>
                    <span className="flex-1 text-zinc-200">{l.say}</span>
                  </li>))}
              </ol>)}
          </li>
        ))}
      </ol>
    </div>
  );
}
