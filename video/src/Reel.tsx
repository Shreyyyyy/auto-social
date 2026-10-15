// Teaching reel with two rhythms: real-world moments on full-screen footage, teaching moments on a bright whiteboard
// (big hand-drawn-style diagrams, define card, charts, phone demo, recap). Every reel = this component + props.json
// from reel.py. Colours come from config.json -> props.theme.
import React from "react";
import {AbsoluteFill, Audio, Easing, OffthreadVideo, Sequence, interpolate, spring, staticFile, useCurrentFrame} from "remotion";
import {loadFont} from "@remotion/google-fonts/Poppins";
import {loadFont as loadDeva} from "@remotion/google-fonts/Mukta";
import {loadFont as loadHand} from "@remotion/google-fonts/Kalam";
import {Lottie} from "@remotion/lottie";

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
  <div style={{width: size, height: size, opacity: pop(t, at), transform: `translateY(${bob * Math.sin(t * 2.4 + at)}px) scale(${0.5 + 0.5 * pop(t, at, 10)})`}}>
    <Lottie animationData={data} loop style={{width: size, height: size}} /></div>;

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

// Clean cover for the profile grid: first footage frame + the hook, big, inside the centre safe area.
const Cover: React.FC<any> = (p) => {
  const HI = p.theme?.highlight || "#FFD43B", sh = (p.shots || []).find((x: any) => x.src);
  return <AbsoluteFill style={{background: PAPER}}>
    {sh && <OffthreadVideo src={staticFile(sh.src)} muted startFrom={30} style={{width: "100%", height: "100%", objectFit: "cover"}} />}
    <AbsoluteFill style={{background: "rgba(0,0,0,.35)"}} />
    <AbsoluteFill style={{alignItems: "center", justifyContent: "center", padding: "0 80px"}}>
      <div style={{...font(118, "#fff", 900), WebkitTextStroke: "12px #000", paintOrder: "stroke", lineHeight: 1.05}}>
        {String(p.hook).split(" ").map((w: string, j: number, a: string[]) => <span key={j} style={j === a.length - 1 || /\d/.test(w) ? {color: HI} : {}}>{w}{j < a.length - 1 ? " " : ""}</span>)}
      </div></AbsoluteFill>
  </AbsoluteFill>;
};

