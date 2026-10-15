// One reusable Gen-Z motion-graphics template. Every reel = this component + a props.json from reel.py.
import React from "react";
import {AbsoluteFill, Audio, Easing, Img, OffthreadVideo, Sequence, interpolate, spring, staticFile, useCurrentFrame} from "remotion";
import {loadFont} from "@remotion/google-fonts/BricolageGrotesque";
import {loadFont as loadDeva} from "@remotion/google-fonts/Mukta";

const FONT = `${loadFont("normal", {weights: ["800"]}).fontFamily}, ${loadDeva("normal", {weights: ["800"]}).fontFamily}, sans-serif`;
const FPS = 30, ACC = "#C6FF00", ACC2 = "#8B5CF6", BG = "#0B0B12";
const pop = (t: number, at: number, damping = 11) => (t < at ? 0 : spring({frame: (t - at) * FPS, fps: FPS, config: {damping, stiffness: 170}}));
const clamp = {extrapolateLeft: "clamp", extrapolateRight: "clamp"} as const;
const text = (size: number, color = "#fff"): React.CSSProperties => ({fontFamily: FONT, fontWeight: 800, fontSize: size, color, textAlign: "center", lineHeight: 1.08});
const card: React.CSSProperties = {background: "rgba(255,255,255,.08)", border: "2px solid rgba(255,255,255,.16)", borderRadius: 36, padding: "26px 36px", boxSizing: "border-box"};
const col: React.CSSProperties = {display: "flex", flexDirection: "column", alignItems: "center", gap: 18};

