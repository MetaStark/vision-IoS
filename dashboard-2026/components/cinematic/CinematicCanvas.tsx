'use client'

/**
 * CinematicCanvas - WebGL 3D Visualization Engine
 * ADR-022/023/024: Retail Observer Cinematic Engine
 *
 * Renders four energy streams driven by Visual State Vectors (VSV):
 * - The Current (Trend) - Plasma river flow
 * - The Pulse (Momentum) - Wave oscillations
 * - The Weather (Volatility) - Volumetric clouds
 * - The Force (Volume) - Particle channel
 *
 * Authority: STIG (CTO) per EC-003
 */

import { useRef, useMemo, useEffect, useState } from 'react'
import { Canvas, useFrame, useThree, extend } from '@react-three/fiber'
import * as THREE from 'three'

// ============================================================================
// Types
// ============================================================================

export interface VSVData {
  trend: {
    flowSpeed: number
    flowDirection: number
    intensity: number
    colorHue: number
  }
  momentum: {
    amplitude: number
    frequency: number
    phase: number
    colorSaturation: number
  }
  volatility: {
    density: number
    turbulence: number
    colorLightness: number
  }
  volume: {
    particleCount: number
    particleSpeed: number
    glowIntensity: number
  }
  camera: {
    shakeIntensity: number
    zoomLevel: number
  }
  post_processing: {
    bloomIntensity: number
    vignetteIntensity: number
    filmGrain: number
  }
  regime?: {
    label: string | null
    confidence: number | null
  }
  defcon: {
    level: string
    degradationFactor: number
  }
}

interface CinematicCanvasProps {
  vsv: VSVData
  width?: number
  height?: number
}

// ============================================================================
// Utility Functions
// ============================================================================

function getRegimeColor(regime: string | null | undefined): THREE.Color {
  switch (regime) {
    case 'BULLISH': return new THREE.Color(0.2, 0.9, 0.3)
    case 'BEARISH': return new THREE.Color(0.9, 0.2, 0.2)
    case 'VOLATILE': return new THREE.Color(0.9, 0.6, 0.1)
    case 'ACCUMULATION': return new THREE.Color(0.2, 0.6, 0.9)
    case 'DISTRIBUTION': return new THREE.Color(0.7, 0.3, 0.8)
    default: return new THREE.Color(0.5, 0.5, 0.6)
  }
}

function getDefconMultiplier(level: string): number {
  switch (level) {
    case 'GREEN': return 1.0
    case 'YELLOW': return 0.8
    case 'ORANGE': return 0.5
    case 'RED': return 0.3
    case 'BLACK': return 0.1
    default: return 1.0
  }
}

// ============================================================================
// THE CURRENT - Trend Plasma River
// ============================================================================

