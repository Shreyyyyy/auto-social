"use client";
import Link from "next/link";
import {useEffect, useState} from "react";
import {api, Settings, Stats} from "@/lib/api";

type V = Record<string, string>;
type Step = {n: string; title: string; icon: string; what: string; tools: (v: V) => string[]; match?: RegExp; free?: string; where: string};

const LLM: Record<string, (v: V) => string> = {
  "claude-code": (v) => `Claude Code${v.CLAUDE_MODEL ? ` (${v.CLAUDE_MODEL})` : ""} - your subscription`,
  anthropic: (v) => `Anthropic API · ${v.ANTHROPIC_MODEL}`, gemini: (v) => `Gemini · ${v.SCRIPT_MODEL}`,
};

const STEPS: Step[] = [
  {n: "01", title: "Research", icon: "🔎", match: /^research/, where: "Settings → Research",
    what: "Finds what happened in the last 60 days, verified facts with sources and dates, everyday analogies, the common myth, what people are asking, and SEO keywords. The best two real examples are kept; the rest are dropped.",
    tools: (v) => v.RESEARCH_PROVIDER === "gemini" ? [`Gemini ${v.RESEARCH_MODEL} + Google Search grounding`] : ["Claude Code + web search · your subscription"]},
  {n: "02", title: "Script", icon: "✍️", match: /^script/, where: "Settings → Script writer",
    what: "Picks the genre (explainer, story, news, list, motivation...), the look (Case File or Story), a persona and the strongest of 5 hooks, then writes the script - for explainers: hook, concept, analogy, how-it-works, real news example, myth vs truth, “yaad rakho” line - each line with spoken Hindi, Hinglish caption, delivery note, footage searches and a teaching visual, plus caption, hashtags and SEO pack. Checks run on every draft (natural spoken sentences, numbers as words, length, required cards) and it is repaired up to 3 times.",
    tools: (v) => [(LLM[v.LLM_PROVIDER] || LLM["claude-code"])(v), `fallback: Gemini ${v.SCRIPT_MODEL}`, "your playbook from Competitors"]},
  {n: "03", title: "Voice", icon: "🎙️", match: /^voice/, where: "Settings → Voice & music",
    what: "One narrator voice reads every line and acts its delivery note (excited, a lowered voice for a secret, sad, amused). It runs free on this Mac: VoxCPM2 for Hindi and English, OmniVoice for other Indian languages, picked from a listening test of 12 open models. To use your own voice, put a 10-second recording in assets/voice/narrator.wav. Line timings come from the real audio.",
    tools: (v) => v.TTS_ENGINE === "edge" ? [`Edge ${v.EDGE_VOICE}`] : v.TTS_ENGINE === "gemini" ? [`Gemini TTS ${v.TTS_MODEL}`] : ["VoxCPM2 (Hindi/English)", "OmniVoice (other Indian languages)", "MLX on Apple silicon"]},
  {n: "04", title: "Footage & visuals", icon: "🎞️", match: /^footage/, where: "Settings → Reel",
    what: "Searches free stock video for every line, Claude looks at the preview frames and scores how well each matches what is being said. Weak matches become a clean text scene instead of unrelated footage. Whiteboard cards (definitions, diagrams, charts, chat demos) and animated emoji are drawn on top.",
    tools: (v) => ["Pexels", "Pixabay", "Coverr", "Openverse", "Wikimedia Commons", "Prelinger Archive", `Claude ${v.CLAUDE_JUDGE_MODEL || "sonnet"} vision judge`, "Noto animated emoji (Lottie)"]},
  {n: "05", title: "Music & sound", icon: "🎵", match: /^music/, where: "Settings → Voice & music",
    what: "A 30-second instrumental made for this reel's mood, plus whooshes and pops on every cut and card - or your own music.mp3.",
    tools: (v) => [`Lyria ${v.MUSIC_MODEL}`, "ffmpeg-generated SFX"]},
  {n: "06", title: "Render", icon: "🖥️", free: "Free - runs on your computer", where: "",
    what: "Remotion (a React video framework) renders the 1080×1920 reel in headless Chrome: footage, cards, red-string corkboard transitions, animated emoji and the voice/music mix. Then the cover image and a contact sheet with one frame per line.",
    tools: () => ["Remotion", "headless Chrome", "ffmpeg", "OpenCV"]},
  {n: "07", title: "Beginner review", icon: "🧐", match: /^beginner review/, where: "Settings → Reel",
    what: "Claude watches the finished video (a frame per line + what is said) as a viewer who knows nothing: what it learned, scores for hook, clarity, teaching, visuals, accuracy and pacing, and timestamped problems. If it isn't good enough the script is rewritten from the feedback and the reel re-made once; the better version is kept.",
    tools: (v) => [`Claude ${v.CLAUDE_JUDGE_MODEL || "sonnet"} · your subscription`]},
  {n: "08", title: "Post", icon: "📤", free: "Free - Buffer free plan", where: "Settings → Posting",
    what: "The video is uploaded to a public link and queued on the channels you switch on: an Instagram reel, a YouTube Short (title + #Shorts) and a LinkedIn video, each with the caption and hashtags. Nothing posts until you press Post or 🚀.",
    tools: (v) => ["Buffer API", v.CLOUDINARY_URL ? "Cloudinary" : "catbox.moe upload", "Instagram", "YouTube", "LinkedIn"]},
];

