"use client";
import {useEffect, useMemo, useState} from "react";
import {api, ORModel, SettingField, Settings} from "@/lib/api";

// Which fields matter for the current choices (the rest are hidden, not lost).
const RELEVANT: Record<string, (v: Record<string, string>) => boolean> = {
  CLAUDE_MODEL: (v) => v.LLM_PROVIDER === "claude-code", CLAUDE_CODE_OAUTH_TOKEN: (v) => v.LLM_PROVIDER === "claude-code",
  ANTHROPIC_MODEL: (v) => v.LLM_PROVIDER === "anthropic", ANTHROPIC_EFFORT: (v) => v.LLM_PROVIDER === "anthropic", ANTHROPIC_API_KEY: (v) => v.LLM_PROVIDER === "anthropic",
  OPENROUTER_MODEL: (v) => v.LLM_PROVIDER === "openrouter" || v.RESEARCH_PROVIDER === "openrouter",
  OPENROUTER_API_KEY: (v) => v.LLM_PROVIDER === "openrouter" || v.RESEARCH_PROVIDER === "openrouter",
  OPENROUTER_RESEARCH_MODEL: (v) => v.RESEARCH_PROVIDER === "openrouter",
};
const SOURCE: Record<string, string> = {settings: "saved here", env: "from .env", default: "default"};

export default function SettingsPage() {
  const [s, setS] = useState<Settings | null>(null);
  const [edits, setEdits] = useState<Record<string, string | null>>({});
  const [models, setModels] = useState<ORModel[]>([]);
  const [msg, setMsg] = useState<{ok: boolean; text: string} | null>(null);
  const [saving, setSaving] = useState(false);
  const load = () => api.settings().then((x) => { setS(x); setEdits({}); }).catch((e) => setMsg({ok: false, text: e.message}));
  useEffect(() => { load(); api.openrouterModels().then(setModels).catch(() => {}); }, []);

  const current = useMemo(() => {
    const v: Record<string, string> = {};
    s?.groups.forEach((g) => g.fields.forEach((f) => { v[f.key] = edits[f.key] ?? f.value; }));
    return v;
  }, [s, edits]);
  if (!s) return <div className="card h-96 animate-pulse" />;

  const set = (k: string, v: string | null) => setEdits((e) => ({...e, [k]: v}));
  const dirty = Object.keys(edits).length;
  const save = async () => {
    setSaving(true); setMsg(null);
    try { setMsg({ok: true, text: (await api.saveSettings(edits)).message}); await load(); } catch (e: any) { setMsg({ok: false, text: e.message}); }
    setSaving(false);
  };

  const field = (f: SettingField) => {
    const val = edits[f.key] ?? f.value;
    const model = f.type === "openrouter" ? models.find((m) => m.id === val) : undefined;
    return (
      <div key={f.key} className="border-t border-white/5 py-4 first:border-0">
        <div className="mb-2 flex flex-wrap items-baseline justify-between gap-x-3">
          <p className="text-sm font-medium text-zinc-100">{f.label}</p>
          <p className="font-mono text-[10px] text-zinc-500">{f.key}</p>
        </div>
        <div className="min-w-0">
          {f.type === "select" ? (
            <select className="input py-2.5 text-sm" value={val || f.default} onChange={(e) => set(f.key, e.target.value)}>
              {f.options?.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          ) : f.type === "secret" ? (
            <div className="flex gap-2">
              <input type="password" autoComplete="off" className="input py-2.5 text-sm" value={edits[f.key] ?? ""}
                placeholder={f.set ? "•••••••• set - type to replace" : "not set"} onChange={(e) => set(f.key, e.target.value)} />
              {f.set && f.source === "settings" && <button className="btn-ghost shrink-0 px-3 text-xs" onClick={() => set(f.key, null)} title="Remove the saved key (falls back to .env)">Clear</button>}
            </div>
          ) : (
            <>
              <input className="input py-2.5 text-sm" type={f.type === "number" ? "number" : "text"} value={val} placeholder={f.default || "empty"}
                list={f.type === "openrouter" ? "or-models" : undefined} onChange={(e) => set(f.key, e.target.value)} />
              {model && <p className="mt-1 text-xs text-zinc-400">{model.name} · ${model.in.toFixed(2)} in / ${model.out.toFixed(2)} out per 1M tokens</p>}
            </>
          )}
          <div className="mt-1.5 flex flex-wrap items-center gap-2">
            <span className={`chip text-[10px] ${f.source === "settings" ? "bg-case-500/20 text-case-400" : "bg-white/5 text-zinc-500"}`}>{edits[f.key] !== undefined ? "unsaved" : SOURCE[f.source]}</span>
            {f.help && <span className="text-xs text-zinc-500">{f.help}</span>}
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-6 pb-24">
      <header>
        <p className="label text-case-400">Settings</p>
        <h1 className="mt-1 text-3xl font-bold sm:text-4xl">Choose your AI, keys and posting</h1>
        <p className="mt-2 max-w-2xl text-sm text-zinc-400">Saved settings override <code className="text-zinc-300">.env</code> and apply from the next reel. Keys are stored on this computer
          in <code className="text-zinc-300">settings.json</code> (never in git) and are never shown again after saving.</p>
      </header>
      {s.pending && <p className="rounded-2xl border border-amber-400/20 bg-amber-500/10 p-3 text-sm text-amber-300">Saved changes apply when the current job finishes.</p>}
      <datalist id="or-models">{models.map((m) => <option key={m.id} value={m.id}>{`${m.name} · $${m.in.toFixed(2)}/$${m.out.toFixed(2)}`}</option>)}</datalist>

      <div className="grid gap-6 xl:grid-cols-2">
        {s.groups.map((g) => {
          const fields = g.fields.filter((f) => !RELEVANT[f.key] || RELEVANT[f.key](current));
          return (
            <section key={g.group} className="card p-5 sm:p-6">
              <h2 className="mb-2 flex items-center gap-2 text-lg font-semibold"><span>{g.icon}</span>{g.group}</h2>
              {fields.map(field)}
            </section>
          );
        })}
      </div>

      <div className="fixed inset-x-0 bottom-4 z-20 flex justify-center px-4">
        <div className="card-glow flex w-full max-w-xl items-center gap-3 p-3">
          <p className="flex-1 truncate pl-2 text-sm text-zinc-300">
            {msg ? <span className={msg.ok ? "text-emerald-300" : "text-red-300"}>{msg.text}</span> : dirty ? `${dirty} unsaved change${dirty > 1 ? "s" : ""}` : "All saved"}</p>
          {dirty > 0 && <button className="btn-ghost px-4 py-2" onClick={() => { setEdits({}); setMsg(null); }}>Discard</button>}
          <button className="btn-primary px-5 py-2" disabled={!dirty || saving} onClick={save}>{saving ? "Saving…" : "Save"}</button>
        </div>
      </div>
    </div>
  );
}
