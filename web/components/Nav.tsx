"use client";
import Link from "next/link";
import {usePathname} from "next/navigation";

const ITEMS = [
  {href: "/", label: "New reel", icon: "✨"},
  {href: "/playlists", label: "Playlists", icon: "📚"},
  {href: "/library", label: "Library", icon: "🎬"},
];

export default function Nav() {
  const path = usePathname();
  return (
    <nav className="space-y-1">
      {ITEMS.map((it) => {
        const active = it.href === "/" ? path === "/" : path.startsWith(it.href);
        return (
          <Link key={it.href} href={it.href}
            className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition ${active ? "bg-white/10 text-white" : "text-zinc-400 hover:bg-white/5 hover:text-zinc-100"}`}>
            <span>{it.icon}</span>{it.label}
          </Link>
        );
      })}
    </nav>
  );
}
