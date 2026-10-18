// Two looks, picked per reel by props.style: AI Case File (explainers) and Story (every other genre).
// Every reel = this component + props.json from reel.py.
// Colours come from config.json -> props.theme. The card renderers (Board) are shared by every clue type.
import React from "react";
import {AbsoluteFill, Audio, Easing, Img, OffthreadVideo, Sequence, interpolate, spring, staticFile, useCurrentFrame} from "remotion";
import {loadFont} from "@remotion/google-fonts/Poppins";
import {loadFont as loadDeva} from "@remotion/google-fonts/Mukta";
import {loadFont as loadHand} from "@remotion/google-fonts/Kalam";
import {Lottie} from "@remotion/lottie";
import {loadFont as loadType} from "@remotion/google-fonts/SpecialElite";

const FONT = `${loadFont("normal", {weights: ["700", "800", "900"]}).fontFamily}, ${loadDeva("normal", {weights: ["800"]}).fontFamily}, sans-serif`;
const HAND = `${loadHand("normal", {weights: ["700"]}).fontFamily}, ${FONT}`;
const FPS = 30, PAPER = "#FBF6EC", BLUE = "#3D6CF0", CORAL = "#FF6B5B", GREEN = "#1FA971";
const pop = (t: number, at: number, damping = 13) => (t < at ? 0 : spring({frame: (t - at) * FPS, fps: FPS, config: {damping, stiffness: 190}}));
const clamp = {extrapolateLeft: "clamp", extrapolateRight: "clamp"} as const;
const font = (size: number, color: string, weight = 800, family = FONT): React.CSSProperties => ({fontFamily: family, fontWeight: weight, fontSize: size, color, lineHeight: 1.12, textAlign: "center"});
const col: React.CSSProperties = {display: "flex", flexDirection: "column", alignItems: "center"};
const BOARD = ["define", "diagram", "flow", "chart", "chat", "recap", "brand"];          // full whiteboard scenes
const STICKER = ["counter", "compare", "stamp", "list", "quote"];                 // float over real footage

// A "sticker" box: ink outline + offset shadow, like a teacher's marker drawing.
const box = (INK: string, bg = "#fff", extra: React.CSSProperties = {}): React.CSSProperties =>
  ({background: bg, border: `5px solid ${INK}`, borderRadius: 26, boxShadow: `8px 8px 0 ${INK}`, padding: "22px 30px", boxSizing: "border-box", ...extra});

// Google Noto Animated Emoji (Lottie): real, professionally animated characters/objects - they never stand still.
const Anim: React.FC<{data: any; size: number; t: number; at: number; bob?: number}> = ({data, size, t, at, bob = 12}) => !data ? null :
  <div style={{width: size, height: size, opacity: pop(t, at), transform: `translateY(${bob * Math.sin(t * 2.4 + at) + (1 - pop(t, at, 7)) * 160}px) scale(${0.3 + 0.7 * pop(t, at, 7)}) rotate(${(1 - pop(t, at, 8)) * -25}deg)`}}>
    <Lottie animationData={data} loop style={{width: size, height: size}} /></div>;

const PALETTE = ["#FBF6EC", "#E8F7EE", "#E9F1FF", "#FFEFE3", "#F2EBFF"];  // a fresh background colour every scene
const REVEAL = ["define", "stamp", "counter", "compare", "chart", "recap", "brand"];

