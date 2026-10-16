"use client";
import Link from "next/link";
import {usePathname} from "next/navigation";

const ITEMS = [
  {href: "/", label: "New reel", icon: "✨"},
  {href: "/playlists", label: "Playlists", icon: "📚"},
  {href: "/library", label: "Library", icon: "🎬"},
  {href: "/competitors", label: "Competitors", icon: "🔎"},
];

export default function Nav() {
  const path = usePathname();
  return (
    <nav className="flex gap-1 overflow-x-auto md:flex-col md:space-y-1">
      {ITEMS.map((it) => {
        const active = it.href === "/" ? path === "/" : path.startsWith(it.href);
        return (
          <Link key={it.href} href={it.href}
            className={`relative flex shrink-0 items-center gap-3 rounded-2xl px-4 py-3 text-[0.95rem] font-medium transition ${active
              ? "bg-gradient-to-r from-case-500/30 via-white/[0.08] to-transparent text-white shadow-[inset_0_1px_0_rgba(255,255,255,.08)]"
              : "text-zinc-400 hover:bg-white/[0.06] hover:text-zinc-100"}`}>
            {active && <span className="absolute left-0 top-1/2 hidden h-6 w-1 -translate-y-1/2 rounded-full bg-gradient-to-b from-neon-cyan to-neon-pink shadow-[0_0_12px] shadow-case-400 md:block" />}
            <span className="text-lg">{it.icon}</span>{it.label}
          </Link>
        );
      })}
    </nav>
  );
}
