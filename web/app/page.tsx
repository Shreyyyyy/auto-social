"use client";
import {useCallback, useState} from "react";
import JobPanel from "@/components/JobPanel";
import ReelView from "@/components/ReelView";
import {api, Job} from "@/lib/api";

const IDEAS = ["ChatGPT kaise kaam karta hai?", "Deepfake kaise pehchaane?", "AI agent kya hota hai?", "AI hallucination kya hai?"];

export default function NewReel() {
  const [prompt, setPrompt] = useState("");
  const [err, setErr] = useState("");
  const [run, setRun] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  const onDone = useCallback((j: Job) => { if (j.status === "done" && j.result?.run) setRun(j.result.run); }, []);
  const start = async () => {
    setErr(""); setRun(null); setStarting(true);
    try { await api.makeReel(prompt); } catch (e: any) { setErr(e.message); }
    setStarting(false);
  };

  return (
    <div className="space-y-6">
      <header>
        <p className="label text-case-400">New case</p>
        <h1 className="mt-1 text-3xl font-bold tracking-tight">What should this reel teach?</h1>
        <p className="mt-2 max-w-2xl text-sm text-zinc-400">One prompt → research, a Case File script, two voices auditioned, real footage + animation, render, cover, SEO pack and a beginner review. Takes about 6–9 minutes.</p>
      </header>

      <div className="card p-5">
        <textarea className="input min-h-28 text-base" placeholder="e.g. Machine learning kya hai? / Deepfake kaise pehchaane?" value={prompt}
          onChange={(e) => setPrompt(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey) && prompt.trim()) start(); }} />
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {IDEAS.map((i) => <button key={i} className="chip bg-white/5 text-zinc-300 hover:bg-white/10" onClick={() => setPrompt(i)}>{i}</button>)}
          <button className="btn-primary ml-auto px-6" disabled={!prompt.trim() || starting} onClick={start}>▶ Run</button>
        </div>
        {err && <p className="mt-3 rounded-xl bg-red-500/10 p-3 text-sm text-red-300">{err}</p>}
      </div>

      <JobPanel onDone={onDone} kind="reel" />
      {run && <ReelView id={run} />}
    </div>
  );
}