const Board: React.FC<{v: any; t: number; s: number; e: number; HI: string; INK: string}> = ({v, t, s, e, HI, INK}) => {
  const k = pop(t, s), at = (i: number) => v.times?.[i] ?? s, n = (v.items || []).length;
  const swipe = (from: number, to: number) => ({backgroundImage: `linear-gradient(${HI}, ${HI})`, backgroundRepeat: "no-repeat",
    backgroundSize: `${interpolate(t, [from, to], [0, 100], clamp)}% 40%`, backgroundPosition: "0 88%"});
  const title = v.title && !["define", "recap", "quote", "stamp", "brand"].includes(v.type)
    ? <div style={{...font(64, INK, 700, HAND), marginBottom: 34, transform: `scale(${k})`}}><span style={swipe(s + 0.15, s + 0.7)}>{v.title}</span></div> : null;
  const arrowDown = (i: number) => <svg width={60} height={70} style={{margin: "6px 0"}}>
    <line x1={30} y1={4} x2={30} y2={4 + 46 * interpolate(t, [at(i) - 0.3, at(i)], [0, 1], clamp)} stroke={INK} strokeWidth={8} strokeLinecap="round" />
    <polygon points="14,50 46,50 30,68" fill={INK} opacity={pop(t, at(i))} /></svg>;
  let body: React.ReactNode = null;
  if (v.type === "define") {
    const m = String(v.items?.[0] || ""), shown = Math.round(m.length * interpolate(t, [at(0), at(0) + 1.1], [0, 1], clamp));
    body = <div style={{...col, gap: 26}}>
      <div style={{...box(INK, HI), ...font(96, INK, 900), transform: `scale(${k}) rotate(-2deg)`}}>{v.title}</div>
      <div style={{...font(46, "#777", 700, HAND), opacity: pop(t, s + 0.3)}}>matlab...</div>
      <div style={{...font(70, INK, 800), maxWidth: 900, minHeight: 170}}>{m.slice(0, shown)}<span style={{opacity: shown < m.length ? 1 : 0, color: BLUE}}>|</span></div></div>;
  } else if (v.type === "diagram" || v.type === "flow") {
    const colors = [BLUE, CORAL, GREEN, HI];
    body = <div style={col}>{(v.items || []).map((it: string, i: number) => <React.Fragment key={i}>
      {i > 0 && arrowDown(i)}
      <div style={{...box(INK, i === n - 1 ? HI : "#fff", {width: 820, padding: "20px 28px", borderLeft: `22px solid ${colors[i % 4]}`}), ...font(n > 3 ? 54 : 62, INK, 800),
        opacity: pop(t, at(i)), transform: `scale(${0.6 + 0.4 * pop(t, at(i))}) rotate(${i % 2 ? 1 : -1}deg)`}}>{it}</div>
    </React.Fragment>)}</div>;
  } else if (v.type === "chart") {
    // a real chart drawn on screen: bars grow / the line draws point to point, values pop in
    const vals: number[] = v.values || [], max = Math.max(...vals, 1), W = 900, H = 620, m = vals.length;
    const x = (i: number) => 90 + (i * (W - 180)) / Math.max(m - 1, 1), y = (val: number) => H - 80 - (val / max) * (H - 190);
    const g = (i: number) => Easing.out(Easing.cubic)(interpolate(t, [at(i) - 0.15, at(i) + 0.4], [0, 1], clamp));
    const pts = vals.map((val, i) => i === 0 ? (g(0) > 0 ? `${x(0)},${y(val)}` : "")
      : g(i) > 0 ? `${x(i - 1) + (x(i) - x(i - 1)) * g(i)},${y(vals[i - 1] + (val - vals[i - 1]) * g(i))}` : "").filter(Boolean).join(" ");
    body = <svg width={W} height={H}>
      <line x1={40} y1={H - 80} x2={W - 20} y2={H - 80} stroke={INK} strokeWidth={6} strokeLinecap="round" />
      <line x1={40} y1={40} x2={40} y2={H - 80} stroke={INK} strokeWidth={6} strokeLinecap="round" />
      {v.chart === "line" ? <>
        <polyline fill="none" stroke={BLUE} strokeWidth={12} strokeLinejoin="round" strokeLinecap="round" points={pts} />
        {vals.map((val, i) => <circle key={i} cx={x(i)} cy={y(val)} r={18 * pop(t, at(i))} fill={i === m - 1 ? HI : "#fff"} stroke={INK} strokeWidth={6} />)}
      </> : vals.map((val, i) => { const bw = Math.min(150, (W - 200) / m - 24), h = (H - 190) * (val / max) * g(i);
        return <rect key={i} x={x(i) - bw / 2} y={H - 80 - h} width={bw} height={h} rx={14} fill={i === m - 1 ? HI : [BLUE, CORAL, GREEN][i % 3]} stroke={INK} strokeWidth={5} />; })}
      {vals.map((val, i) => <React.Fragment key={i}>
        <text x={x(i)} y={y(val) - 34} textAnchor="middle" style={{fontFamily: FONT, fontWeight: 900, fontSize: 44}} fill={INK} opacity={pop(t, at(i) + 0.25)}>{val.toLocaleString("en-IN")}{v.suffix}</text>
        <text x={x(i)} y={H - 26} textAnchor="middle" style={{fontFamily: HAND, fontWeight: 700, fontSize: 42}} fill={INK} opacity={pop(t, at(i))}>{v.items?.[i]}</text>
      </React.Fragment>)}
    </svg>;
  } else if (v.type === "counter") {
    const num = (v.number || 0) * Easing.out(Easing.cubic)(interpolate(t, [s, s + (e - s) * 0.6], [0, 1], clamp));
    body = <div style={{...box(INK, HI), ...font(170, INK, 900), transform: `scale(${k}) rotate(-2deg)`}}>{num.toLocaleString("en-IN", {maximumFractionDigits: num < 10 ? 1 : 0})}{v.suffix}</div>;
  } else if (v.type === "compare") {
    body = <div style={{...col, gap: 18}}>{[0, 1].map((i) => <React.Fragment key={i}>
      {i === 1 && <div style={{...font(64, "#fff", 900), background: CORAL, borderRadius: 50, padding: "6px 30px", transform: `scale(${pop(t, at(1), 9)}) rotate(-4deg)`}}>VS</div>}
      <div style={{...box(INK, i ? "#EAF0FF" : "#FFF1E6", {width: 860, minHeight: 210, display: "flex", alignItems: "center", justifyContent: "center"}), ...font(64, INK, 800),
        opacity: pop(t, at(i)), transform: `translateX(${(1 - pop(t, at(i))) * (i ? 400 : -400)}px)`}}>{v.items?.[i]}</div>
    </React.Fragment>)}</div>;
  } else if (v.type === "stamp") {
    const p = pop(t, at(0), 10), good = v.good !== false;
    body = <div style={{...col, gap: 30}}>
      <div style={{...font(72, INK, 800), maxWidth: 900, opacity: pop(t, s)}}>{v.title}</div>
      <div style={{...font(120, good ? GREEN : CORAL, 900), border: `12px solid ${good ? GREEN : CORAL}`, borderRadius: 30, padding: "6px 40px",
        opacity: p, transform: `scale(${interpolate(p, [0, 1], [2.2, 1])}) rotate(-8deg)`}}>{good ? "✅ SACH" : "❌ MYTH"}</div></div>;
  } else if (v.type === "list") {
    body = <div style={{...col, gap: 22, alignItems: "stretch"}}>{(v.items || []).map((it: string, i: number) =>
      <div key={i} style={{...box(INK, "#fff", {width: 860}), ...font(58, INK, 800), textAlign: "left", opacity: pop(t, at(i)),
        transform: `translateX(${(1 - pop(t, at(i))) * -300}px)`}}><span style={{color: GREEN}}>✔</span> {it}</div>)}</div>;
  } else if (v.type === "chat") {
    // phone demo: the question types itself, then the answer appears - show, don't tell
    const q = String(v.items?.[0] || ""), a = String(v.items?.[1] || ""), at1 = at(1);
    const qs = Math.round(q.length * interpolate(t, [s + 0.2, s + 1.2], [0, 1], clamp)), as = Math.round(a.length * interpolate(t, [at1, at1 + 1.4], [0, 1], clamp));
    body = <div style={{width: 760, height: 860, background: "#fff", border: `14px solid ${INK}`, borderRadius: 70, padding: "60px 34px", boxSizing: "border-box", boxShadow: `14px 14px 0 ${INK}`,
      display: "flex", flexDirection: "column", gap: 26, transform: `translateY(${(1 - k) * 300}px)`}}>
      <div style={font(34, "#888", 700)}>{v.title || "AI Chat"}</div>
      <div style={{alignSelf: "flex-end", maxWidth: 560, background: BLUE, borderRadius: "34px 34px 6px 34px", padding: "20px 26px", ...font(40, "#fff", 700), textAlign: "left"}}>{q.slice(0, qs) || "…"}</div>
      {t > at1 - 0.5 && <div style={{alignSelf: "flex-start", maxWidth: 600, background: "#F0F0F3", borderRadius: "34px 34px 34px 6px", padding: "20px 26px", ...font(40, INK, 700), textAlign: "left"}}>
        {t < at1 ? "• • •" : a.slice(0, as)}</div>}
    </div>;
  } else if (v.type === "brand") {
    // the channel's signature sting: same every reel, so viewers recognise it
    const steam = (o: number) => <div style={{position: "absolute", top: -70 - 20 * Math.sin(t * 3 + o), left: 70 + o * 40, width: 14, height: 60, borderRadius: 10,
      background: "#00000022", transform: `scaleY(${0.8 + 0.3 * Math.sin(t * 4 + o)})`}} />;
    body = <div style={{...col, gap: 26}}>
      {v.anim ? <Anim data={v.anim} size={300} t={t} at={s} bob={8} />
        : <div style={{position: "relative", fontSize: 200, transform: `scale(${pop(t, s, 9)}) rotate(${6 * Math.sin(t * 2)}deg)`}}>{steam(0)}{steam(1)}{steam(2)}{v.suffix || "☕"}</div>}
      <div style={{...font(96, INK, 700, HAND), transform: `scale(${pop(t, s + 0.15)})`}}><span style={swipe(s + 0.3, s + 0.9)}>{v.title}</span></div>
      <div style={{...font(44, "#fff", 800), background: INK, borderRadius: 40, padding: "10px 28px", opacity: pop(t, at(0)), transform: `translateY(${(1 - pop(t, at(0))) * 40}px)`}}>{v.items?.[0]}</div>
    </div>;
  } else if (v.type === "recap" || v.type === "quote") {
    body = <div style={{...col, gap: 30}}>
      {v.type === "recap" && <div style={{...font(54, "#fff", 900), background: INK, borderRadius: 18, padding: "10px 30px", transform: `scale(${k}) rotate(-3deg)`}}>📌 YAAD RAKHO</div>}
      <div style={{...box(INK, "#fff", {maxWidth: 940}), ...font(76, INK, 900), transform: `scale(${interpolate(pop(t, at(0)), [0, 1], [0.6, 1])})`}}>
        <span style={swipe(at(0) + 0.2, at(0) + 1)}>{v.title}</span></div></div>;
  } else return null;
  return <div style={col}>{title}{body}</div>;
};