const Visual: React.FC<{v: any; t: number; s: number; e: number}> = ({v, t, s, e}) => {
  const d = e - s, k = pop(t, s), at = (i: number) => v.times?.[i] ?? s;
  const title = v.title ? <div style={{...text(76), transform: `scale(${0.7 + 0.3 * k})`}}>{v.title}</div> : null;
  switch (v.type) {
    case "hook": {
      const shake = t - s < 0.35 ? 16 * Math.sin(t * 95) : 0;
      return <div style={{...col, transform: `translateX(${shake}px)`}}>
        {v.emoji && <div style={{fontSize: 210, transform: `scale(${pop(t, s + 0.15, 8)})`}}>{v.emoji}</div>}
        <div style={{...text(118), transform: `scale(${interpolate(k, [0, 1], [2.4, 1])})`, textShadow: `0 0 40px ${ACC}88`}}>{v.title}</div>
      </div>;
    }
    case "flow": return <div style={col}>{title}{(v.items || []).map((it: string, i: number) => {
      const last = i === v.items.length - 1, p = pop(t, at(i));
      return <React.Fragment key={i}>
        {i > 0 && <div style={{width: 10, borderRadius: 5, background: ACC, height: interpolate(t, [at(i) - 0.25, at(i)], [0, 30], clamp)}} />}
        <div style={{...card, ...text(v.items.length > 4 ? 40 : 50, last ? BG : "#fff"), background: last ? ACC : card.background, width: 760, padding: "18px 30px", opacity: p, transform: `scale(${p})`}}>{it}</div>
      </React.Fragment>;
    })}</div>;
    case "counter": {
      const n = (v.number || 0) * Easing.out(Easing.cubic)(interpolate(t, [s, s + d * 0.7], [0, 1], clamp));
      return <div style={col}>
        <div style={{...text(200, ACC), transform: `scale(${k})`, textShadow: `0 0 50px ${ACC}66`}}>{n.toLocaleString("en-IN", {maximumFractionDigits: n < 10 ? 1 : 0})}{v.suffix}</div>{title}</div>;
    }
    case "compare": return <div style={col}>{title}<div style={{display: "flex", gap: 30, alignItems: "center"}}>
      {[0, 1].map((i) => <div key={i} style={{...card, ...text(54), width: 420, minHeight: 300, display: "flex", alignItems: "center", justifyContent: "center",
        borderColor: i ? ACC : ACC2, transform: `translateY(${(1 - pop(t, at(i))) * 300}px)`, opacity: pop(t, at(i))}}>{v.items?.[i]}</div>)}
    </div><div style={{...text(64, BG), background: ACC, borderRadius: 50, padding: "10px 34px", transform: `scale(${pop(t, at(1), 7)})`, marginTop: -60}}>VS</div></div>;
    case "stamp": {
      const p = pop(t, at(0), 8);
      return <div style={col}>{title}<div style={{fontSize: 300, opacity: p, transform: `scale(${interpolate(p, [0, 1], [3, 1])}) rotate(-12deg)`}}>{v.good === false ? "❌" : "✅"}</div></div>;
    }
    case "list": return <div style={{...col, alignItems: "stretch"}}>{title}{(v.items || []).map((it: string, i: number) =>
      <div key={i} style={{...card, ...text(54), textAlign: "left", width: 820, opacity: pop(t, at(i)), transform: `translateX(${(1 - pop(t, at(i))) * -500}px)`}}>
        <span style={{color: ACC}}>✓ </span>{it}</div>)}</div>;
    case "image": case "video": return <div style={{...col, gap: 0}}>
      <div style={{width: 800, height: 760, borderRadius: 44, overflow: "hidden", border: `4px solid ${ACC}`, transform: `scale(${0.8 + 0.2 * k}) rotate(${(1 - k) * -6}deg)`, boxShadow: "0 30px 80px rgba(0,0,0,.6)"}}>
        {v.type === "video" ? <OffthreadVideo src={staticFile(v.src)} muted style={{width: "100%", height: "100%", objectFit: "cover"}} />
          : <Img src={staticFile(v.src)} style={{width: "100%", height: "100%", objectFit: "cover", transform: `scale(${1 + 0.1 * (t - s) / d})`}} />}
      </div>
      {v.title && <div style={{...text(60, BG), background: ACC, borderRadius: 24, padding: "14px 30px", marginTop: -50, transform: `scale(${pop(t, s + 0.3)}) rotate(-2deg)`}}>{v.title}</div>}
    </div>;
    case "quote": return <div style={{...text(84), padding: "0 40px", transform: `scale(${0.8 + 0.2 * k})`}}>
      <span style={{backgroundImage: `linear-gradient(${ACC}66, ${ACC}66)`, backgroundRepeat: "no-repeat", backgroundSize: `${interpolate(t, [s + 0.3, s + 1.1], [0, 100], clamp)}% 40%`, backgroundPosition: "0 85%"}}>{v.title}</span></div>;
    default: return <div style={col}>{v.emoji && <div style={{fontSize: 250, transform: `translateY(${-30 * Math.abs(Math.sin((t - s) * 5))}px) scale(${pop(t, s, 7)})`}}>{v.emoji}</div>}{title}</div>;
  }
};