function TheCurrent({ vsv }: { vsv: VSVData }) {
  const materialRef = useRef<THREE.ShaderMaterial>(null)

  const defconMult = getDefconMultiplier(vsv.defcon.level)
  const regimeColor = getRegimeColor(vsv.regime?.label)

  const uniforms = useMemo(() => ({
    uTime: { value: 0 },
    uFlowSpeed: { value: vsv.trend.flowSpeed * defconMult },
    uFlowDirection: { value: vsv.trend.flowDirection },
    uIntensity: { value: vsv.trend.intensity * defconMult },
    uColorHue: { value: vsv.trend.colorHue },
    uRegimeColor: { value: regimeColor },
    uDefconLevel: { value: defconMult },
  }), [])

  useEffect(() => {
    if (materialRef.current) {
      materialRef.current.uniforms.uFlowSpeed.value = vsv.trend.flowSpeed * defconMult
      materialRef.current.uniforms.uFlowDirection.value = vsv.trend.flowDirection
      materialRef.current.uniforms.uIntensity.value = vsv.trend.intensity * defconMult
      materialRef.current.uniforms.uColorHue.value = vsv.trend.colorHue
      materialRef.current.uniforms.uRegimeColor.value = regimeColor
      materialRef.current.uniforms.uDefconLevel.value = defconMult
    }
  }, [vsv, defconMult, regimeColor])

  useFrame((state) => {
    if (materialRef.current) {
      materialRef.current.uniforms.uTime.value = state.clock.elapsedTime
    }
  })

  const vertexShader = `
    varying vec2 vUv;
    varying vec3 vPosition;

    void main() {
      vUv = uv;
      vPosition = position;
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }
  `

  const fragmentShader = `
    uniform float uTime;
    uniform float uFlowSpeed;
    uniform float uFlowDirection;
    uniform float uIntensity;
    uniform float uColorHue;
    uniform vec3 uRegimeColor;
    uniform float uDefconLevel;

    varying vec2 vUv;
    varying vec3 vPosition;

    vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
    vec2 mod289(vec2 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
    vec3 permute(vec3 x) { return mod289(((x*34.0)+1.0)*x); }

    float snoise(vec2 v) {
      const vec4 C = vec4(0.211324865405187, 0.366025403784439, -0.577350269189626, 0.024390243902439);
      vec2 i  = floor(v + dot(v, C.yy));
      vec2 x0 = v -   i + dot(i, C.xx);
      vec2 i1 = (x0.x > x0.y) ? vec2(1.0, 0.0) : vec2(0.0, 1.0);
      vec4 x12 = x0.xyxy + C.xxzz;
      x12.xy -= i1;
      i = mod289(i);
      vec3 p = permute(permute(i.y + vec3(0.0, i1.y, 1.0)) + i.x + vec3(0.0, i1.x, 1.0));
      vec3 m = max(0.5 - vec3(dot(x0,x0), dot(x12.xy,x12.xy), dot(x12.zw,x12.zw)), 0.0);
      m = m*m;
      m = m*m;
      vec3 x = 2.0 * fract(p * C.www) - 1.0;
      vec3 h = abs(x) - 0.5;
      vec3 ox = floor(x + 0.5);
      vec3 a0 = x - ox;
      m *= 1.79284291400159 - 0.85373472095314 * (a0*a0 + h*h);
      vec3 g;
      g.x  = a0.x  * x0.x  + h.x  * x0.y;
      g.yz = a0.yz * x12.xz + h.yz * x12.yw;
      return 130.0 * dot(m, g);
    }

    vec3 hsl2rgb(float h, float s, float l) {
      vec3 rgb = clamp(abs(mod(h*6.0+vec3(0.0,4.0,2.0),6.0)-3.0)-1.0, 0.0, 1.0);
      return l + s * (rgb - 0.5) * (1.0 - abs(2.0 * l - 1.0));
    }

    void main() {
      vec2 uv = vUv;
      float flowTime = uTime * uFlowSpeed * 0.5;
      float direction = uFlowDirection * 3.14159;

      vec2 flowUv = uv;
      flowUv.x += cos(direction) * flowTime;
      flowUv.y += sin(direction) * flowTime;

      float noise1 = snoise(flowUv * 3.0 + uTime * 0.2) * 0.5 + 0.5;
      float noise2 = snoise(flowUv * 6.0 - uTime * 0.3) * 0.5 + 0.5;
      float noise3 = snoise(flowUv * 12.0 + uTime * 0.1) * 0.5 + 0.5;

      float plasma = noise1 * 0.5 + noise2 * 0.3 + noise3 * 0.2;
      plasma = pow(plasma, 1.5);

      vec3 baseColor = hsl2rgb(uColorHue, 0.8, 0.5);
      vec3 color = mix(baseColor, uRegimeColor, 0.4);

      color *= plasma * uIntensity * 2.0;
      color += pow(plasma, 4.0) * vec3(1.0, 0.9, 0.7) * uIntensity;

      float edgeFade = smoothstep(0.0, 0.3, uv.y) * smoothstep(1.0, 0.7, uv.y);
      edgeFade *= smoothstep(0.0, 0.2, uv.x) * smoothstep(1.0, 0.8, uv.x);

      vec3 desaturated = vec3(dot(color, vec3(0.299, 0.587, 0.114)));
      color = mix(desaturated, color, uDefconLevel);

      gl_FragColor = vec4(color * edgeFade, plasma * uIntensity * edgeFade);
    }
  `

  return (
    <mesh position={[0, -2, -3]} rotation={[-0.5, 0, 0]}>
      <planeGeometry args={[20, 6, 64, 64]} />
      <shaderMaterial
        ref={materialRef}
        vertexShader={vertexShader}
        fragmentShader={fragmentShader}
        uniforms={uniforms}
        transparent
        blending={THREE.AdditiveBlending}
        side={THREE.DoubleSide}
      />
    </mesh>
  )
}

// ============================================================================
// THE PULSE - Momentum Wave Visualization
// ============================================================================

