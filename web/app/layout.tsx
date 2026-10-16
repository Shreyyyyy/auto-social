import type {Metadata, Viewport} from "next";
import {Inter, JetBrains_Mono, Space_Grotesk} from "next/font/google";
import Link from "next/link";
import Backdrop from "@/components/Backdrop";
import Logo from "@/components/Logo";
import Nav from "@/components/Nav";
import "./globals.css";

const sans = Inter({subsets: ["latin"], variable: "--font-sans"});
const display = Space_Grotesk({subsets: ["latin"], variable: "--font-display"});
const mono = JetBrains_Mono({subsets: ["latin"], variable: "--font-mono"});

export const metadata: Metadata = {title: {default: "Katha", template: "%s · Katha"}, description: "Topic in, reels everywhere: research, script, voice, footage, render, review and post.",
  appleWebApp: {capable: true, title: "Katha", statusBarStyle: "black-translucent"}};
export const viewport: Viewport = {themeColor: "#05040b"};

export default function RootLayout({children}: {children: React.ReactNode}) {
  return (
    <html lang="en" className={`${sans.variable} ${display.variable} ${mono.variable}`}>
      <body className="min-h-screen">
        <Backdrop />
        <div className="mx-auto flex max-w-[1560px] gap-10 px-4 py-6 sm:px-8 md:py-8">
          <aside className="card sticky top-8 hidden h-[calc(100vh-4rem)] w-64 shrink-0 flex-col p-5 md:flex">
            <Link href="/" className="group mb-10"><Logo /></Link>
            <Nav />
            <div className="mt-auto rounded-2xl border border-white/10 bg-black/20 p-4">
              <p className="flex items-center gap-2 text-xs font-medium text-zinc-300"><span className="h-2 w-2 animate-pulse rounded-full bg-emerald-400 shadow-[0_0_10px] shadow-emerald-400" /> Studio online</p>
              <p className="mt-1.5 text-xs leading-relaxed text-zinc-500">Posts go to Instagram, YouTube and LinkedIn via Buffer, only when you press Post or 🚀.</p>
            </div>
          </aside>
          <main className="min-w-0 flex-1 animate-rise">
            <div className="mb-6 space-y-4 md:hidden"><Link href="/" className="group block"><Logo /></Link><Nav /></div>
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