export const Reel: React.FC<any> = (p) => {
  const t = useCurrentFrame() / FPS, L = p.lines;
  const i = Math.max(0, L.findLastIndex((l: any) => l.start <= t)), line = L[i], prev = L[i - 1]?.speaker;
  const ws = line.words, cur = ws.findLastIndex((w: any) => w[1] <= t), c0 = Math.floor(Math.max(cur, 0) / 3) * 3;
  const end = p.duration - 1.3, k = Math.min(1, (t - line.start) / 0.25);
  return <AbsoluteFill style={{background: BG, overflow: "hidden"}}>
    {[[ACC2, 0], ["#00C2FF", 2], [ACC, 4]].map(([c, o]: any, j) => <div key={j} style={{position: "absolute", width: 900, height: 900, borderRadius: "50%", background: `radial-gradient(circle, ${c}33 0%, transparent 65%)`,
      left: 90 + 380 * Math.sin(t * 0.4 + o), top: 510 + 600 * Math.cos(t * 0.3 + o)}} />)}
    {/* visuals, one Sequence per line so stock video plays from its start */}
    {L.map((l: any, j: number) => { const to = L[j + 1]?.start ?? p.duration; return <Sequence key={j} from={Math.round(l.start * FPS)} durationInFrames={Math.max(1, Math.round((to - l.start) * FPS))}>
      <AbsoluteFill style={{top: 450, height: 820, alignItems: "center", justifyContent: "center", transform: `scale(${1 + 0.08 * Math.max(0, 1 - (t - l.start) / 0.2)})`}}>
        <Visual v={l.v} t={t} s={l.start} e={l.end} /></AbsoluteFill></Sequence>; })}
    {/* hosts as facecam bubbles */}
    {Object.entries(p.hosts).map(([n, src]: any, j) => {
      const on = line.speaker === n, same = prev === line.speaker, size = on ? (same ? 250 : 150 + 100 * k) : (n === prev && !same ? 250 - 100 * k : 150);
      return <div key={n} style={{position: "absolute", top: 170 + (on ? 6 * Math.sin(t * 6) : 0), [j ? "right" : "left"]: 70, ...col, gap: 10}}>
        <Img src={staticFile(src)} style={{width: size, height: size, borderRadius: "50%", objectFit: "cover", border: `6px solid ${on ? ACC : "#ffffff33"}`,
          boxShadow: on ? `0 0 0 ${8 + 8 * Math.abs(Math.sin(t * 7))}px ${ACC}55` : "none", filter: on ? "none" : "grayscale(.6) brightness(.7)"}} />
        {on && <div style={{...text(34, BG), background: ACC, borderRadius: 20, padding: "4px 18px", transform: `scale(${pop(t, line.start)})`}}>{n === "Uncle" ? "Sharma Uncle" : n}</div>}
      </div>;
    })}
    {/* karaoke captions */}
    {cur >= 0 && t < end && <div style={{position: "absolute", top: 1310, width: "100%", padding: "0 60px", boxSizing: "border-box", textAlign: "center"}}>
      {ws.slice(c0, c0 + 3).map(([w, wt]: any, j: number) => c0 + j <= cur && <span key={j} style={{...text(94, c0 + j === cur ? ACC : "#fff"), display: "inline-block", margin: "0 12px",
        transform: `scale(${c0 + j === cur ? 0.7 + 0.35 * pop(t, wt, 9) : 1})`, WebkitTextStroke: "4px #000", paintOrder: "stroke", textShadow: "0 8px 0 #000"}}>{w}</span>)}
    </div>}
    {/* open loop sticker + progress bar + flash on hook + end card */}
    {t > 1.6 && t < p.duration * 0.7 && <div style={{position: "absolute", top: 1440, left: 60, ...text(36, "#fff"), background: ACC2, borderRadius: 18, padding: "8px 18px",
      transform: `rotate(${6 + 3 * Math.sin(t * 3)}deg) scale(${pop(t, 1.6)})`}}>wait for the end 👀</div>}
    <div style={{position: "absolute", top: 0, left: 0, height: 14, width: `${(100 * t) / p.duration}%`, background: ACC, boxShadow: `0 0 20px ${ACC}`}} />
    <AbsoluteFill style={{background: "#fff", opacity: Math.max(0, 0.7 - t * 5), pointerEvents: "none"}} />
    {t >= end && <AbsoluteFill style={{background: `${BG}dd`, alignItems: "center", justifyContent: "center"}}>
      <div style={{...col, transform: `scale(${pop(t, end, 9)})`}}><div style={{...text(84), maxWidth: 940}}>{p.punchline}</div>
        <div style={{...text(52, BG), background: ACC, borderRadius: 30, padding: "18px 40px", maxWidth: 900}}>{p.cta}</div></div></AbsoluteFill>}
    <Audio src={staticFile(p.voice)} />
    {p.music && <Audio src={staticFile(p.music)} volume={0.12} loop />}
    {p.sfx.map(([at, n]: any, j: number) => <Sequence key={j} from={Math.round(at * FPS)} durationInFrames={30}><Audio src={staticFile(`sfx/${n}.wav`)} volume={0.5} /></Sequence>)}
  </AbsoluteFill>;
};