function ThePulse({ vsv }: { vsv: VSVData }) {
  const materialRef = useRef<THREE.ShaderMaterial>(null)
  const defconMult = getDefconMultiplier(vsv.defcon.level)

  const uniforms = useMemo(() => ({
    uTime: { value: 0 },
    uAmplitude: { value: vsv.momentum.amplitude * defconMult },
    uFrequency: { value: vsv.momentum.frequency },
    uPhase: { value: vsv.momentum.phase },
    uSaturation: { value: vsv.momentum.colorSaturation * defconMult },
    uDefconLevel: { value: defconMult },
  }), [])

  useEffect(() => {
    if (materialRef.current) {
      materialRef.current.uniforms.uAmplitude.value = vsv.momentum.amplitude * defconMult
      materialRef.current.uniforms.uFrequency.value = vsv.momentum.frequency
      materialRef.current.uniforms.uPhase.value = vsv.momentum.phase
      materialRef.current.uniforms.uSaturation.value = vsv.momentum.colorSaturation * defconMult
      materialRef.current.uniforms.uDefconLevel.value = defconMult
    }
  }, [vsv, defconMult])

  useFrame((state) => {
    if (materialRef.current) {
      materialRef.current.uniforms.uTime.value = state.clock.elapsedTime
    }
  })

  const vertexShader = `
    uniform float uTime;
    uniform float uAmplitude;
    uniform float uFrequency;
    uniform float uPhase;

    varying vec2 vUv;
    varying float vElevation;

    void main() {
      vUv = uv;
      vec3 pos = position;

      float wave1 = sin(pos.x * uFrequency + uTime * 2.0 + uPhase) * uAmplitude;
      float wave2 = sin(pos.x * uFrequency * 2.0 - uTime * 1.5 + uPhase * 0.5) * uAmplitude * 0.5;
      float wave3 = cos(pos.y * uFrequency * 0.5 + uTime * 0.8) * uAmplitude * 0.3;

      pos.z += wave1 + wave2 + wave3;
      vElevation = (wave1 + wave2 + wave3) / (uAmplitude * 2.0);

      gl_Position = projectionMatrix * modelViewMatrix * vec4(pos, 1.0);
    }
  `

  const fragmentShader = `
    uniform float uSaturation;
    uniform float uDefconLevel;

    varying vec2 vUv;
    varying float vElevation;

    vec3 hsl2rgb(float h, float s, float l) {
      vec3 rgb = clamp(abs(mod(h*6.0+vec3(0.0,4.0,2.0),6.0)-3.0)-1.0, 0.0, 1.0);
      return l + s * (rgb - 0.5) * (1.0 - abs(2.0 * l - 1.0));
    }

    void main() {
      float hue = 0.55 + vElevation * 0.15;
      vec3 color = hsl2rgb(hue, uSaturation, 0.5 + vElevation * 0.3);

      float glow = pow(abs(vElevation), 2.0) * 1.5;
      color += vec3(0.3, 0.5, 1.0) * glow;

      float edgeFade = smoothstep(0.0, 0.2, vUv.x) * smoothstep(1.0, 0.8, vUv.x);
      edgeFade *= smoothstep(0.0, 0.2, vUv.y) * smoothstep(1.0, 0.8, vUv.y);

      vec3 desaturated = vec3(dot(color, vec3(0.299, 0.587, 0.114)));
      color = mix(desaturated, color, uDefconLevel);

      float alpha = (0.4 + abs(vElevation) * 0.6) * edgeFade;
      gl_FragColor = vec4(color, alpha);
    }
  `

  return (
    <mesh position={[0, 0, -5]}>
      <planeGeometry args={[16, 8, 128, 128]} />
      <shaderMaterial
        ref={materialRef}
        vertexShader={vertexShader}
        fragmentShader={fragmentShader}
        uniforms={uniforms}
        transparent
        blending={THREE.AdditiveBlending}
        side={THREE.DoubleSide}
      />
    </mesh>
  )
}

// ============================================================================
// THE WEATHER - Volatility Volumetric Clouds
// ============================================================================