// ======================= AI CASE FILE =======================
// Every reel is a mystery case on a detective's corkboard: each line pins a new clue (footage polaroid, evidence card,
// sticky note with animated characters), a red string runs from the last clue, the camera glides to it; the verdict is
// stamped CASE SOLVED and the camera pulls back to show the whole solved board.
const TYPE = `${loadType("normal", {weights: ["400"]}).fontFamily}, monospace`;
const CORK = "#B48655", BW = 1500, STEP = 760;
const slot = (k: number) => ({x: k % 2 === 0 ? 480 : 1020, y: 640 + k * STEP});   // zig-zag down the board
const pinAt = (k: number) => ({x: slot(k).x + (k % 2 ? -60 : 60), y: slot(k).y - 400});
const ease = (x: number) => Easing.inOut(Easing.cubic)(Math.max(0, Math.min(1, x)));
const rot = (k: number) => [-3, 2.5, -1.5, 3, -2.5, 1.5][k % 6];

const Pin: React.FC<{x: number; y: number; t: number; at: number}> = ({x, y, t, at}) =>
  <div style={{position: "absolute", left: x - 26, top: y - 26, width: 52, height: 52, borderRadius: "50%", zIndex: 6,
    background: "radial-gradient(circle at 35% 30%, #ffffffcc 0 16%, #E8352B 22%, #7A1410 100%)", boxShadow: "5px 8px 8px #0007",
    transform: `scale(${pop(t, at, 9)})`}} />;

