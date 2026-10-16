// Typed client for server.py (proxied through Next.js rewrites: /api -> :8787/api, /media -> :8787/media)
export type Scores = Record<string, number>;
export type RunSummary = {
  id: string; title: string; status: string; series?: string; ep?: number; voice?: string;
  verdict?: string; scores?: Scores; cover?: string | null; video: string;
};
export type RunDetail = RunSummary & {
  caption: string; marketing?: string; research?: string; meta: Record<string, any>;
  review?: {learned?: string; remember?: string; verdict?: string; scores?: Scores; problems?: {time: string; issue: string; fix: string}[]};
  usage?: {gemini_usd: number; claude_usd_equivalent: number; calls: number; minutes?: number;
    steps: Record<string, {calls: number; in: number; out: number; usd: number; model: string}>};
  script?: {hook: string; case_title?: string; lines: {caption: string; visual: {type: string}; onscreen?: string; delivery?: string}[]};
};
export type Job = {id: string; kind: string; label: string; status: "running" | "done" | "error"; log: string; error?: string;
  started: number; ended?: number; result?: {run?: string; playlist?: string} | null};
export type PlaylistSummary = {id: string; name: string; subject?: string; created?: string; episodes: number; scripted: number; made: number};
export type Episode = {n: number; title: string; era?: string; brief?: string; status: string; run?: string | null; cover?: string | null;
  hook?: string; script: {say: string; visual: string; onscreen: string}[]};
export type Playlist = Omit<PlaylistSummary, "episodes"> & {episodes: Episode[]};

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, {cache: "no-store", ...init, headers: {"Content-Type": "application/json", ...(init?.headers || {})}});
  if (!r.ok) {
    let msg = `${r.status}`;
    try { msg = (await r.json()).detail || msg; } catch {}
    throw new Error(msg);
  }
  return r.json();
}

export const api = {
  runs: () => call<RunSummary[]>("/api/runs"),
  run: (id: string) => call<RunDetail>(`/api/runs/${id}`),
  makeReel: (prompt: string) => call<Job>("/api/reels", {method: "POST", body: JSON.stringify({prompt})}),
  currentJob: () => call<Job | null>("/api/jobs/current"),
  playlists: () => call<PlaylistSummary[]>("/api/playlists"),
  playlist: (id: string) => call<Playlist>(`/api/playlists/${id}`),
  newPlaylist: (subject: string, episodes: number) => call<Job>("/api/playlists", {method: "POST", body: JSON.stringify({subject, episodes})}),
  runEpisode: (id: string, n: number) => call<Job>(`/api/playlists/${id}/episodes/${n}/run`, {method: "POST"}),
  rewriteScript: (id: string, n: number) => call<Job>(`/api/playlists/${id}/episodes/${n}/script`, {method: "POST"}),
  approve: (id: string, caption: string) => call<{message: string}>(`/api/runs/${id}/approve`, {method: "POST", body: JSON.stringify({caption})}),
  post: (id: string, caption: string) => call<{message: string}>(`/api/runs/${id}/post`, {method: "POST", body: JSON.stringify({caption})}),
};

// Pipeline stages, recognised from the job log, for the progress stepper.
export const STAGES = [
  {key: "research", label: "Research", match: /researching/},
  {key: "script", label: "Script", match: /writing|planning|script/},
  {key: "voice", label: "Voice", match: /voice:|take \d/},
  {key: "footage", label: "Footage", match: /line \d+:|assets/},
  {key: "render", label: "Render", match: /rendering/},
  {key: "review", label: "Review", match: /review:/},
];
export const stageOf = (log: string) => STAGES.reduce((acc, s, i) => (s.match.test(log) ? i : acc), -1);