function TheWeather({ vsv }: { vsv: VSVData }) {
  const materialRef = useRef<THREE.ShaderMaterial>(null)
  const defconMult = getDefconMultiplier(vsv.defcon.level)

  const uniforms = useMemo(() => ({
    uTime: { value: 0 },
    uDensity: { value: vsv.volatility.density * defconMult },
    uTurbulence: { value: vsv.volatility.turbulence },
    uLightness: { value: vsv.volatility.colorLightness },
    uDefconLevel: { value: defconMult },
  }), [])

  useEffect(() => {
    if (materialRef.current) {
      materialRef.current.uniforms.uDensity.value = vsv.volatility.density * defconMult
      materialRef.current.uniforms.uTurbulence.value = vsv.volatility.turbulence
      materialRef.current.uniforms.uLightness.value = vsv.volatility.colorLightness
      materialRef.current.uniforms.uDefconLevel.value = defconMult
    }
  }, [vsv, defconMult])

  useFrame((state) => {
    if (materialRef.current) {
      materialRef.current.uniforms.uTime.value = state.clock.elapsedTime
    }
  })

  const vertexShader = `
    varying vec2 vUv;
    void main() {
      vUv = uv;
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }
  `

  const fragmentShader = `
    uniform float uTime;
    uniform float uDensity;
    uniform float uTurbulence;
    uniform float uLightness;
    uniform float uDefconLevel;

    varying vec2 vUv;

    vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
    vec4 mod289(vec4 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
    vec4 permute(vec4 x) { return mod289(((x*34.0)+1.0)*x); }
    vec4 taylorInvSqrt(vec4 r) { return 1.79284291400159 - 0.85373472095314 * r; }

    float snoise3D(vec3 v) {
      const vec2 C = vec2(1.0/6.0, 1.0/3.0);
      const vec4 D = vec4(0.0, 0.5, 1.0, 2.0);
      vec3 i  = floor(v + dot(v, C.yyy));
      vec3 x0 = v - i + dot(i, C.xxx);
      vec3 g = step(x0.yzx, x0.xyz);
      vec3 l = 1.0 - g;
      vec3 i1 = min(g.xyz, l.zxy);
      vec3 i2 = max(g.xyz, l.zxy);
      vec3 x1 = x0 - i1 + C.xxx;
      vec3 x2 = x0 - i2 + C.yyy;
      vec3 x3 = x0 - D.yyy;
      i = mod289(i);
      vec4 p = permute(permute(permute(i.z + vec4(0.0, i1.z, i2.z, 1.0)) + i.y + vec4(0.0, i1.y, i2.y, 1.0)) + i.x + vec4(0.0, i1.x, i2.x, 1.0));
      float n_ = 0.142857142857;
      vec3 ns = n_ * D.wyz - D.xzx;
      vec4 j = p - 49.0 * floor(p * ns.z * ns.z);
      vec4 x_ = floor(j * ns.z);
      vec4 y_ = floor(j - 7.0 * x_);
      vec4 x = x_ *ns.x + ns.yyyy;
      vec4 y = y_ *ns.x + ns.yyyy;
      vec4 h = 1.0 - abs(x) - abs(y);
      vec4 b0 = vec4(x.xy, y.xy);
      vec4 b1 = vec4(x.zw, y.zw);
      vec4 s0 = floor(b0)*2.0 + 1.0;
      vec4 s1 = floor(b1)*2.0 + 1.0;
      vec4 sh = -step(h, vec4(0.0));
      vec4 a0 = b0.xzyw + s0.xzyw*sh.xxyy;
      vec4 a1 = b1.xzyw + s1.xzyw*sh.zzww;
      vec3 p0 = vec3(a0.xy, h.x);
      vec3 p1 = vec3(a0.zw, h.y);
      vec3 p2 = vec3(a1.xy, h.z);
      vec3 p3 = vec3(a1.zw, h.w);
      vec4 norm = taylorInvSqrt(vec4(dot(p0,p0), dot(p1,p1), dot(p2,p2), dot(p3,p3)));
      p0 *= norm.x; p1 *= norm.y; p2 *= norm.z; p3 *= norm.w;
      vec4 m = max(0.6 - vec4(dot(x0,x0), dot(x1,x1), dot(x2,x2), dot(x3,x3)), 0.0);
      m = m * m;
      return 42.0 * dot(m*m, vec4(dot(p0,x0), dot(p1,x1), dot(p2,x2), dot(p3,x3)));
    }

    float fbm(vec3 p) {
      float value = 0.0;
      float amplitude = 0.5;
      float frequency = 1.0;
      for(int i = 0; i < 5; i++) {
        value += amplitude * snoise3D(p * frequency);
        amplitude *= 0.5;
        frequency *= 2.0;
      }
      return value;
    }

    void main() {
      vec3 pos = vec3(vUv * 4.0, uTime * 0.1 * uTurbulence);
      float cloud = fbm(pos);
      cloud = cloud * 0.5 + 0.5;

      vec3 turbulentPos = pos + vec3(snoise3D(pos * 2.0) * uTurbulence, snoise3D(pos * 2.0 + 100.0) * uTurbulence, 0.0);
      float turbulentCloud = fbm(turbulentPos);
      cloud = mix(cloud, turbulentCloud * 0.5 + 0.5, uTurbulence);
      cloud = smoothstep(1.0 - uDensity, 1.0, cloud);

      vec3 lightDir = normalize(vec3(1.0, 1.0, 0.5));
      float lighting = dot(normalize(vec3(cloud, cloud, 1.0)), lightDir) * 0.5 + 0.5;

      vec3 darkColor = vec3(0.1, 0.15, 0.25);
      vec3 lightColor = vec3(uLightness * 0.8, uLightness * 0.85, uLightness);
      vec3 color = mix(darkColor, lightColor, lighting * cloud);
      color += vec3(0.4, 0.5, 0.7) * pow(cloud, 3.0) * uDensity;

      vec3 desaturated = vec3(dot(color, vec3(0.299, 0.587, 0.114)));
      color = mix(desaturated, color, uDefconLevel);

      float edgeFade = smoothstep(0.0, 0.3, vUv.x) * smoothstep(1.0, 0.7, vUv.x);
      edgeFade *= smoothstep(0.0, 0.3, vUv.y) * smoothstep(1.0, 0.7, vUv.y);

      gl_FragColor = vec4(color, cloud * uDensity * edgeFade * 0.7);
    }
  `

  return (
    <mesh position={[0, 3, -8]}>
      <planeGeometry args={[24, 10, 1, 1]} />
      <shaderMaterial
        ref={materialRef}
        vertexShader={vertexShader}
        fragmentShader={fragmentShader}
        uniforms={uniforms}
        transparent
        blending={THREE.NormalBlending}
        side={THREE.DoubleSide}
        depthWrite={false}
      />
    </mesh>
  )
}

