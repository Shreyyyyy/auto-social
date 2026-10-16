"use client";
import {useId} from "react";

// Katha (कथा, "story"): a speech bubble telling a story, a play button for the reel, a spark for the AI.
export function Mark({size = 48, className = ""}: {size?: number; className?: string}) {
  const id = useId().replace(/:/g, ""), g = `kg${id}`, h = `kh${id}`;  // unique per copy: a hidden copy must not own the gradient
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" className={className} aria-hidden>
      <defs>
        <linearGradient id={g} x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#22d3ee" /><stop offset=".5" stopColor="#8b5cf6" /><stop offset="1" stopColor="#f472b6" /></linearGradient>
        <radialGradient id={h} cx=".25" cy=".15" r=".9"><stop offset="0" stopColor="#fff" stopOpacity=".4" /><stop offset=".55" stopColor="#fff" stopOpacity="0" /></radialGradient>
      </defs>
      <rect x="2" y="2" width="60" height="60" rx="18" fill={`url(#${g})`} />
      <rect x="2" y="2" width="60" height="60" rx="18" fill={`url(#${h})`} />
      <path d="M20 14h24a9 9 0 0 1 9 9v13a9 9 0 0 1-9 9H29l-9.5 7.2c-1.3 1-3.1.1-3.1-1.6V44.3A9 9 0 0 1 11 36V23a9 9 0 0 1 9-9z" fill="#fff" />
      <path d="M28 22.6v14.8c0 1.5 1.6 2.4 2.9 1.6l11.6-7.4c1.2-.8 1.2-2.5 0-3.3l-11.6-7.3c-1.3-.8-2.9.1-2.9 1.6z" fill={`url(#${g})`} />
      <path d="M51 6.5l1.6 4.1 4.1 1.6-4.1 1.6L51 17.9l-1.6-4.1-4.1-1.6 4.1-1.6z" fill="#fde047" className="origin-[51px_12px] animate-pulse" />
    </svg>
  );
}

export default function Logo() {
  return (
    <span className="flex items-center gap-3">
      <span className="relative">
        <span className="absolute inset-0 rounded-2xl bg-case-500/50 blur-xl" />
        <Mark size={48} className="relative drop-shadow-lg transition duration-500 group-hover:rotate-[-6deg] group-hover:scale-105" />
      </span>
      <span>
        <span className="block font-display text-xl font-bold leading-none tracking-[0.18em]">KATHA</span>
        <span className="mt-1 block text-[11px] text-zinc-400">topic in · reels everywhere</span>
      </span>
    </span>
  );
}
