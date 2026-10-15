// News-explainer reel: full-screen real footage, burned-in creator captions, clean data cards, source chips.
// Every reel = this component + a props.json from reel.py. Colours come from config.json -> props.theme.
import React from "react";
import {AbsoluteFill, Audio, Easing, OffthreadVideo, Sequence, interpolate, spring, staticFile, useCurrentFrame} from "remotion";
import {loadFont} from "@remotion/google-fonts/Poppins";
import {loadFont as loadDeva} from "@remotion/google-fonts/Mukta";

const FONT = `${loadFont("normal", {weights: ["700", "800", "900"]}).fontFamily}, ${loadDeva("normal", {weights: ["800"]}).fontFamily}, sans-serif`;
const FPS = 30;
const pop = (t: number, at: number, damping = 14) => (t < at ? 0 : spring({frame: (t - at) * FPS, fps: FPS, config: {damping, stiffness: 200}}));
const clamp = {extrapolateLeft: "clamp", extrapolateRight: "clamp"} as const;
const font = (size: number, color: string, weight = 800): React.CSSProperties => ({fontFamily: FONT, fontWeight: weight, fontSize: size, color, lineHeight: 1.12, textAlign: "center"});
const card: React.CSSProperties = {background: "#fff", borderRadius: 20, padding: "20px 30px", boxShadow: "0 16px 44px rgba(0,0,0,.45)", boxSizing: "border-box"};
const col: React.CSSProperties = {display: "flex", flexDirection: "column", alignItems: "center", gap: 14};

// Clean white data cards - only on the few lines that need a number, steps, a comparison or a verdict.
const Card: React.FC<{v: any; t: number; s: number; e: number; HI: string; INK: string}> = ({v, t, s, e, HI, INK}) => {
  const k = pop(t, s), at = (i: number) => v.times?.[i] ?? s, fade = interpolate(t, [e - 0.05, e + 0.2], [1, 0], clamp);
  const head = v.title && v.type !== "quote" ? <div style={{...font(42, "#fff", 900), background: INK, borderRadius: 12, padding: "8px 20px", transform: `scale(${k})`}}>{v.title}</div> : null;
  let body: React.ReactNode = null;
  if (v.type === "counter") {
    const n = (v.number || 0) * Easing.out(Easing.cubic)(interpolate(t, [s, s + (e - s) * 0.6], [0, 1], clamp));
    body = <div style={{...card, transform: `scale(${k})`}}><div style={font(140, INK, 900)}>{n.toLocaleString("en-IN", {maximumFractionDigits: n < 10 ? 1 : 0})}{v.suffix}</div></div>;
  } else if (v.type === "flow") {
    body = <div style={{...col, gap: 8}}>{(v.items || []).map((it: string, i: number) => <React.Fragment key={i}>
      {i > 0 && <div style={{...font(40, "#fff"), opacity: pop(t, at(i)), textShadow: "0 2px 8px #000"}}>↓</div>}
      <div style={{...card, ...font(42, INK), padding: "12px 26px", background: i === v.items.length - 1 ? HI : "#fff", opacity: pop(t, at(i)), transform: `translateY(${(1 - pop(t, at(i))) * 30}px)`}}>{it}</div>
    </React.Fragment>)}</div>;
  } else if (v.type === "compare") {
    body = <div style={{display: "flex", gap: 16, alignItems: "center"}}>{[0, 1].map((i) => <React.Fragment key={i}>
      {i === 1 && <div style={{...font(40, INK, 900), background: HI, borderRadius: 40, padding: "8px 16px", transform: `scale(${pop(t, at(1), 9)})`}}>VS</div>}
      <div style={{...card, ...font(42, INK), width: 400, minHeight: 180, display: "flex", alignItems: "center", justifyContent: "center", opacity: pop(t, at(i)), transform: `scale(${pop(t, at(i))})`}}>{v.items?.[i]}</div>
    </React.Fragment>)}</div>;
  } else if (v.type === "stamp") {
    const p = pop(t, at(0), 10);
    body = <div style={{...card, ...font(58, INK, 900), display: "flex", alignItems: "center", gap: 18, opacity: p, transform: `scale(${interpolate(p, [0, 1], [1.6, 1])}) rotate(-3deg)`}}>
      <span style={{fontSize: 80}}>{v.good === false ? "❌" : "✅"}</span>{v.good === false ? "MYTH" : "FACT"}</div>;
  } else if (v.type === "list") {
    body = <div style={{...col, alignItems: "stretch", gap: 10}}>{(v.items || []).map((it: string, i: number) =>
      <div key={i} style={{...card, ...font(42, INK), textAlign: "left", width: 820, padding: "12px 24px", opacity: pop(t, at(i)), transform: `translateX(${(1 - pop(t, at(i))) * -100}px)`}}>✔ {it}</div>)}</div>;
  } else if (v.type === "quote") {
    body = <div style={{...card, ...font(56, INK, 900), maxWidth: 900, transform: `scale(${k})`}}>
      <span style={{backgroundImage: `linear-gradient(${HI}, ${HI})`, backgroundRepeat: "no-repeat", backgroundSize: `${interpolate(t, [s + 0.2, s + 0.9], [0, 100], clamp)}% 45%`, backgroundPosition: "0 90%"}}>{v.title}</span></div>;
  } else return null;
  return <div style={{...col, opacity: fade}}>{head}{body}</div>;
};