const Clue: React.FC<{l: any; k: number; t: number; p: any; HI: string; INK: string; next: number}> = ({l, k, t, p, HI, INK, next}) => {
  const s = l.start, live = t >= s - 0.1 && t < next + 0.2, drop = pop(t, s - 0.1, 12), {x, y} = slot(k);
  const an = (l.anim || []).map((c: string) => p.lottie?.[c]).filter(Boolean), type = l.v?.type;
  const wrap = (w: number, body: React.ReactNode, bg = "#FFFDF4") =>
    <div style={{position: "absolute", left: x - w / 2, top: y - 420, width: w, background: bg, padding: 26, boxSizing: "border-box",
      boxShadow: "14px 18px 28px #0008", transform: `translateY(${(1 - drop) * -260}px) rotate(${rot(k) + (1 - drop) * 12}deg) scale(${0.7 + 0.3 * drop})`,
      opacity: Math.min(1, drop * 2)}}>{body}</div>;
  const label = (txt: string) => <div style={{fontFamily: TYPE, fontSize: 30, color: "#8B1A12", letterSpacing: 2, marginBottom: 14}}>{txt}</div>;
  if (type === "brand")  // the case folder opens
    return wrap(820, <div style={{...col, gap: 10}}>
      <div style={{fontFamily: TYPE, fontSize: 40, color: "#5B3A12"}}>CONFIDENTIAL · CASE FILE #{String(p.case_no || 1).padStart(2, "0")}</div>
      {an[0] && <Anim data={an[0]} size={260} t={t} at={s} bob={6} />}
      <div style={{...font(78, INK, 700, HAND)}}>{l.v.title}</div>
      <div style={{fontFamily: TYPE, fontSize: 32, color: "#5B3A12"}}>{l.v.items?.[0]}</div></div>, "#E9C77B");
  if (type === "recap")  // the verdict
    return wrap(900, <div style={{...col, gap: 18, position: "relative"}}>
      {label("VERDICT")}
      <div style={{...font(70, INK, 900)}}>{l.v.title}</div>
      <div style={{position: "absolute", top: -120, right: -80, fontFamily: TYPE, fontSize: 64, background: "#FFFDF4dd", color: "#C8231B", border: "8px solid #C8231B",
        padding: "4px 22px", transform: `rotate(-14deg) scale(${interpolate(pop(t, s + 0.6, 9), [0, 1], [2.4, 1])})`, opacity: pop(t, s + 0.6)}}>CASE SOLVED</div>
      {an.length > 0 && <div style={{display: "flex", gap: 20}}>{an.map((d: any, q: number) => <Anim key={q} data={d} size={180} t={t} at={s + 0.9 + q * 0.3} />)}</div>}
    </div>);
  if (l.clip)  // real footage as a polaroid (plays while it is the current clue, a still afterwards)
    return wrap(820, <>
      <div style={{width: 768, height: 860, overflow: "hidden", background: "#111"}}>
        {live ? <Sequence from={Math.round(s * FPS)} durationInFrames={Math.max(1, Math.round((next - s + 0.4) * FPS))} layout="none">
            <OffthreadVideo src={staticFile(l.clip)} muted style={{width: "100%", height: "100%", objectFit: "cover"}} /></Sequence>
          : <Img src={staticFile(l.still || l.clip.replace(".mp4", ".jpg"))} style={{width: "100%", height: "100%", objectFit: "cover"}} />}
      </div>
      <div style={{...font(54, INK, 700, HAND), marginTop: 18, minHeight: 64}}>{l.onscreen}</div>
      {STICKER.includes(type) && <div style={{position: "absolute", right: -60, bottom: 120, transform: "scale(0.62) rotate(4deg)", transformOrigin: "bottom right",
        background: "#FFFDF4", padding: 24, boxShadow: "10px 12px 20px #0007"}}><Board v={l.v} t={t} s={s} e={l.end} HI={HI} INK={INK} /></div>}
    </>, "#fff");
  if (BOARD.includes(type) || STICKER.includes(type))  // an evidence card
    return wrap(940, <div style={{...col}}>{label(`EVIDENCE #${k}`)}<div style={{transform: "scale(0.86)"}}><Board v={l.v} t={t} s={s} e={l.end} HI={HI} INK={INK} /></div>
      {an[0] && <div style={{position: "absolute", right: -70, bottom: -70}}><Anim data={an[0]} size={190} t={t} at={s + 0.5} /></div>}</div>);
  // a sticky note: the key idea + the animated characters acting it out
  return wrap(820, <div style={{...col, gap: 14}}>
    <div style={{display: "flex", gap: 24}}>{an.map((d: any, q: number) => <Anim key={q} data={d} size={an.length > 1 ? 300 : 380} t={t} at={s + 0.2 + q * 0.4} />)}</div>
    <div style={{...font(78, INK, 700, HAND)}}><span style={{backgroundImage: `linear-gradient(${HI}, ${HI})`, backgroundRepeat: "no-repeat", backgroundPosition: "0 88%",
      backgroundSize: `${interpolate(t, [s + 0.5, s + 1.1], [0, 100], clamp)}% 36%`}}>{l.onscreen}</span></div></div>, "#FFE873");
};

