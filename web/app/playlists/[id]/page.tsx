"use client";
import Link from "next/link";
import {use, useCallback, useEffect, useState} from "react";
import JobPanel from "@/components/JobPanel";
import {StatusChip} from "@/components/ReelView";
import {api, Episode, Job, Playlist} from "@/lib/api";

const VIS: Record<string, string> = {none: "🎥", define: "📖", diagram: "🧩", flow: "➡️", chart: "📊", chat: "💬", recap: "📌", brand: "☕", counter: "🔢", compare: "⚖️", stamp: "✅", list: "📋", quote: "💡"};
const stateOf = (e: Episode) => e.run ? (e.status === "posted" ? "queued" : e.status === "generated" ? "awaiting approval" : e.status) : e.script.length ? "scripted" : "planned";
const DOT: Record<string, string> = {queued: "bg-emerald-400", "awaiting approval": "bg-amber-400", approved: "bg-sky-400", scripted: "bg-zinc-300", planned: "bg-zinc-600"};

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
  const jump = (n: number) => document.getElementById(`ep-${n}`)?.scrollIntoView({behavior: "smooth", block: "center"});

  return (
    <div className="space-y-6">
      <header>
        <Link href="/playlists" className="text-sm text-zinc-400 hover:text-white">← Playlists</Link>
        <h1 className="mt-2 text-3xl font-bold tracking-tight">{pl.name}</h1>
        <p className="mt-2 text-sm text-zinc-400">{pl.arcs.length} chapters · {pl.episodes.length} episodes · {pl.made} made · {next ? `next up: case #${next.n}` : "all done 🎉"}</p>
      </header>

      {/* map of the whole tree */}
      <div className="card overflow-x-auto p-5">
        <p className="label mb-4">Learning tree</p>
        <div className="flex min-w-max items-start gap-3">
          {pl.arcs.map((a, ai) => (
            <div key={ai} className="flex items-start gap-3">
              <div className="w-48">
                <div className="mb-3 rounded-xl border border-case-400/30 bg-case-500/10 px-3 py-2">
                  <p className="font-mono text-[10px] text-case-400">CHAPTER {ai + 1}</p>
                  <p className="line-clamp-2 text-xs font-semibold leading-snug">{a.title}</p>
                </div>
                <div className="ml-3 space-y-1.5 border-l border-white/15 pl-3">
                  {pl.episodes.filter((e) => e.arc === ai).map((e) => (
                    <button key={e.n} onClick={() => jump(e.n)} className="flex w-full items-center gap-2 rounded-lg px-1.5 py-1 text-left hover:bg-white/5">
                      <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${DOT[stateOf(e)]} ${next?.n === e.n ? "ring-2 ring-case-400 ring-offset-2 ring-offset-zinc-900" : ""}`} />
                      <span className="font-mono text-[11px] text-zinc-500">#{e.n}</span>
                      <span className="line-clamp-1 text-[11px] text-zinc-300">{e.title}</span>
                    </button>))}
                </div>
              </div>
              {ai < pl.arcs.length - 1 && <span className="mt-4 text-zinc-600">→</span>}
            </div>))}
        </div>
        <div className="mt-4 flex flex-wrap gap-3 text-[11px] text-zinc-500">
          {Object.entries(DOT).map(([k, c]) => <span key={k} className="flex items-center gap-1.5"><span className={`h-2 w-2 rounded-full ${c}`} />{k}</span>)}
        </div>
      </div>

      {err && <p className="rounded-xl bg-red-500/10 p-3 text-sm text-red-300">{err}</p>}
      <JobPanel onDone={onDone} />

      {/* chapters as branches, episodes hanging off them */}
      {pl.arcs.map((a, ai) => (
        <section key={ai}>
          <div className="mb-3 flex items-center gap-3">
            <span className="grid h-9 w-9 place-items-center rounded-full bg-case-500 font-mono text-sm font-bold shadow-lg shadow-case-500/30">{ai + 1}</span>
            <div><p className="font-semibold">{a.title}</p><p className="text-xs text-zinc-400">{a.summary}</p></div>
          </div>
          <ol className="relative ml-4 space-y-3 border-l-2 border-white/10 pl-6">
            {pl.episodes.filter((e) => e.arc === ai).map((e) => (
              <li key={e.n} id={`ep-${e.n}`} className={`card relative overflow-hidden ${next?.n === e.n ? "border-case-400/50" : ""}`}>
                <span className="absolute -left-[31px] top-8 h-0.5 w-6 bg-white/10" />
                <div className="flex items-start gap-4 p-5">
                  {e.cover ? <img src={e.cover} alt="" className="h-28 w-16 shrink-0 rounded-lg border border-white/10 object-cover" />
                    : <div className="grid h-28 w-16 shrink-0 place-items-center rounded-lg bg-cork/30 font-mono text-lg font-bold text-cork">#{e.n}</div>}
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-xs text-case-400">CASE #{String(e.n).padStart(2, "0")}</span>
                      {e.era && <span className="text-xs text-zinc-500">{e.era}</span>}
                      <StatusChip s={stateOf(e)} />
                    </div>
                    <p className="mt-1 font-semibold leading-snug">{e.title}</p>
                    {e.hook && <p className="mt-1 text-sm text-zinc-400">“{e.hook}”</p>}
                    {e.builds_on.length > 0 && <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs text-zinc-500">↳ builds on
                      {e.builds_on.map((b) => <button key={b} onClick={() => jump(b)} className="chip bg-white/5 text-zinc-300 hover:bg-white/10">#{b} {pl.episodes[b - 1]?.title.slice(0, 28)}…</button>)}</div>}
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
              </li>))}
          </ol>
        </section>))}
    </div>
  );
}