const usd = (x: number) => (x < 0.01 && x > 0 ? `$${x.toFixed(3)}` : `$${x.toFixed(2)}`);

export default function How() {
  const [st, setSt] = useState<Stats | null>(null);
  const [v, setV] = useState<V>({});
  const [perDay, setPerDay] = useState(1);
  useEffect(() => {
    api.stats().then(setSt).catch(() => {});
    api.settings().then((s: Settings) => { const o: V = {}; s.groups.forEach((g) => g.fields.forEach((f) => { o[f.key] = f.value || f.default; })); setV(o); }).catch(() => {});
  }, []);

  // expected cost per reel for a stage = avg cost when the step runs × how often it runs
  const cost = (re?: RegExp) => !st || !re ? 0 : Object.entries(st.steps).filter(([k]) => re.test(k)).reduce((a, [, s]) => a + s.avg_usd * s.share, 0);
  const calls = (re?: RegExp) => !st || !re ? 0 : Object.entries(st.steps).filter(([k]) => re.test(k)).reduce((a, [, s]) => a + s.calls_per_reel * s.share, 0);
  const sub = st ? Object.entries(st.steps).filter(([, s]) => s.model === "claude").reduce((a, [, s]) => a + s.avg_usd * s.share, 0) : 0;
  const perReel = st ? st.avg_paid_usd : 0;
  const max = Math.max(...STEPS.map((s) => cost(s.match)), 0.0001);

  return (
    <div className="space-y-8">
      <header>
        <p className="label text-case-400">How it works</p>
        <h1 className="mt-1 text-3xl font-bold sm:text-5xl">One topic → <span className="text-gradient">eight steps</span> → three channels</h1>
        <p className="mt-3 max-w-3xl text-base text-zinc-400">Everything Katha does for one reel, the tools behind each step, and what it really costs -
          averaged from {st ? `your last ${st.reels} reels` : "your reels"}. Change any provider or model in <Link href="/settings" className="text-case-400 hover:underline">Settings</Link>.</p>
      </header>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          {k: "Per reel (paid APIs)", v: st ? usd(perReel) : "…", s: st ? `≈ ₹${(perReel * 88).toFixed(0)}` : ""},
          {k: "Time per reel", v: st ? `${st.avg_minutes} min` : "…", s: "research to review"},
          {k: "Claude subscription", v: sub ? `≈${usd(sub)}` : "$0", s: "API-equivalent, already paid"},
          {k: "Per month", v: st ? usd(perReel * perDay * 30) : "…", s: `${perDay} reel${perDay > 1 ? "s" : ""}/day · ≈ ₹${(perReel * perDay * 30 * 88).toFixed(0)}`},
        ].map((x) => (
          <div key={x.k} className="card p-5">
            <p className="label">{x.k}</p>
            <p className="mt-2 font-display text-3xl font-bold">{x.v}</p>
            <p className="mt-1 text-xs text-zinc-500">{x.s}</p>
          </div>
        ))}
      </div>
      <div className="card flex flex-wrap items-center gap-4 p-4">
        <span className="text-sm text-zinc-300">Reels per day</span>
        <input type="range" min={1} max={10} value={perDay} onChange={(e) => setPerDay(+e.target.value)} className="flex-1 accent-case-500" />
        <span className="w-28 text-right font-mono text-sm text-zinc-200">{perDay}/day = {usd(perReel * perDay * 30)}/mo</span>
      </div>

      <ol className="relative space-y-4 before:absolute before:bottom-6 before:left-[27px] before:top-6 before:w-px before:bg-gradient-to-b before:from-neon-cyan/60 before:via-case-400/40 before:to-neon-pink/60">
        {STEPS.map((s) => {
          const c = cost(s.match), n = calls(s.match);
          return (
            <li key={s.n} className="relative flex gap-4 sm:gap-6">
              <span className="relative z-10 grid h-14 w-14 shrink-0 place-items-center rounded-2xl border border-white/15 bg-[#0d0920] text-2xl shadow-lg shadow-case-500/20">{s.icon}</span>
              <div className="card min-w-0 flex-1 p-5">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <h2 className="text-xl font-semibold"><span className="mr-2 font-mono text-sm text-case-400">{s.n}</span>{s.title}</h2>
                  <div className="text-right">
                    <p className="font-display text-xl font-bold">{s.free ? "Free" : st ? usd(c) : "…"}</p>
                    <p className="text-[11px] text-zinc-500">{s.free || (st ? `per reel · ${n.toFixed(1)} AI calls` : "")}</p>
                  </div>
                </div>
                {!s.free && st && <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/5">
                  <div className="h-full rounded-full bg-gradient-to-r from-neon-cyan via-case-400 to-neon-pink" style={{width: `${Math.max(2, (c / max) * 100)}%`}} /></div>}
                <p className="mt-3 text-sm leading-relaxed text-zinc-300">{s.what}</p>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {s.tools(v).map((t) => <span key={t} className="chip bg-white/[0.05] text-zinc-300">{t}</span>)}
                  {s.where && <Link href="/settings" className="chip border-case-400/30 bg-case-500/10 text-case-400 hover:bg-case-500/20">⚙ {s.where}</Link>}
                </div>
              </div>
            </li>
          );
        })}
      </ol>

      {st && <div className="card p-5 sm:p-6">
        <p className="label mb-3">Every AI call, averaged per reel</p>
        <div className="overflow-x-auto"><table className="w-full min-w-[520px] text-sm">
          <thead><tr className="text-left text-xs text-zinc-500"><th className="py-2">Step</th><th>Model</th><th>Calls</th><th>Runs in</th><th className="text-right">Cost / reel</th></tr></thead>
          <tbody>{Object.entries(st.steps).sort((a, b) => b[1].avg_usd * b[1].share - a[1].avg_usd * a[1].share).map(([k, s]) => (
            <tr key={k} className="border-t border-white/5"><td className="py-2 text-zinc-200">{k}</td><td className="font-mono text-xs text-zinc-400">{s.model}</td>
              <td className="text-zinc-400">{s.calls_per_reel}</td><td className="text-zinc-400">{Math.round(s.share * 100)}% of reels</td>
              <td className="text-right font-mono text-zinc-200">{s.model === "claude" ? "subscription" : usd(s.avg_usd * s.share)}</td></tr>))}</tbody>
        </table></div>
        <p className="mt-3 text-xs text-zinc-500">Prices are the providers' paid-tier rates; Gemini's free tier and Google Search's 5,000 free grounded requests a month can make it cheaper.
          Claude Code runs on your subscription. Stock footage, emoji, rendering and Buffer are free.</p>
      </div>}
    </div>
  );
}
