import { useEffect, useRef } from 'react'
import * as THREE from 'three'

// Ambient radar scanner for the cockpit hero: one full-screen shader quad (rings + a rotating
// sweep + a few contacts), transparent so the hero gradient shows through. Lazy loaded, so
// three.js only ships on the cockpit. Reduced-motion freezes the sweep.
const frag = `
precision highp float;
varying vec2 vUv;
uniform float uTime;
uniform vec2 uRes;
uniform vec2 uMouse;
uniform vec3 uAccent;
uniform vec3 uWarn;
uniform float uReduced;

const float TAU = 6.28318530718;
// three contacts in scanner space (x,y)
const vec2 c0 = vec2(0.18, 0.10);
const vec2 c1 = vec2(-0.22, -0.06);
const vec2 c2 = vec2(0.06, -0.20);

void main() {
  vec2 center = vec2(0.70, 0.52) + uMouse * 0.03;
  vec2 p = vUv - center;
  p.x *= uRes.x / uRes.y;
  float r = length(p) * 1.9;
  float ang = atan(p.y, p.x);

  // concentric rings
  float rings = smoothstep(0.028, 0.0, abs(fract(r * 6.0) - 0.5) - 0.47);
  // radial spokes, faint
  float spokes = smoothstep(0.985, 1.0, abs(cos(ang * 6.0))) * 0.25;
  // rotating sweep with a trailing fade
  float sweepAng = mod(uTime * 0.5, TAU);
  float d = mod(ang - sweepAng + TAU, TAU);
  float sweep = smoothstep(2.4, 0.0, d) * 0.55 * (1.0 - uReduced);

  float fade = smoothstep(1.05, 0.15, r);
  float base = (rings * 0.5 + spokes + sweep) * fade;
  vec3 col = uAccent * base;
  float alpha = base;

  // contacts light up as the sweep passes, pulse gently
  vec2 cs[3];
  cs[0] = c0; cs[1] = c1; cs[2] = c2;
  for (int i = 0; i < 3; i++) {
    float bd = length(p - cs[i]);
    float dot = smoothstep(0.02, 0.0, bd);
    float ring = smoothstep(0.055, 0.045, bd) * 0.4;
    float pulse = 0.55 + 0.45 * sin(uTime * 2.2 + float(i) * 1.7);
    float blip = (dot + ring) * pulse;
    col += uWarn * blip;
    alpha += blip * 0.9;
  }
  gl_FragColor = vec4(col, clamp(alpha, 0.0, 1.0));
}
`
const vert = `varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position, 1.0); }`

const hexToVec3 = (hex: string) => {
  const c = new THREE.Color(hex)
  return new THREE.Vector3(c.r, c.g, c.b)
}

export default function ScannerCanvas() {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches

    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5))
    el.appendChild(renderer.domElement)
    Object.assign(renderer.domElement.style, { width: '100%', height: '100%', display: 'block' })

    const scene = new THREE.Scene()
    const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1)
    const uniforms = {
      uTime: { value: 0 },
      uRes: { value: new THREE.Vector2(1, 1) },
      uMouse: { value: new THREE.Vector2(0, 0) },
      uAccent: { value: hexToVec3('#F26A43') },
      uWarn: { value: hexToVec3('#F79570') },
      uReduced: { value: reduced ? 1 : 0 },
    }
    const mesh = new THREE.Mesh(
      new THREE.PlaneGeometry(2, 2),
      new THREE.ShaderMaterial({ vertexShader: vert, fragmentShader: frag, uniforms, transparent: true, blending: THREE.AdditiveBlending, depthTest: false }),
    )
    scene.add(mesh)

    const resize = () => {
      const w = el.clientWidth, h = el.clientHeight
      renderer.setSize(w, h, false)
      uniforms.uRes.value.set(w, h)
    }
    resize()
    const ro = new ResizeObserver(resize)
    ro.observe(el)

    const target = new THREE.Vector2(0, 0)
    const onMove = (e: PointerEvent) => {
      const r = el.getBoundingClientRect()
      target.set((e.clientX - r.left) / r.width - 0.5, -((e.clientY - r.top) / r.height - 0.5))
    }
    window.addEventListener('pointermove', onMove)

    let raf = 0
    const start = performance.now()
    const loop = () => {
      uniforms.uTime.value = (performance.now() - start) / 1000
      uniforms.uMouse.value.lerp(target, 0.05)
      renderer.render(scene, camera)
      raf = requestAnimationFrame(loop)
    }
    if (reduced) renderer.render(scene, camera)
    else raf = requestAnimationFrame(loop)

    return () => {
      cancelAnimationFrame(raf)
      ro.disconnect()
      window.removeEventListener('pointermove', onMove)
      mesh.geometry.dispose()
      ;(mesh.material as THREE.Material).dispose()
      renderer.dispose()
      el.removeChild(renderer.domElement)
    }
  }, [])

  return <div ref={ref} className="absolute inset-0 h-full w-full" aria-hidden />
}