export const Reel: React.FC<any> = (p) => {
  const t = useCurrentFrame() / FPS, L = p.lines, HI = p.theme?.highlight || "#FFE600", INK = p.theme?.ink || "#111";
  const i = Math.max(0, L.findLastIndex((l: any) => l.start <= t)), line = L[i];
  const ws = line?.words || [], cur = ws.findLastIndex((w: any) => w[1] <= t), c0 = Math.floor(Math.max(cur, 0) / 3) * 3;
  const stroke = {WebkitTextStroke: "10px #000", paintOrder: "stroke"} as React.CSSProperties;
  return <AbsoluteFill style={{background: "#000", overflow: "hidden"}}>
    {/* full-screen real footage: hard cuts, slow push-in like a handheld edit */}
    {(p.shots || []).map((sh: any, j: number) => <Sequence key={j} from={Math.round(sh.start * FPS)} durationInFrames={Math.max(1, Math.round((sh.end - sh.start) * FPS))}>
      {sh.src ? <AbsoluteFill style={{transform: `scale(${1.02 + 0.05 * interpolate(t, [sh.start, sh.end], [0, 1], clamp)})`}}>
        <OffthreadVideo src={staticFile(sh.src)} muted startFrom={Math.round((sh.offset || 0) * FPS)} style={{width: "100%", height: "100%", objectFit: "cover"}} />
      </AbsoluteFill>
      /* text scene: no relevant footage -> clean dark background with a slow glow (never unrelated footage) */
      : <AbsoluteFill style={{background: `radial-gradient(circle at ${50 + 20 * Math.sin(t * 0.7)}% ${40 + 15 * Math.cos(t * 0.5)}%, ${HI}26 0%, #101014 55%, #08080a 100%)`}} />}
    </Sequence>)}
    <AbsoluteFill style={{background: "linear-gradient(180deg, rgba(0,0,0,.42) 0%, rgba(0,0,0,0) 26%, rgba(0,0,0,0) 52%, rgba(0,0,0,.5) 100%)"}} />
    {/* hook headline while line 1 is spoken (the keyword on screen + in audio) */}
    {i === 0 && p.hook && <div style={{position: "absolute", top: 250, width: "100%", padding: "0 70px", boxSizing: "border-box", ...col}}>
      <div style={{...font(82, "#fff", 900), ...stroke, opacity: pop(t, 0.05), transform: `scale(${interpolate(pop(t, 0.05, 12), [0, 1], [1.2, 1])})`}}>
        {String(p.hook).split(" ").map((w: string, j: number, a: string[]) => <span key={j} style={j === a.length - 1 || /\d/.test(w) ? {color: HI} : {}}>{w}{j < a.length - 1 ? " " : ""}</span>)}
      </div></div>}
    {/* data card for the current line */}
    {L.map((l: any, j: number) => l.v?.type && l.v.type !== "none" && t >= l.start && t < l.end + 0.25 &&
      <AbsoluteFill key={j} style={{top: 300, height: 760, alignItems: "center", justifyContent: "center"}}><Card v={l.v} t={t} s={l.start} e={l.end} HI={HI} INK={INK} /></AbsoluteFill>)}
    {/* source chip whenever a line states a news fact */}
    {line?.source && <div style={{position: "absolute", top: 1090, left: 60, ...font(30, INK, 700), background: "rgba(255,255,255,.93)", borderRadius: 12, padding: "8px 16px",
      opacity: pop(t, line.start + 0.2), transform: `translateX(${(1 - pop(t, line.start + 0.2)) * -40}px)`}}>📰 {line.source}</div>}
    {/* text scene with no card: the spoken words become big centred kinetic type */}
    {line?.text_scene && line.v?.type === "none" && i > 0 && cur >= 0 && <div style={{position: "absolute", top: 640, width: "100%", padding: "0 70px", boxSizing: "border-box", textAlign: "center"}}>
      {ws.slice(c0, c0 + 3).map(([w, wt]: any, j: number) => c0 + j <= cur && <div key={j} style={{...font(124, c0 + j === cur ? HI : "#fff", 900), opacity: pop(t, wt, 12),
        transform: `translateY(${(1 - pop(t, wt, 12)) * 30}px)`}}>{w}</div>)}
    </div>}
    {/* creator-style captions: 3 words at a time, white with a black outline, spoken word highlighted */}
    {cur >= 0 && !(line?.text_scene && line.v?.type === "none" && i > 0) && <div style={{position: "absolute", top: 1170, width: "100%", padding: "0 60px", boxSizing: "border-box", textAlign: "center"}}>
      {ws.slice(c0, c0 + 3).map(([w, wt]: any, j: number) => c0 + j <= cur && <span key={j} style={{...font(86, c0 + j === cur ? HI : "#fff", 900), ...stroke, display: "inline-block", margin: "0 10px",
        textShadow: "0 5px 12px rgba(0,0,0,.5)", transform: `scale(${c0 + j === cur ? 0.88 + 0.12 * pop(t, wt, 12) : 1})`}}>{w}</span>)}
    </div>}
    <Audio src={staticFile(p.voice)} />
    {p.music && <Audio src={staticFile(p.music)} volume={0.08} loop />}
    {(p.sfx || []).map(([at, n]: any, j: number) => <Sequence key={j} from={Math.round(at * FPS)} durationInFrames={30}><Audio src={staticFile(`sfx/${n}.wav`)} volume={0.2} /></Sequence>)}
  </AbsoluteFill>;
};
