"use client";
import Link from "next/link";
import {useCallback, useEffect, useState} from "react";
import JobPanel from "@/components/JobPanel";
import {api, Job, PlaylistSummary} from "@/lib/api";

export default function Playlists() {
  const [list, setList] = useState<PlaylistSummary[]>([]);
  const [subject, setSubject] = useState("");
  const [n, setN] = useState(10);
  const [err, setErr] = useState("");
  const load = () => api.playlists().then(setList).catch(() => {});
  useEffect(() => { load(); }, []);
  const onDone = useCallback((j: Job) => { load(); if (j.status === "done" && j.result?.playlist) window.location.href = `/playlists/${j.result.playlist}`; }, []);
  const create = async () => { setErr(""); try { await api.newPlaylist(subject, n); } catch (e: any) { setErr(e.message); } };

  return (
    <div className="space-y-6">
      <header>
        <p className="label text-case-400">Playlists</p>
        <h1 className="mt-1 text-3xl font-bold tracking-tight">A series of cases, one per day</h1>
        <p className="mt-2 max-w-2xl text-sm text-zinc-400">All scripts are written first so you can read them. Then make one video a day - each episode learns from the previous one's review and uses fresh research.</p>
      </header>

      <div className="card p-5">
        <p className="label mb-2">New playlist</p>
        <input className="input" placeholder="e.g. AI ki kahani: pehle computer se ChatGPT tak" value={subject} onChange={(e) => setSubject(e.target.value)} />
        <div className="mt-3 flex flex-wrap items-center gap-4">
          <label className="flex items-center gap-3 text-sm text-zinc-300">Episodes
            <input type="range" min={3} max={30} value={n} onChange={(e) => setN(+e.target.value)} className="accent-case-500" />
            <span className="w-8 font-mono">{n}</span></label>
          <button className="btn-primary ml-auto" disabled={!subject.trim()} onClick={create}>📝 Write {n} scripts</button>
        </div>
        {err && <p className="mt-3 rounded-xl bg-red-500/10 p-3 text-sm text-red-300">{err}</p>}
      </div>

      <JobPanel onDone={onDone} kind="playlist" />

      <div className="grid gap-4 sm:grid-cols-2">
        {list.map((p) => (
          <Link key={p.id} href={`/playlists/${p.id}`} className="card group p-5 transition hover:border-case-400/40">
            <p className="font-semibold leading-snug group-hover:text-white">{p.name}</p>
            <p className="mt-1 text-xs text-zinc-500">{p.created || ""}</p>
            <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-white/10"><div className="h-full bg-case-500" style={{width: `${(100 * p.made) / p.episodes}%`}} /></div>
            <p className="mt-2 text-xs text-zinc-400">{p.made}/{p.episodes} videos made · {p.scripted} scripts</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