// ============================================================================
// THE FORCE - Volume Particle System
// ============================================================================

function TheForce({ vsv }: { vsv: VSVData }) {
  const pointsRef = useRef<THREE.Points>(null)
  const materialRef = useRef<THREE.ShaderMaterial>(null)

  const defconMult = getDefconMultiplier(vsv.defcon.level)
  const particleCount = Math.floor(vsv.volume.particleCount * defconMult)

  const [positions, velocities, sizes] = useMemo(() => {
    const count = Math.max(100, particleCount)
    const pos = new Float32Array(count * 3)
    const vel = new Float32Array(count * 3)
    const siz = new Float32Array(count)

    for (let i = 0; i < count; i++) {
      pos[i * 3] = (Math.random() - 0.5) * 20
      pos[i * 3 + 1] = (Math.random() - 0.5) * 8 - 1
      pos[i * 3 + 2] = (Math.random() - 0.5) * 15 - 5
      vel[i * 3] = (Math.random() - 0.5) * 0.5
      vel[i * 3 + 1] = (Math.random() - 0.5) * 0.3
      vel[i * 3 + 2] = (Math.random() - 0.3) * 0.5
      siz[i] = Math.random() * 0.5 + 0.1
    }

    return [pos, vel, siz]
  }, [particleCount])

  const uniforms = useMemo(() => ({
    uTime: { value: 0 },
    uSpeed: { value: vsv.volume.particleSpeed * defconMult },
    uGlow: { value: vsv.volume.glowIntensity * defconMult },
    uDefconLevel: { value: defconMult },
  }), [])

  useEffect(() => {
    if (materialRef.current) {
      materialRef.current.uniforms.uSpeed.value = vsv.volume.particleSpeed * defconMult
      materialRef.current.uniforms.uGlow.value = vsv.volume.glowIntensity * defconMult
      materialRef.current.uniforms.uDefconLevel.value = defconMult
    }
  }, [vsv, defconMult])

  useFrame((state, delta) => {
    if (materialRef.current) {
      materialRef.current.uniforms.uTime.value = state.clock.elapsedTime
    }

    if (pointsRef.current) {
      const geometry = pointsRef.current.geometry
      const posAttr = geometry.getAttribute('position')
      const speed = vsv.volume.particleSpeed * defconMult * delta * 10

      for (let i = 0; i < posAttr.count; i++) {
        let x = posAttr.getX(i)
        let y = posAttr.getY(i)
        let z = posAttr.getZ(i)

        z += velocities[i * 3 + 2] * speed
        x += velocities[i * 3] * speed * 0.5
        y += Math.sin(state.clock.elapsedTime * 2 + i) * speed * 0.1

        if (z > 5) {
          z = -15
          x = (Math.random() - 0.5) * 20
          y = (Math.random() - 0.5) * 8 - 1
        }

        posAttr.setXYZ(i, x, y, z)
      }
      posAttr.needsUpdate = true
    }
  })

  const vertexShader = `
    attribute float size;
    uniform float uGlow;
    varying float vGlow;

    void main() {
      vGlow = uGlow;
      vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
      gl_PointSize = size * uGlow * 50.0 * (300.0 / -mvPosition.z);
      gl_Position = projectionMatrix * mvPosition;
    }
  `

  const fragmentShader = `
    uniform float uDefconLevel;
    varying float vGlow;

    void main() {
      vec2 center = gl_PointCoord - vec2(0.5);
      float dist = length(center);
      if (dist > 0.5) discard;

      float alpha = smoothstep(0.5, 0.0, dist);
      vec3 color = vec3(0.4, 0.6, 1.0) * vGlow;
      color += vec3(1.0, 0.8, 0.5) * pow(alpha, 3.0) * vGlow;

      vec3 desaturated = vec3(dot(color, vec3(0.299, 0.587, 0.114)));
      color = mix(desaturated, color, uDefconLevel);

      gl_FragColor = vec4(color, alpha * vGlow);
    }
  `

  return (
    <points ref={pointsRef}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          count={positions.length / 3}
          array={positions}
          itemSize={3}
        />
        <bufferAttribute
          attach="attributes-size"
          count={sizes.length}
          array={sizes}
          itemSize={1}
        />
      </bufferGeometry>
      <shaderMaterial
        ref={materialRef}
        vertexShader={vertexShader}
        fragmentShader={fragmentShader}
        uniforms={uniforms}
        transparent
        blending={THREE.AdditiveBlending}
        depthWrite={false}
      />
    </points>
  )
}

