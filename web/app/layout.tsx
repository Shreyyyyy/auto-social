import type {Metadata} from "next";
import {Inter, JetBrains_Mono} from "next/font/google";
import Link from "next/link";
import Nav from "@/components/Nav";
import "./globals.css";

const sans = Inter({subsets: ["latin"], variable: "--font-sans"});
const mono = JetBrains_Mono({subsets: ["latin"], variable: "--font-mono"});

export const metadata: Metadata = {title: "Case File Studio", description: "AI Case File reels: research, script, voice, footage, render, review."};

export default function RootLayout({children}: {children: React.ReactNode}) {
  return (
    <html lang="en" className={`${sans.variable} ${mono.variable}`}>
      <body className="min-h-screen bg-[radial-gradient(ellipse_at_top,_rgba(200,35,27,0.12),_transparent_55%)]">
        <div className="mx-auto flex max-w-7xl gap-8 px-6 py-6">
          <aside className="sticky top-6 hidden h-[calc(100vh-3rem)] w-56 shrink-0 flex-col md:flex">
            <Link href="/" className="mb-8 flex items-center gap-3">
              <span className="grid h-10 w-10 place-items-center rounded-xl bg-case-500 text-lg shadow-lg shadow-case-500/30">📁</span>
              <span>
                <span className="block font-mono text-sm font-bold tracking-wide">CASE FILE</span>
                <span className="block text-xs text-zinc-400">AI ki Chai-Break Class</span>
              </span>
            </Link>
            <Nav />
            <p className="mt-auto text-xs leading-relaxed text-zinc-500">Nothing is posted until you press Post.</p>
          </aside>
          <main className="min-w-0 flex-1">{children}</main>
        </div>
      </body>
    </html>
  );
}