// Clean cover for the profile grid: the case question on the corkboard, inside the centre safe area.
const Cover: React.FC<any> = (p) => {
  const first = (p.lines || []).find((l: any) => l.still);
  if (p.style === "story") return <AbsoluteFill style={{background: "#111", alignItems: "center", justifyContent: "center"}}>
    {first && <Img src={staticFile(first.still)} style={{position: "absolute", width: "100%", height: "100%", objectFit: "cover"}} />}
    <AbsoluteFill style={{background: "linear-gradient(#0000 25%, #000c)"}} />
    <div style={{...font(118, "#fff", 900), WebkitTextStroke: "14px #000", paintOrder: "stroke", padding: "0 70px", lineHeight: 1.05}}>{p.hook}</div>
  </AbsoluteFill>;
  return <AbsoluteFill style={{background: CORK, backgroundImage: "radial-gradient(#00000022 2px, transparent 3px), radial-gradient(#ffffff18 1px, transparent 2px)",
    backgroundSize: "18px 18px, 11px 11px", alignItems: "center", justifyContent: "center"}}>
    {first && <Img src={staticFile(first.still)} style={{position: "absolute", width: 760, height: 900, objectFit: "cover", border: "26px solid #fff", borderBottomWidth: 110,
      transform: "rotate(-4deg)", boxShadow: "18px 24px 40px #0009", opacity: 0.9}} />}
    <div style={{position: "absolute", top: 330, fontFamily: TYPE, fontSize: 52, color: "#fff", background: "#8B1A12", padding: "8px 26px", transform: "rotate(-3deg)"}}>
      CASE FILE #{String(p.case_no || 1).padStart(2, "0")}</div>
    <div style={{...font(112, "#fff", 900), WebkitTextStroke: "12px #000", paintOrder: "stroke", padding: "0 70px", lineHeight: 1.05, zIndex: 2}}>{p.hook}</div>
  </AbsoluteFill>;
};