// ============================================================================
// CAMERA CONTROLLER
// ============================================================================

function CameraController({ vsv }: { vsv: VSVData }) {
  const { camera } = useThree()
  const basePosition = useRef(new THREE.Vector3(0, 0, 10))
  const defconMult = getDefconMultiplier(vsv.defcon.level)

  useFrame(() => {
    const shakeIntensity = vsv.camera.shakeIntensity * defconMult
    const zoom = vsv.camera.zoomLevel

    const shakeX = (Math.random() - 0.5) * shakeIntensity * 0.5
    const shakeY = (Math.random() - 0.5) * shakeIntensity * 0.5

    const targetZ = 10 / zoom
    const currentZ = camera.position.z

    camera.position.x = basePosition.current.x + shakeX
    camera.position.y = basePosition.current.y + shakeY
    camera.position.z = THREE.MathUtils.lerp(currentZ, targetZ, 0.05)

    camera.lookAt(0, 0, -5)
  })

  return null
}

// ============================================================================
// MAIN CANVAS COMPONENT
// ============================================================================

export function CinematicCanvas({ vsv, width, height }: CinematicCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [isClient, setIsClient] = useState(false)

  useEffect(() => {
    setIsClient(true)
  }, [])

  if (!isClient) {
    return (
      <div
        ref={containerRef}
        style={{
          width: width || '100%',
          height: height || '100%',
          minHeight: 400,
          background: 'linear-gradient(180deg, #0a0a12 0%, #141428 50%, #0a0a12 100%)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <span style={{ color: '#666' }}>Initializing WebGL...</span>
      </div>
    )
  }

  return (
    <div
      ref={containerRef}
      style={{
        width: width || '100%',
        height: height || '100%',
        minHeight: 400,
        background: 'linear-gradient(180deg, #0a0a12 0%, #141428 50%, #0a0a12 100%)',
        borderRadius: 8,
        overflow: 'hidden',
      }}
    >
      <Canvas
        camera={{ position: [0, 0, 10], fov: 60 }}
        gl={{
          antialias: true,
          alpha: true,
          powerPreference: 'high-performance',
        }}
        dpr={[1, 2]}
      >
        <ambientLight intensity={0.2} />
        <pointLight position={[10, 10, 10]} intensity={0.5} />

        <mesh position={[0, 0, -20]}>
          <sphereGeometry args={[30, 32, 32]} />
          <meshBasicMaterial color="#0a0a12" side={THREE.BackSide} />
        </mesh>

        <TheWeather vsv={vsv} />
        <ThePulse vsv={vsv} />
        <TheCurrent vsv={vsv} />
        <TheForce vsv={vsv} />

        <CameraController vsv={vsv} />
      </Canvas>
    </div>
  )
}
