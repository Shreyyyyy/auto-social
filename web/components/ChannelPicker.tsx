"use client";
import {useEffect, useState} from "react";
import {api, Channel} from "@/lib/api";

export const NET: Record<string, {icon: string; name: string; on: string}> = {
  instagram: {icon: "📸", name: "Instagram", on: "from-pink-500/30 to-orange-400/20 border-pink-400/50 shadow-pink-500/30"},
  youtube: {icon: "▶️", name: "YouTube", on: "from-red-500/30 to-red-400/10 border-red-400/50 shadow-red-500/30"},
  linkedin: {icon: "💼", name: "LinkedIn", on: "from-sky-500/30 to-blue-400/10 border-sky-400/50 shadow-sky-500/30"},
};
const KEY = "post-channels";

// Buffer channels + which ones are switched on. The choice is remembered in this browser (all on by default).
export function useChannels() {
  const [channels, setChannels] = useState<Channel[] | null>(null);
  const [picked, setPicked] = useState<string[]>([]);
  useEffect(() => {
    api.channels().then((cs) => {
      setChannels(cs);
      let saved: string[] | null = null;
      try { saved = JSON.parse(localStorage.getItem(KEY) || "null"); } catch {}
      const all = cs.map((c) => c.service);
      setPicked(saved ? all.filter((s) => saved!.includes(s)) : all);
    }).catch(() => setChannels([]));
  }, []);
  const toggle = (s: string) => setPicked((p) => {
    const next = p.includes(s) ? p.filter((x) => x !== s) : [...p, s];
    try { localStorage.setItem(KEY, JSON.stringify(next)); } catch {}
    return next;
  });
  return {channels, picked, toggle};
}

// Toggle pills, one per channel. `sent` channels show as done and can't be toggled.
export default function ChannelPicker({channels, picked, toggle, sent = {}, failed = {}}: {
  channels: Channel[] | null; picked: string[]; toggle: (s: string) => void; sent?: Record<string, string>; failed?: Record<string, string>;
}) {
  if (channels === null) return <div className="h-11 w-72 animate-pulse rounded-2xl bg-white/5" />;
  if (!channels.length) return <p className="text-xs text-zinc-500">No Buffer channels found - check BUFFER_TOKEN.</p>;
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="label mr-1">Post to</span>
      {channels.map((c) => {
        const n = NET[c.service] || {icon: "🔗", name: c.service, on: "from-case-500/30 to-transparent border-case-400/50 shadow-case-500/30"};
        const done = !!sent[c.service], on = !done && picked.includes(c.service), err = failed[c.service];
        return (
          <button key={c.id} type="button" role="switch" aria-checked={on} disabled={done} onClick={() => toggle(c.service)}
            title={done ? `Already sent to ${n.name}` : err ? `Last try failed: ${err}` : `${c.name} - click to ${on ? "skip" : "include"}`}
            className={`group flex items-center gap-2.5 rounded-2xl border px-3.5 py-2 text-sm font-medium backdrop-blur-xl transition duration-200 ${done
              ? "cursor-default border-emerald-400/30 bg-emerald-500/10 text-emerald-300"
              : on ? `bg-gradient-to-br ${n.on} text-white shadow-lg` : "border-white/10 bg-white/[0.04] text-zinc-500 hover:border-white/25 hover:text-zinc-300"}`}>
            <span className={`text-base transition ${on || done ? "" : "grayscale opacity-60"}`}>{n.icon}</span>
            {n.name}
            {done ? <span className="text-xs">✓ sent</span>
              : <span className={`relative h-5 w-9 rounded-full transition ${on ? "bg-white/30" : "bg-white/10"}`}>
                  <span className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-all duration-200 ${on ? "left-[18px]" : "left-0.5 bg-zinc-400"}`} />
                </span>}
            {err && !done && <span className="text-xs text-red-300">!</span>}
          </button>
        );
      })}
    </div>
  );
}
