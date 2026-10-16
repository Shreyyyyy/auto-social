"use client";
import {useEffect, useState} from "react";
import ReactMarkdown from "react-markdown";
import {api, RunDetail} from "@/lib/api";

const STATUS: Record<string, string> = {
  "awaiting approval": "bg-amber-500/15 text-amber-300", approved: "bg-sky-500/15 text-sky-300",
  queued: "bg-emerald-500/15 text-emerald-300", failed: "bg-red-500/15 text-red-300",
};
export const StatusChip = ({s}: {s: string}) => <span className={`chip ${STATUS[s] || "bg-white/10 text-zinc-300"}`}>{s}</span>;

// One finished reel: player + cover, editable caption, approve/post, beginner review, script, SEO & marketing pack.
export default function ReelView({id}: {id: string}) {
  const [r, setR] = useState<RunDetail | null>(null);
  const [caption, setCaption] = useState("");
  const [msg, setMsg] = useState<{ok: boolean; text: string} | null>(null);
  const [busy, setBusy] = useState(false);
  const [tab, setTab] = useState<"review" | "script" | "marketing">("review");

  const load = () => api.run(id).then((x) => { setR(x); setCaption(x.caption); }).catch((e) => setMsg({ok: false, text: e.message}));
  useEffect(() => { load(); }, [id]);
  if (!r) return <div className="card h-96 animate-pulse" />;

  const act = async (fn: () => Promise<{message: string}>) => {
    setBusy(true); setMsg(null);
    try { setMsg({ok: true, text: (await fn()).message}); load(); } catch (e: any) { setMsg({ok: false, text: e.message}); }
    setBusy(false);
  };
  const sc = r.review?.scores || r.scores || {};
  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,360px)_1fr]">
      <div className="space-y-4">
        <video key={r.video} src={r.video} poster={r.cover || undefined} controls playsInline className="aspect-[9/16] w-full rounded-2xl border border-white/10 bg-black object-cover" />
        <div className="flex gap-2">
          <a href={r.video} download className="btn-ghost flex-1">⬇ Video</a>
          {r.cover && <a href={r.cover} download className="btn-ghost flex-1">⬇ Cover</a>}
        </div>
      </div>
      <div className="min-w-0 space-y-5">
        <div className="card p-5">
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <StatusChip s={r.status} />
            {r.voice && <span className="chip bg-white/10 text-zinc-300">🎙 {r.voice}</span>}
            {r.ep && <span className="chip bg-white/10 text-zinc-300">Case #{r.ep}</span>}
          </div>
          <h1 className="text-xl font-bold leading-snug">{r.title}</h1>
          {r.cover && <img src={r.cover} alt="cover" className="mt-4 h-40 w-auto rounded-xl border border-white/10" />}
        </div>

        <div className="card p-5">
          <p className="label mb-2">Caption</p>
          <textarea className="input min-h-40 font-sans text-sm" value={caption} onChange={(e) => setCaption(e.target.value)} />
          <div className="mt-3 flex flex-wrap gap-2">
            <button className="btn-ghost" disabled={busy} onClick={() => act(() => api.approve(id, caption))}>✅ Approve for schedule</button>
            <button className="btn-primary" disabled={busy || r.status === "queued"} onClick={() => act(() => api.post(id, caption))}>
              {busy ? "Posting…" : r.status === "queued" ? "Already sent to Buffer" : "📤 Post via Buffer"}</button>
          </div>
          {msg && <p className={`mt-3 whitespace-pre-wrap rounded-xl p-3 text-sm ${msg.ok ? "bg-emerald-500/10 text-emerald-300" : "bg-red-500/10 text-red-300"}`}>{msg.text}</p>}
        </div>

        <div className="card p-5">
          <div className="mb-4 flex gap-1 rounded-xl bg-black/30 p-1">
            {(["review", "script", "marketing"] as const).map((t) => (
              <button key={t} onClick={() => setTab(t)} className={`flex-1 rounded-lg px-3 py-1.5 text-sm font-medium capitalize ${tab === t ? "bg-white/10 text-white" : "text-zinc-400"}`}>
                {t === "marketing" ? "SEO & marketing" : t}</button>
            ))}
          </div>
          {tab === "review" && (r.review ? <div className="space-y-4">
            <div className="grid grid-cols-4 gap-2">
              {Object.entries(sc).map(([k, v]) => (
                <div key={k} className="rounded-xl bg-black/30 p-3 text-center">
                  <p className={`text-xl font-bold ${v >= 8 ? "text-emerald-300" : v >= 6.5 ? "text-amber-300" : "text-red-300"}`}>{v}</p>
                  <p className="text-[11px] capitalize text-zinc-400">{k.replace("_", " ")}</p>
                </div>))}
            </div>
            <div><p className="label mb-1">A beginner learned</p><p className="text-sm text-zinc-200">{r.review.learned}</p></div>
            {r.review.problems?.length ? <div><p className="label mb-1">Problems spotted</p>
              <ul className="space-y-1.5 text-sm text-zinc-300">{r.review.problems.slice(0, 6).map((p, i) =>
                <li key={i}><span className="font-mono text-zinc-500">{p.time}</span> {p.issue}</li>)}</ul></div> : null}
          </div> : <p className="text-sm text-zinc-400">No review for this reel.</p>)}
          {tab === "script" && r.script && <ol className="space-y-2">
            {r.script.lines.map((l, i) => <li key={i} className="flex gap-3 text-sm">
              <span className="w-6 shrink-0 font-mono text-zinc-500">{i + 1}</span>
              <span className="flex-1 text-zinc-200">{l.caption}</span>
              <span className="chip h-fit bg-white/5 text-zinc-400">{l.visual.type === "none" ? "footage" : l.visual.type}</span></li>)}
          </ol>}
          {tab === "marketing" && (r.marketing ? <div className="prose-pack"><ReactMarkdown>{r.marketing}</ReactMarkdown></div> : <p className="text-sm text-zinc-400">No marketing pack.</p>)}
        </div>
      </div>
    </div>
  );
}