export const Reel: React.FC<any> = (p) => {
  if (p.cover) return <Cover {...p} />;
  const t = useCurrentFrame() / FPS, L = p.lines, HI = p.theme?.highlight || "#FFD43B", INK = p.theme?.ink || "#1D1D1F";
  const i = Math.max(0, L.findLastIndex((l: any) => l.start <= t)), line = L[i];
  const ws = line?.words || [], cur = ws.findLastIndex((w: any) => w[1] <= t), c0 = Math.floor(Math.max(cur, 0) / 3) * 3;
  const board = (l: any) => !!l && (BOARD.includes(l.v?.type) || !!l.text_scene);
  const onBoard = board(line), bigWords = !p.captions || (onBoard && !BOARD.includes(line.v?.type) && !STICKER.includes(line.v?.type)), left = Math.max(0, Math.ceil(p.duration - t));
  return <AbsoluteFill style={{background: "#000", overflow: "hidden"}}>
    {/* real-world moments: full-screen footage with a slow push-in */}
    {(p.shots || []).map((sh: any, j: number) => sh.src && <Sequence key={j} from={Math.round(sh.start * FPS)} durationInFrames={Math.max(1, Math.round((sh.end - sh.start) * FPS))}>
      <AbsoluteFill style={{transform: `scale(${1.02 + 0.05 * interpolate(t, [sh.start, sh.end], [0, 1], clamp)})`}}>
        <OffthreadVideo src={staticFile(sh.src)} muted startFrom={Math.round((sh.offset || 0) * FPS)} style={{width: "100%", height: "100%", objectFit: "cover"}} />
      </AbsoluteFill></Sequence>)}
    {!onBoard && <AbsoluteFill style={{background: "linear-gradient(180deg, rgba(0,0,0,.4) 0%, rgba(0,0,0,0) 26%, rgba(0,0,0,0) 55%, rgba(0,0,0,.55) 100%)"}} />}
    {/* teaching moments: a bright whiteboard slides in */}
    {L.map((l: any, j: number) => { if (!(board(l) && t >= l.start - 0.2 && t < (L[j + 1]?.start ?? p.duration))) return null;
      const end = L[j + 1]?.start ?? p.duration, prog = interpolate(t, [l.start, end], [0, 1], clamp), an = (l.anim || []).map((c: string) => p.lottie?.[c]).filter(Boolean);
      const teach = BOARD.includes(l.v?.type), textScene = !teach && !STICKER.includes(l.v?.type);
      return <AbsoluteFill key={j} style={{background: PAPER, backgroundImage: "radial-gradient(#00000014 2px, transparent 2px)", backgroundSize: "44px 44px",
        backgroundPosition: `${t * 14}px ${t * 9}px`,  // the paper itself drifts: nothing on screen is ever frozen
        transform: board(L[j - 1]) ? "none" : `translateX(${(1 - pop(t, l.start - 0.2, 20)) * 1080}px)`}}>
        {/* slow camera push on every board scene */}
        <AbsoluteFill style={{transform: `scale(${1 + 0.045 * prog}) translateY(${-12 * prog}px)`}}>
        {textScene ? <AbsoluteFill style={{top: j === 0 && p.hook ? 560 : 230, height: j === 0 && p.hook ? 860 : 1150, alignItems: "center", justifyContent: "center", gap: 20}}>
            {/* the animated emoji act out the line, the key idea is written underneath */}
            <div style={{display: "flex", gap: 30}}>{an.map((d: any, q: number) => <Anim key={q} data={d} size={an.length > 1 ? 380 : 500} t={t} at={l.start + q * 0.45} />)}</div>
            {!(j === 0 && p.hook) && <div style={{...font(an.length ? 96 : 118, INK, 700, HAND), maxWidth: 920, transform: `scale(${0.7 + 0.3 * pop(t, l.start + 0.2)}) rotate(-1.5deg)`, opacity: pop(t, l.start + 0.2)}}>
              <span style={{backgroundImage: `linear-gradient(${HI}, ${HI})`, backgroundRepeat: "no-repeat", backgroundPosition: "0 88%",
                backgroundSize: `${interpolate(t, [l.start + 0.45, l.start + 1.1], [0, 100], clamp)}% 38%`}}>{l.onscreen || (l.words || []).slice(0, 4).map((w: any) => w[0]).join(" ")}</span></div>}
          </AbsoluteFill>
        : teach ? <>
            <AbsoluteFill style={{top: 250, height: 900, alignItems: "center", justifyContent: "center"}}>
              <Board v={l.v?.type === "brand" ? {...l.v, anim: an[0]} : l.v} t={t} s={l.start} e={l.end} HI={HI} INK={INK} /></AbsoluteFill>
            {l.v?.type !== "brand" && an[0] && <div style={{position: "absolute", top: 1170, width: "100%", display: "flex", justifyContent: "center", gap: 40}}>
              {an.map((d: any, q: number) => <Anim key={q} data={d} size={250} t={t} at={l.start + 0.3 + q * 0.4} />)}</div>}
          </> : null}
        </AbsoluteFill></AbsoluteFill>; })}
    {/* sticker cards over real footage (or over the plain board if no footage matched) */}
    {L.map((l: any, j: number) => STICKER.includes(l.v?.type) && t >= l.start && t < l.end + 0.25 &&
      <AbsoluteFill key={`s${j}`} style={{top: 330, height: 760, alignItems: "center", justifyContent: "center",
        opacity: interpolate(t, [l.end - 0.05, l.end + 0.25], [1, 0], clamp)}}>
        <div style={{background: "rgba(255,253,247,.94)", border: `5px solid ${INK}`, borderRadius: 34, boxShadow: `10px 10px 0 ${INK}`, padding: "30px 26px",
          transform: `scale(${0.82 * (0.85 + 0.15 * pop(t, l.start))})`}}><Board v={l.v} t={t} s={l.start} e={l.end} HI={HI} INK={INK} /></div>
      </AbsoluteFill>)}
    {/* hook headline on line 1 */}
    {i === 0 && p.hook && <div style={{position: "absolute", top: 470, width: "100%", padding: "0 70px", boxSizing: "border-box", ...col}}>
      <div style={{...font(84, onBoard ? INK : "#fff", 900), ...(onBoard ? {} : {WebkitTextStroke: "10px #000", paintOrder: "stroke"}), opacity: pop(t, 0.05),
        transform: `scale(${interpolate(pop(t, 0.05, 12), [0, 1], [1.2, 1])})`}}>
        {String(p.hook).split(" ").map((w: string, j: number, a: string[]) => <span key={j} style={j === a.length - 1 || /\d/.test(w) ? {color: onBoard ? BLUE : HI} : {}}>{w}{j < a.length - 1 ? " " : ""}</span>)}
      </div></div>}
    {/* countdown chip keeps the "samjho in N sec" promise visible (completion) */}
    <div style={{position: "absolute", top: 240, right: 60, ...font(34, INK, 900), background: HI, border: `4px solid ${INK}`, borderRadius: 40, padding: "6px 20px",
      opacity: interpolate(t, [0.3, 0.8], [0, 1], clamp)}}>⏱ {left}s</div>
    {/* source chip whenever a line states a news fact */}
    {line?.source && <div style={{position: "absolute", top: onBoard ? 1180 : 1090, left: 60, ...font(30, INK, 700), background: "rgba(255,255,255,.95)", border: `3px solid ${INK}`, borderRadius: 12, padding: "6px 14px", maxWidth: 760,
      whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", opacity: pop(t, line.start + 0.2)}}>📰 {line.source}</div>}
    {/* captions: on footage = white with black outline; on the whiteboard = ink with a highlighter on the spoken word */}
    {cur >= 0 && !bigWords && <div style={{position: "absolute", top: onBoard ? 1260 : 1170, width: "100%", padding: "0 60px", boxSizing: "border-box", textAlign: "center"}}>
      {ws.slice(c0, c0 + 3).map(([w, wt]: any, j: number) => c0 + j <= cur && <span key={j} style={{...font(onBoard ? 72 : 86, onBoard ? INK : (c0 + j === cur ? HI : "#fff"), 900),
        ...(onBoard ? {background: c0 + j === cur ? HI : "transparent", borderRadius: 12, padding: "0 10px"} : {WebkitTextStroke: "10px #000", paintOrder: "stroke"}),
        display: "inline-block", margin: "0 6px", transform: `scale(${c0 + j === cur ? 0.9 + 0.1 * pop(t, wt, 12) : 1})`}}>{w}</span>)}
    </div>}
    <Audio src={staticFile(p.voice)} />
    {p.music && <Audio src={staticFile(p.music)} volume={0.09} loop />}
    {(p.sfx || []).map(([at, n]: any, j: number) => <Sequence key={j} from={Math.round(at * FPS)} durationInFrames={30}><Audio src={staticFile(`sfx/${n}.wav`)} volume={0.2} /></Sequence>)}
  </AbsoluteFill>;
};