// ======================= STORY =======================
// Any other genre: full-screen real footage with a punch-in on every cut, bold word-by-word captions, proof cards popping
// over the footage, whiteboard scenes for diagrams/charts, and a progress bar.
const Captions: React.FC<{words: [string, number][]; t: number; HI: string}> = ({words, t, HI}) => {
  const k = (words || []).findLastIndex(([, at]) => at <= t);
  if (k < 0) return null;
  const c = Math.floor(k / 3) * 3, chunk = words.slice(c, c + 3);
  return <div style={{position: "absolute", top: 1230, left: 50, right: 50, display: "flex", flexWrap: "wrap", justifyContent: "center",
    transform: `scale(${0.82 + 0.18 * pop(t, chunk[0][1], 10)})`}}>
    {chunk.map(([w], q) => <span key={q} style={{...font(94, c + q === k ? HI : "#fff", 900), WebkitTextStroke: "14px #000", paintOrder: "stroke",
      textTransform: "uppercase", display: "inline-block", margin: "0 20px", transform: c + q === k ? "scale(1.1) rotate(-2deg)" : "none"}}>{w}</span>)}</div>;
};

const Sound: React.FC<any> = (p) => <>
  <Audio src={staticFile(p.voice)} />
  {p.music && <Audio src={staticFile(p.music)} volume={0.1} loop />}
  {(p.sfx || []).map(([at, n_]: any, j: number) => <Sequence key={j} from={Math.round(at * FPS)} durationInFrames={30}><Audio src={staticFile(`sfx/${n_}.wav`)} volume={0.22} /></Sequence>)}
</>;

