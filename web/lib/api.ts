// Typed client for server.py (proxied through Next.js rewrites: /api -> :8787/api, /media -> :8787/media)
export type Scores = Record<string, number>;
export type RunSummary = {
  id: string; title: string; status: string; series?: string; ep?: number; voice?: string;
  verdict?: string; scores?: Scores; cover?: string | null; video: string;
};
export type Channel = {id: string; name: string; service: string};
export type RunDetail = RunSummary & {
  sent: Record<string, string>; send_errors: Record<string, string>;
  caption: string; marketing?: string; research?: string; meta: Record<string, any>; contact?: string | null;
  review?: {learned?: string; remember?: string; verdict?: string; scores?: Scores; problems?: {time: string; issue: string; fix: string}[]};
  usage?: {gemini_usd: number; claude_usd_equivalent: number; calls: number; minutes?: number;
    steps: Record<string, {calls: number; in: number; out: number; usd: number; model: string}>};
  script?: {hook: string; case_title?: string; lines: {caption: string; visual: {type: string}; onscreen?: string; delivery?: string}[]};
};
export type Job = {id: string; kind: string; label: string; status: "running" | "done" | "error"; log: string; error?: string;
  started: number; ended?: number; result?: {run?: string; playlist?: string} | null};
export type PlaylistSummary = {id: string; name: string; subject?: string; created?: string; episodes: number; scripted: number; made: number};
export type Episode = {n: number; arc: number; builds_on: number[]; title: string; era?: string; brief?: string; status: string; run?: string | null; cover?: string | null;
  hook?: string; script: {say: string; visual: string; onscreen: string}[]};
export type Playlist = Omit<PlaylistSummary, "episodes"> & {episodes: Episode[]; arcs: {title: string; summary: string}[]};

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
  autopilot: (prompt: string, channels?: string[]) => call<Job>("/api/reels/autopilot", {method: "POST", body: JSON.stringify({prompt, channels})}),
  channels: () => call<Channel[]>("/api/channels"),
  currentJob:() => call<Job | null>("/api/jobs/current"),
  playlists: () => call<PlaylistSummary[]>("/api/playlists"),
  playlist: (id: string) => call<Playlist>(`/api/playlists/${id}`),
  newPlaylist: (subject: string, episodes: number) => call<Job>("/api/playlists", {method: "POST", body: JSON.stringify({subject, episodes})}),
  runEpisode: (id: string, n: number) => call<Job>(`/api/playlists/${id}/episodes/${n}/run`, {method: "POST"}),
  autopilotEpisode: (id: string, n: number, channels?: string[]) => call<Job>(`/api/playlists/${id}/episodes/${n}/autopilot`, {method: "POST", body: JSON.stringify({channels})}),
  rewriteScript: (id: string, n: number) => call<Job>(`/api/playlists/${id}/episodes/${n}/script`, {method: "POST"}),
  approve: (id: string, caption: string) => call<{message: string}>(`/api/runs/${id}/approve`, {method: "POST", body: JSON.stringify({caption})}),
  post: (id: string, caption: string, channels?: string[]) => call<{message: string}>(`/api/runs/${id}/post`, {method: "POST", body: JSON.stringify({caption, channels})}),
  deletePlaylist: (id: string, deleteVideos: boolean = false) => call<{message: string}>(`/api/playlists/${id}${deleteVideos ? "?delete_videos=true" : ""}`, {method: "DELETE"}),
  deleteRun: (id: string) => call<{message: string}>(`/api/runs/${id}`, {method: "DELETE"}),
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
// Autopilot jobs also post: one more stage after the review.
export const stagesFor = (kind: string) => kind === "autopilot" ? [...STAGES, {key: "post", label: "Buffer", match: /sending to Buffer/}] : STAGES;
export const stageOf = (log: string, stages = STAGES) => stages.reduce((acc, s, i) => (s.match.test(log) ? i : acc), -1);
