import type {Metadata} from "next";
import {Inter, JetBrains_Mono, Space_Grotesk} from "next/font/google";
import Link from "next/link";
import Backdrop from "@/components/Backdrop";
import Nav from "@/components/Nav";
import "./globals.css";

const sans = Inter({subsets: ["latin"], variable: "--font-sans"});
const display = Space_Grotesk({subsets: ["latin"], variable: "--font-display"});
const mono = JetBrains_Mono({subsets: ["latin"], variable: "--font-mono"});

export const metadata: Metadata = {title: "Case File Studio", description: "AI Case File reels: research, script, voice, footage, render, review."};

export default function RootLayout({children}: {children: React.ReactNode}) {
  return (
    <html lang="en" className={`${sans.variable} ${display.variable} ${mono.variable}`}>
      <body className="min-h-screen">
        <Backdrop />
        <div className="mx-auto flex max-w-[1560px] gap-10 px-4 py-6 sm:px-8 md:py-8">
          <aside className="card sticky top-8 hidden h-[calc(100vh-4rem)] w-64 shrink-0 flex-col p-5 md:flex">
            <Link href="/" className="group mb-10 flex items-center gap-3">
              <span className="relative grid h-12 w-12 place-items-center overflow-hidden rounded-2xl text-xl shadow-lg shadow-case-500/40">
                <span className="absolute inset-[-60%] animate-spin-slow bg-[conic-gradient(#22d3ee,#8b5cf6,#f472b6,#22d3ee)]" />
                <span className="absolute inset-[2px] rounded-[14px] bg-[#0d0920]" />
                <span className="relative">📁</span>
              </span>
              <span>
                <span className="block font-display text-base font-bold tracking-[0.2em]">CASE FILE</span>
                <span className="block text-xs text-zinc-400">AI ki Chai-Break Class</span>
              </span>
            </Link>
            <Nav />
            <div className="mt-auto rounded-2xl border border-white/10 bg-black/20 p-4">
              <p className="flex items-center gap-2 text-xs font-medium text-zinc-300"><span className="h-2 w-2 animate-pulse rounded-full bg-emerald-400 shadow-[0_0_10px] shadow-emerald-400" /> Studio online</p>
              <p className="mt-1.5 text-xs leading-relaxed text-zinc-500">Posts go to Instagram, YouTube and LinkedIn via Buffer, only when you press Post or 🚀.</p>
            </div>
          </aside>
          <main className="min-w-0 flex-1 animate-rise">
            <div className="mb-6 md:hidden"><Nav /></div>
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