const Story: React.FC<any> = (p) => {
  const t = useCurrentFrame() / FPS, L = p.lines, HI = p.theme?.highlight || "#FFD43B", INK = p.theme?.ink || "#1D1D1F";
  const i = Math.max(0, L.findLastIndex((l: any) => l.start <= t)), line = L[i], type = line?.v?.type, board = BOARD.includes(type);
  const an = (line.anim || []).map((c: string) => p.lottie?.[c]).filter(Boolean), punch = 1 - pop(t, line.start, 14);
  return <AbsoluteFill style={{background: "#000", overflow: "hidden"}}>
    {(p.shots || []).map((s: any, k: number) => s.src && <Sequence key={k} from={Math.round(s.start * FPS)} durationInFrames={Math.max(1, Math.round((s.end - s.start) * FPS))}>
      <AbsoluteFill style={{transform: `scale(${1.04 + 0.06 * Math.min(1, (t - s.start) / Math.max(s.end - s.start, 0.1)) + 0.14 * (1 - pop(t, s.start, 14))})`}}>
        <OffthreadVideo src={staticFile(s.src)} trimBefore={Math.round((s.offset || 0) * FPS)} muted style={{width: "100%", height: "100%", objectFit: "cover"}} />
      </AbsoluteFill></Sequence>)}
    {!line.clip && <AbsoluteFill style={{background: board ? PALETTE[i % PALETTE.length] : `radial-gradient(circle at 50% 38%, ${HI}, #FF8A3D)`,
      ...col, justifyContent: "center", transform: `scale(${1 + 0.08 * punch})`}}>
      {board ? <div style={{marginTop: -280}}><Board v={line.v} t={t} s={line.start} e={line.end} HI={HI} INK={INK} /></div>
        : <><div style={{display: "flex", gap: 24, marginTop: -240}}>{an.map((d: any, q: number) => <Anim key={q} data={d} size={an.length > 1 ? 300 : 380} t={t} at={line.start + 0.2 + q * 0.4} />)}</div>
          <div style={{...font(108, INK, 900), padding: "0 70px", marginTop: 30, transform: `scale(${pop(t, line.start + 0.1)})`}}>{line.onscreen}</div></>}
    </AbsoluteFill>}
    {line.clip && <AbsoluteFill style={{background: "linear-gradient(#0006 0%, #0000 22%, #0000 52%, #000b 100%)"}} />}
    {line.clip && STICKER.includes(type) && <div style={{position: "absolute", top: 360, left: 0, right: 0, ...col}}>
      <div style={{background: "#FFFDF4", padding: 30, borderRadius: 34, boxShadow: "0 24px 50px #0009", transform: `scale(${0.82 * pop(t, line.start + 0.15)}) rotate(-1.5deg)`}}>
        <Board v={line.v} t={t} s={line.start} e={line.end} HI={HI} INK={INK} /></div></div>}
    {line.clip && an[0] && <div style={{position: "absolute", right: 40, top: 930}}><Anim data={an[0]} size={230} t={t} at={line.start + 0.3} /></div>}
    {i === 0 && p.hook && <div style={{position: "absolute", top: 300, left: 0, right: 0, ...col}}>
      <div style={{...font(96, INK, 900), background: HI, padding: "16px 34px", borderRadius: 24, maxWidth: 940, boxShadow: `10px 10px 0 ${INK}`,
        transform: `scale(${pop(t, 0.1, 9)}) rotate(-2deg)`}}>{p.hook}</div></div>}
    <Captions words={line.words} t={t} HI={HI} />
    {line?.source && <div style={{position: "absolute", bottom: 380, left: 60, ...font(28, "#fff", 700), background: "#000a", borderRadius: 14, padding: "6px 16px",
      opacity: pop(t, line.start + 0.3)}}>📰 {line.source}</div>}
    <div style={{position: "absolute", top: 0, left: 0, height: 12, width: `${(100 * t) / p.duration}%`, background: HI}} />
    {t - line.start < 0.12 && i > 0 && <AbsoluteFill style={{background: "#fff", opacity: 0.25 * (1 - (t - line.start) / 0.12)}} />}
    <Sound {...p} />
  </AbsoluteFill>;
};

