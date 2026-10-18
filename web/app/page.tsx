"use client";
import {useCallback, useState} from "react";
import JobPanel from "@/components/JobPanel";
import ChannelPicker, {NET, useChannels} from "@/components/ChannelPicker";
import ReelView from "@/components/ReelView";
import {api, Job} from "@/lib/api";

const IDEAS = ["ChatGPT kaise kaam karta hai?", "Deepfake kaise pehchaane?", "AI agent kya hota hai?", "AI hallucination kya hai?"];
const PIPE = ["Research", "Script", "Voice", "Footage", "Render", "Review", "Post"];

export default function NewReel() {
  const [prompt, setPrompt] = useState("");
  const [err, setErr] = useState("");
  const [run, setRun] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const {channels, picked, toggle} = useChannels();
  const names = picked.map((s) => NET[s]?.name || s).join(", ");

  const onDone = useCallback((j: Job) => { if (j.status === "done" && j.result?.run) setRun(j.result.run); }, []);
  const start = async (auto = false) => {
    if (auto && !confirm(`Autopilot makes the reel and sends it straight to ${names} via Buffer — no review step. Go?`)) return;
    setErr(""); setRun(null); setStarting(true);
    try { await (auto ? api.autopilot(prompt, picked) : api.makeReel(prompt)); } catch (e: any) { setErr(e.message); }
    setStarting(false);
  };

  return (
    <div className="space-y-8">
      <header className="pt-2 md:pt-6">
        <p className="chip w-fit bg-white/[0.06] text-case-400"><span className="h-1.5 w-1.5 animate-pulse rounded-full bg-neon-cyan" /> New case</p>
        <h1 className="mt-5 max-w-4xl font-display text-4xl font-bold leading-[1.05] tracking-tight sm:text-6xl">
          What should <span className="text-gradient">today's reel</span> be?
        </h1>
        <p className="mt-4 max-w-2xl text-base text-zinc-400 sm:text-lg">Type a topic. The studio researches it, writes the script, records the voice, finds footage, renders, reviews — and can post it everywhere.</p>
        <div className="mt-6 flex flex-wrap items-center gap-2">
          {PIPE.map((s, i) => (
            <span key={s} className="flex items-center gap-2">
              <span className="chip bg-white/[0.05] font-mono text-[11px] text-zinc-300" style={{animationDelay: `${i * .4}s`}}>
                <span className="text-case-400">{String(i + 1).padStart(2, "0")}</span>{s}</span>
              {i < PIPE.length - 1 && <span className="h-px w-4 bg-gradient-to-r from-case-400/60 to-transparent" />}
            </span>
          ))}
        </div>
      </header>

      <div className="card-glow p-5 sm:p-7">
        <textarea className="input min-h-36 text-lg sm:text-xl" placeholder="Anything - e.g. Machine learning kya hai? / Zomato ki kahani, menu card se ₹2 lakh crore tak / 5 UPI scams jo abhi chal rahe hain" value={prompt}
          onChange={(e) => setPrompt(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey) && prompt.trim()) start(); }} />
        <div className="mt-4 flex flex-wrap gap-2">
          {IDEAS.map((i) => <button key={i} className="chip bg-white/[0.05] text-zinc-300 transition hover:border-case-400/50 hover:bg-white/10 hover:text-white" onClick={() => setPrompt(i)}>{i}</button>)}
        </div>
        <div className="mt-6 border-t border-white/10 pt-5"><ChannelPicker channels={channels} picked={picked} toggle={toggle} /></div>
        <div className="mt-5 grid gap-3 sm:grid-cols-2">
          <button className="btn-ghost py-4 text-base" disabled={!prompt.trim() || starting} onClick={() => start()}>
            ▶ Make reel <span className="text-xs font-normal text-zinc-400">· you approve before posting</span></button>
          <button className="btn-hyper py-4 text-base" disabled={!prompt.trim() || starting || !picked.length} onClick={() => start(true)}
            title={`Research → script → reel → post to ${names || "nothing - pick a channel"}, in one go`}>
            🚀 {picked.length === (channels?.length || 3) ? "Make & post everywhere" : picked.length ? "Make & post" : "Pick a channel"}
            {picked.length > 0 && <span className="text-sm">{picked.map((s) => NET[s]?.icon).join(" ")}</span>}</button>
        </div>
        {err && <p className="mt-4 rounded-2xl border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-300">{err}</p>}
      </div>

      <JobPanel onDone={onDone} kind={["reel", "autopilot"]} />
      {run && <ReelView id={run} />}
    </div>
  );
}
