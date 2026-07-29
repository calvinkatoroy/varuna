import { useEffect, useRef } from 'react'
import * as THREE from 'three'

// Full-viewport animated dark gradient with drifting noise + mouse parallax. Sits behind the
// app as an ambient backdrop for dark mode. One shader quad; reduced-motion freezes it.
const frag = `
precision highp float;
varying vec2 vUv;
uniform float uTime;
uniform vec2 uMouse;
uniform vec3 uC0;
uniform vec3 uC1;
uniform vec3 uAccent;

float hash(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise(vec2 p){
  vec2 i = floor(p), f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash(i), hash(i + vec2(1,0)), f.x),
             mix(hash(i + vec2(0,1)), hash(i + vec2(1,1)), f.x), f.y);
}
float fbm(vec2 p){
  float v = 0.0, a = 0.5;
  for (int i = 0; i < 4; i++) { v += a * noise(p); p *= 2.0; a *= 0.5; }
  return v;
}

void main(){
  vec2 uv = vUv;
  vec2 q = uv * 1.6 + uMouse * 0.12;
  float n = fbm(q + uTime * 0.025);
  vec3 c = mix(uC0, uC1, clamp(uv.y * 0.5 + n * 0.5, 0.0, 1.0));
  // a slow coral bloom drifting across the top-right
  vec2 gp = vec2(0.72 + 0.12 * sin(uTime * 0.08), 0.18 + 0.06 * cos(uTime * 0.06));
  float glow = smoothstep(0.55, 0.0, distance(uv + uMouse * 0.05, gp));
  c += uAccent * glow * 0.05;
  gl_FragColor = vec4(c, 1.0);
}
`
const vert = `varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position, 1.0); }`

const v3 = (hex: string) => { const c = new THREE.Color(hex); return new THREE.Vector3(c.r, c.g, c.b) }

export default function GradientBg() {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches

    const renderer = new THREE.WebGLRenderer({ antialias: false })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.25))
    el.appendChild(renderer.domElement)
    Object.assign(renderer.domElement.style, { width: '100%', height: '100%', display: 'block' })

    const scene = new THREE.Scene()
    const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1)
    const uniforms = {
      uTime: { value: 0 },
      uMouse: { value: new THREE.Vector2(0, 0) },
      uC0: { value: v3('#05070a') },
      uC1: { value: v3('#0e211b') },
      uAccent: { value: v3('#F26A43') },
    }
    const mesh = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), new THREE.ShaderMaterial({ vertexShader: vert, fragmentShader: frag, uniforms }))
    scene.add(mesh)

    const resize = () => renderer.setSize(el.clientWidth, el.clientHeight, false)
    resize()
    const ro = new ResizeObserver(resize)
    ro.observe(el)

    const target = new THREE.Vector2(0, 0)
    const onMove = (e: PointerEvent) => target.set(e.clientX / window.innerWidth - 0.5, -(e.clientY / window.innerHeight - 0.5))
    window.addEventListener('pointermove', onMove)

    let raf = 0
    const start = performance.now()
    const loop = () => {
      uniforms.uTime.value = (performance.now() - start) / 1000
      uniforms.uMouse.value.lerp(target, 0.04)
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
  return <div ref={ref} className="fixed inset-0 -z-10 h-full w-full" aria-hidden />
}
