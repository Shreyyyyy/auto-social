"use client";
import {useEffect, useRef} from "react";

// The living background: aurora + neon grid floor + a neural network that reacts to the cursor.
// While a job is running the network "thinks" harder: faster drift, more data pulses, hotter colours.
export default function Backdrop() {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const cv = ref.current!, ctx = cv.getContext("2d")!;
    const calm = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let w = 0, h = 0, dpr = 1, raf = 0, busy = 0, energy = 0;
    const mouse = {x: -9999, y: -9999};
    type Node = {x: number; y: number; vx: number; vy: number; r: number; hue: number};
    type Pulse = {a: Node; b: Node; t: number; speed: number; hue: number};
    let nodes: Node[] = [];
    const pulses: Pulse[] = [];
    const HUES = [190, 265, 320];

    const resize = () => {
      dpr = Math.min(window.devicePixelRatio || 1, 2); w = window.innerWidth; h = window.innerHeight;
      cv.width = w * dpr; cv.height = h * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const n = Math.round(Math.min(130, (w * h) / 14000));
      nodes = Array.from({length: n}, () => ({x: Math.random() * w, y: Math.random() * h, vx: (Math.random() - .5) * .35, vy: (Math.random() - .5) * .35,
        r: Math.random() * 1.6 + .6, hue: HUES[Math.floor(Math.random() * 3)]}));
    };
    const LINK = 150;
    const frame = () => {
      energy += ((busy ? 1 : 0) - energy) * .02;  // ease in/out of "thinking" mode
      const speed = 1 + energy * 2.2;
      ctx.clearRect(0, 0, w, h);
      for (const p of nodes) {
        const dx = mouse.x - p.x, dy = mouse.y - p.y, d2 = dx * dx + dy * dy;
        if (d2 < 220 * 220) { const f = .00009 * (1 - Math.sqrt(d2) / 220) * 220; p.vx += dx * f * .01; p.vy += dy * f * .01; }
        p.vx *= .995; p.vy *= .995;
        p.x += p.vx * speed; p.y += p.vy * speed;
        if (p.x < -20) p.x = w + 20; else if (p.x > w + 20) p.x = -20;
        if (p.y < -20) p.y = h + 20; else if (p.y > h + 20) p.y = -20;
      }
      ctx.lineWidth = 1;
      for (let i = 0; i < nodes.length; i++) for (let j = i + 1; j < nodes.length; j++) {
        const a = nodes[i], b = nodes[j], dx = a.x - b.x, dy = a.y - b.y, d2 = dx * dx + dy * dy;
        if (d2 > LINK * LINK) continue;
        const near = Math.max(0, 1 - Math.hypot((a.x + b.x) / 2 - mouse.x, (a.y + b.y) / 2 - mouse.y) / 260);
        const al = (1 - Math.sqrt(d2) / LINK) * (.13 + near * .45 + energy * .12);
        ctx.strokeStyle = `hsla(${a.hue},90%,70%,${al})`;
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
        if (Math.random() < .0004 * (1 + energy * 8) && pulses.length < 60) pulses.push({a, b, t: 0, speed: .012 + Math.random() * .02, hue: HUES[Math.floor(Math.random() * 3)]});
      }
      for (const p of nodes) {
        const g = Math.max(0, 1 - Math.hypot(p.x - mouse.x, p.y - mouse.y) / 200);
        ctx.fillStyle = `hsla(${p.hue},95%,${70 + g * 20}%,${.55 + g * .45})`;
        ctx.beginPath(); ctx.arc(p.x, p.y, p.r + g * 2.2 + energy * .6, 0, 7); ctx.fill();
      }
      ctx.globalCompositeOperation = "lighter";
      for (let k = pulses.length - 1; k >= 0; k--) {
        const q = pulses[k]; q.t += q.speed * speed;
        if (q.t >= 1) { pulses.splice(k, 1); continue; }
        const x = q.a.x + (q.b.x - q.a.x) * q.t, y = q.a.y + (q.b.y - q.a.y) * q.t;
        const gr = ctx.createRadialGradient(x, y, 0, x, y, 14);
        gr.addColorStop(0, `hsla(${q.hue},100%,80%,.95)`); gr.addColorStop(1, `hsla(${q.hue},100%,60%,0)`);
        ctx.fillStyle = gr; ctx.beginPath(); ctx.arc(x, y, 14, 0, 7); ctx.fill();
      }
      ctx.globalCompositeOperation = "source-over";
      raf = requestAnimationFrame(frame);
    };

    resize();
    if (calm) { energy = 0; frame(); cancelAnimationFrame(raf); } else raf = requestAnimationFrame(frame);
    const onMove = (e: PointerEvent) => { mouse.x = e.clientX; mouse.y = e.clientY; };
    const onLeave = () => { mouse.x = mouse.y = -9999; };
    window.addEventListener("resize", resize); window.addEventListener("pointermove", onMove); document.addEventListener("pointerleave", onLeave);
    const poll = async () => {
      try { const j = await (await fetch("/api/jobs/current", {cache: "no-store"})).json(); busy = j?.status === "running" ? 1 : 0; } catch {}
    };
    poll(); const t = setInterval(poll, 4000);
    return () => { cancelAnimationFrame(raf); clearInterval(t); window.removeEventListener("resize", resize);
      window.removeEventListener("pointermove", onMove); document.removeEventListener("pointerleave", onLeave); };
  }, []);

  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <div className="aurora aurora-1" /><div className="aurora aurora-2" /><div className="aurora aurora-3" />
      <div className="grid-floor" />
      <canvas ref={ref} className="absolute inset-0 h-full w-full" />
      <div className="scanline" />
      <div className="noise" />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_40%,rgba(5,4,11,.85))]" />
    </div>
  );
}
