"use client";
import {useEffect, useState} from "react";
import ReactMarkdown from "react-markdown";
import ChannelPicker, {NET, useChannels} from "@/components/ChannelPicker";
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
  const [tab, setTab] = useState<"review" | "script" | "marketing" | "usage">("review");
  const {channels, picked, toggle} = useChannels();

  const load = () => api.run(id).then((x) => { setR(x); setCaption(x.caption); }).catch((e) => setMsg({ok: false, text: e.message}));
  useEffect(() => { load(); }, [id]);
  if (!r) return <div className="card h-96 animate-pulse" />;

  const act = async (fn: () => Promise<{message: string}>) => {
    setBusy(true); setMsg(null);
    try { setMsg({ok: true, text: (await fn()).message}); load(); } catch (e: any) { setMsg({ok: false, text: e.message}); }
    setBusy(false);
  };
  const handleDelete = async () => {
    if (!window.confirm("Are you sure you want to delete this reel?")) return;
    setBusy(true); setMsg(null);
    try {
      await api.deleteRun(id);
      window.location.href = "/library";
    } catch (e: any) {
      setMsg({ok: false, text: e.message});
      setBusy(false);
    }
  };
  const sc = r.review?.scores || r.scores || {};
  const left = (channels || []).filter((c) => !r.sent?.[c.service]);
  const allSent = channels !== null && channels.length > 0 && left.length === 0;
  const targets = left.filter((c) => picked.includes(c.service)).map((c) => c.service);
  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,360px)_1fr]">
      <div className="space-y-4">
        <div className="relative rounded-[1.75rem] bg-gradient-to-b from-neon-cyan/40 via-case-500/30 to-neon-pink/40 p-[2px] shadow-[0_30px_80px_-20px_rgba(124,58,237,.6)]">
          <video key={r.video} src={r.video} poster={r.cover || undefined} controls playsInline className="aspect-[9/16] w-full rounded-[1.65rem] bg-black object-cover" />
        </div>
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
          <h1 className="font-display text-2xl font-bold leading-snug">{r.title}</h1>
          {r.cover && <img src={r.cover} alt="cover" className="mt-4 h-40 w-auto rounded-xl border border-white/10" />}
          {r.contact && <div className="mt-5"><p className="label mb-2">Contact sheet · one frame per line</p>
            <a href={r.contact} target="_blank"><img src={r.contact} alt="contact sheet" className="w-full rounded-xl border border-white/10 transition hover:opacity-90" /></a></div>}
        </div>

        <div className="card p-5">
          <p className="label mb-2">Caption</p>
          <textarea className="input min-h-40 font-sans text-sm" value={caption} onChange={(e) => setCaption(e.target.value)} />
          <div className="mt-4"><ChannelPicker channels={channels} picked={picked} toggle={toggle} sent={r.sent} failed={r.send_errors} /></div>
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <button className="btn-ghost" disabled={busy} onClick={() => act(() => api.approve(id, caption))}>✅ Approve for schedule</button>
            <button className="btn-primary" disabled={busy || allSent || !targets.length} onClick={() => act(() => api.post(id, caption, targets))}>
              {busy ? "Posting…" : allSent ? "Sent everywhere" : !targets.length ? "Pick a channel"
                : `📤 Post to ${targets.map((s) => NET[s]?.name || s).join(" + ")}`}</button>
            <button className="btn-danger ml-auto" disabled={busy} onClick={handleDelete}>
              🗑️ Delete reel
            </button>
          </div>
          {msg && <p className={`mt-3 whitespace-pre-wrap rounded-xl p-3 text-sm ${msg.ok ? "bg-emerald-500/10 text-emerald-300" : "bg-red-500/10 text-red-300"}`}>{msg.text}</p>}
        </div>

        <div className="card p-5">
          <div className="mb-4 flex gap-1 rounded-xl bg-black/30 p-1">
            {(["review", "script", "marketing", "usage"] as const).map((t) => (
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
          {tab === "usage" && (r.usage ? <div className="space-y-4">
            <div className="grid grid-cols-3 gap-2">
              <div className="rounded-xl bg-black/30 p-3 text-center"><p className="text-xl font-bold text-emerald-300">${r.usage.gemini_usd.toFixed(3)}</p>
                <p className="text-[11px] text-zinc-400">Gemini (≈₹{(r.usage.gemini_usd * 88).toFixed(1)})</p></div>
              <div className="rounded-xl bg-black/30 p-3 text-center"><p className="text-xl font-bold text-zinc-200">≈${r.usage.claude_usd_equivalent.toFixed(2)}</p>
                <p className="text-[11px] text-zinc-400">Claude (subscription)</p></div>
              <div className="rounded-xl bg-black/30 p-3 text-center"><p className="text-xl font-bold text-zinc-200">{r.usage.calls}</p>
                <p className="text-[11px] text-zinc-400">AI calls · {r.usage.minutes ?? "?"} min</p></div>
            </div>
            <table className="w-full text-sm"><thead><tr className="text-left text-xs text-zinc-500"><th className="py-1">Step</th><th>Calls</th><th>Tokens in/out</th><th className="text-right">Cost</th></tr></thead>
              <tbody>{Object.entries(r.usage.steps).sort((a, b) => b[1].usd - a[1].usd).map(([k, v]) => <tr key={k} className="border-t border-white/5">
                <td className="py-1.5 text-zinc-200">{k}</td><td className="text-zinc-400">{v.calls}</td>
                <td className="font-mono text-xs text-zinc-400">{(v.in / 1000).toFixed(1)}K / {(v.out / 1000).toFixed(1)}K</td>
                <td className="text-right font-mono text-zinc-200">${v.usd.toFixed(4)}</td></tr>)}</tbody></table>
            <p className="text-xs text-zinc-500">Footage, emoji animation, rendering and Buffer are free. Claude runs on your Claude Code subscription (shown as API-equivalent).</p>
          </div> : <p className="text-sm text-zinc-400">Usage is tracked for reels made from now on.</p>)}
          {tab === "marketing" && (r.marketing ? <div className="prose-pack"><ReactMarkdown>{r.marketing}</ReactMarkdown></div> : <p className="text-sm text-zinc-400">No marketing pack.</p>)}
        </div>
      </div>
    </div>
  );
}