export const Reel: React.FC<any> = (p) => {
  if (p.cover) return <Cover {...p} />;
  if (p.style === "story") return <Story {...p} />;
  const t = useCurrentFrame() / FPS, L = p.lines, n = L.length, HI = p.theme?.highlight || "#FFD43B", INK = p.theme?.ink || "#1D1D1F";
  const i = Math.max(0, L.findLastIndex((l: any) => l.start <= t)), line = L[i];
  const nextOf = (k: number) => L[k + 1]?.start ?? p.duration, left = Math.max(0, Math.ceil(p.duration - t));
  // camera: glide from the previous clue to the current one, a little drift, then pull back to the whole board at the end
  const g = ease((t - line.start) / 0.9), a = slot(Math.max(0, i - 1)), b = slot(i);
  let cx = a.x + (b.x - a.x) * (i ? g : 1), cy = a.y + (b.y - a.y) * (i ? g : 1) - 40, sc = 1.04 + 0.03 * Math.sin(t * 0.6);
  // finale: pull back to show the last few clues connected by their strings (the "solved" board)
  const H = slot(n - 1).y + 700, out = ease((t - (p.duration - 2.2)) / 1.2), endY = (slot(Math.max(0, n - 4)).y + slot(n - 1).y) / 2;
  cx = cx + (BW / 2 - cx) * out; cy = cy + (endY - cy) * out; sc = sc + (0.42 - sc) * out;
  const since = t - line.start, shake = since < 0.3 ? 7 * Math.sin(t * 85) * (1 - since / 0.3) : 0;
  const reveal = REVEAL.includes(line?.v?.type) ? (line.v.times?.[0] ?? line.start) : -9, sinceReveal = t - reveal;
  return <AbsoluteFill style={{background: "#2A1B10", overflow: "hidden"}}>
    <AbsoluteFill style={{transform: `translate(${540 - cx * sc + shake}px, ${960 - cy * sc + shake * 0.6}px) scale(${sc})`, transformOrigin: "0 0"}}>
      {/* the corkboard */}
      <div style={{position: "absolute", left: -400, top: -600, width: BW + 800, height: H + 1400, background: CORK,
        backgroundImage: "radial-gradient(#00000026 2px, transparent 3px), radial-gradient(#ffffff1c 1px, transparent 2px)", backgroundSize: "18px 18px, 11px 11px",
        boxShadow: "inset 0 0 220px #000a"}} />
      {/* red strings, drawn as each new clue is pinned */}
      <svg style={{position: "absolute", left: 0, top: 0, overflow: "visible"}} width={BW} height={H}>
        {L.map((l: any, k: number) => { if (k === 0 || t < l.start) return null;
          const p0 = pinAt(k - 1), p1 = pinAt(k), mx = (p0.x + p1.x) / 2, my = (p0.y + p1.y) / 2 + 90, len = Math.hypot(p1.x - p0.x, p1.y - p0.y) + 120;
          const d = interpolate(t, [l.start, l.start + 0.7], [len, 0], clamp);
          return <path key={k} d={`M ${p0.x} ${p0.y} Q ${mx} ${my} ${p1.x} ${p1.y}`} fill="none" stroke="#C8231B" strokeWidth={9} strokeLinecap="round"
            strokeDasharray={len} strokeDashoffset={d} style={{filter: "drop-shadow(4px 6px 3px #0006)"}} />; })}
      </svg>
      {L.map((l: any, k: number) => t >= l.start - 0.1 && <React.Fragment key={k}>
        <Clue l={l} k={k} t={t} p={p} HI={HI} INK={INK} next={nextOf(k)} />
        <Pin x={pinAt(k).x} y={pinAt(k).y} t={t} at={l.start + 0.15} /></React.Fragment>)}
    </AbsoluteFill>
    {/* the case question, typed out while the hook is spoken */}
    {i <= 1 && p.hook && <div style={{position: "absolute", top: 1430, left: 70, right: 70, background: "#FFFDF4", padding: "22px 30px", boxShadow: "10px 14px 24px #0009",
      transform: `rotate(-1.5deg) translateY(${(1 - pop(t, 0.1)) * 400}px)`, opacity: i === 1 ? interpolate(t, [L[1].start, L[1].start + 0.4], [1, 0], clamp) : 1}}>
      <div style={{fontFamily: TYPE, fontSize: 30, color: "#8B1A12"}}>THE CASE:</div>
      <div style={{fontFamily: TYPE, fontSize: 50, color: INK}}>{String(p.hook).slice(0, Math.round(String(p.hook).length * interpolate(t, [0.2, 1.6], [0, 1], clamp)))}</div></div>}
    {/* HUD: case tab + countdown */}
    <div style={{position: "absolute", top: 230, left: 50, fontFamily: TYPE, fontSize: 34, color: "#fff", background: "#8B1A12", padding: "8px 20px", boxShadow: "6px 8px 0 #0006"}}>
      📁 CASE #{String(p.case_no || 1).padStart(2, "0")}{p.case_title ? ` · ${p.case_title}` : ""}</div>
    <div style={{position: "absolute", top: 230, right: 50, fontFamily: TYPE, fontSize: 36, color: left <= 5 ? "#fff" : INK, background: left <= 5 ? "#C8231B" : "#FFFDF4",
      padding: "6px 18px", scale: left <= 5 ? `${1 + 0.12 * Math.abs(Math.sin(t * 6))}` : "1"}}>⏱ {left}s</div>
    {line?.source && <div style={{position: "absolute", bottom: 470, left: 60, fontFamily: TYPE, fontSize: 28, color: INK, background: "#FFFDF4", padding: "6px 14px", maxWidth: 760,
      whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", opacity: pop(t, line.start + 0.3), boxShadow: "6px 8px 0 #0005"}}>📰 {line.source}</div>}
    {/* reveal: flash + animated sparkles */}
    {sinceReveal >= 0 && sinceReveal < 0.15 && <AbsoluteFill style={{background: "#fff", opacity: 0.3 * (1 - sinceReveal / 0.15)}} />}
    {sinceReveal >= 0 && sinceReveal < 1.4 && p.lottie?.["2728"] && [[90, 560], [800, 500], [140, 1150], [810, 1080]].map(([x, y], q) =>
      <div key={q} style={{position: "absolute", left: x, top: y, opacity: interpolate(sinceReveal, [0, 0.2, 1.1, 1.4], [0, 1, 1, 0], clamp)}}>
        <Lottie animationData={p.lottie["2728"]} loop style={{width: 150, height: 150}} /></div>)}
    <Sound {...p} />
  </AbsoluteFill>;
};
