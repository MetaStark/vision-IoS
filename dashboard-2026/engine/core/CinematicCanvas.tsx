'use client';

/**
 * Cinematic Canvas - Main Three.js/R3F Container
 * ADR-024: Retail Observer Cinematic Engine
 *
 * This is the root 3D canvas that hosts all cinematic elements.
 * Uses React Three Fiber for declarative Three.js rendering.
 */

import React, { Suspense, useRef } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import {
  OrbitControls,
  Environment,
  Stars,
  PerspectiveCamera,
} from '@react-three/drei';
import { EffectComposer, Bloom, Vignette, Noise } from '@react-three/postprocessing';
import * as THREE from 'three';

import { useVisualState, useAnimation, useVisuals, useSystemState } from './StateProvider';

// =============================================================================
// LOADING FALLBACK
// =============================================================================

function LoadingFallback() {
  return (
    <mesh>
      <boxGeometry args={[1, 1, 1]} />
      <meshStandardMaterial color="#333" wireframe />
    </mesh>
  );
}

// =============================================================================
// DATACENTER ENVIRONMENT (Background)
// =============================================================================

function DatacenterEnvironment() {
  const { visuals } = useVisualState();

  return (
    <>
      {/* Ambient lighting */}
      <ambientLight intensity={0.1} />

      {/* Main directional light */}
      <directionalLight
        position={[10, 10, 5]}
        intensity={0.3}
        color="#ffffff"
      />

      {/* Accent point lights */}
      <pointLight position={[-10, 5, -10]} intensity={0.2} color="#4488FF" />
      <pointLight position={[10, 5, 10]} intensity={0.2} color="#00FF88" />

      {/* Stars background */}
      <Stars
        radius={100}
        depth={50}
        count={3000}
        factor={4}
        saturation={0}
        fade
        speed={0.5}
      />

      {/* Floor grid */}
      <gridHelper
        args={[50, 50, '#1a1a3a', '#0a0a2a']}
        position={[0, -5, 0]}
      />
    </>
  );
}

// =============================================================================
// IoS-001: ASSET COMPLIANCE GRID (Left)
// =============================================================================

function IoS001AssetGrid() {
  const groupRef = useRef<THREE.Group>(null);
  const { animation } = useVisualState();

  useFrame((state) => {
    if (groupRef.current) {
      // Subtle rotation
      groupRef.current.rotation.y += 0.001;
    }
  });

  // Create a simple node graph representation
  const nodes = [
    { pos: [0, 0, 0], color: '#00FF88' },
    { pos: [1, 1, 0], color: '#00FF88' },
    { pos: [-1, 1, 0], color: '#00FF88' },
    { pos: [0, 2, 0], color: '#00FF88' },
    { pos: [1, -1, 0], color: '#44FF44' },
    { pos: [-1, -1, 0], color: '#44FF44' },
  ];

  return (
    <group ref={groupRef} position={[-8, 0, 0]}>
      {/* Central label */}
      {/* Nodes */}
      {nodes.map((node, i) => (
        <mesh key={i} position={node.pos as [number, number, number]}>
          <sphereGeometry args={[0.2, 16, 16]} />
          <meshStandardMaterial
            color={node.color}
            emissive={node.color}
            emissiveIntensity={0.5}
          />
        </mesh>
      ))}

      {/* Connections */}
      {nodes.slice(1).map((node, i) => (
        <line key={`line-${i}`}>
          <bufferGeometry>
            <bufferAttribute
              attach="attributes-position"
              count={2}
              array={new Float32Array([
                ...nodes[0].pos,
                ...node.pos,
              ])}
              itemSize={3}
            />
          </bufferGeometry>
          <lineBasicMaterial color="#00FF44" opacity={0.5} transparent />
        </line>
      ))}

      {/* Enclosing wireframe */}
      <mesh>
        <boxGeometry args={[4, 5, 2]} />
        <meshStandardMaterial
          color="#00FF88"
          wireframe
          transparent
          opacity={0.2}
        />
      </mesh>
    </group>
  );
}

// =============================================================================
// IoS-002: INDICATOR ENGINE CORE (Center)
// =============================================================================

function IoS002Core() {
  const coreRef = useRef<THREE.Mesh>(null);
  const ringRef = useRef<THREE.Mesh>(null);
  const { animation, visuals } = useVisualState();

  useFrame((state, delta) => {
    if (coreRef.current) {
      // Rotation based on animation params
      coreRef.current.rotation.y += animation.core_rotation_speed * delta;
      coreRef.current.rotation.x = Math.sin(state.clock.elapsedTime * animation.core_pulse_rate) * 0.1;
    }

    if (ringRef.current) {
      ringRef.current.rotation.z += animation.core_rotation_speed * delta * 0.5;
    }
  });

  return (
    <group position={[0, 0, 0]}>
      {/* Main core sphere */}
      <mesh ref={coreRef}>
        <sphereGeometry args={[1.5, 32, 32]} />
        <meshStandardMaterial
          color={visuals.primary_color}
          emissive={visuals.emission_color}
          emissiveIntensity={animation.core_glow_intensity}
          roughness={0.2}
          metalness={0.8}
        />
      </mesh>

      {/* Outer ring */}
      <mesh ref={ringRef}>
        <torusGeometry args={[2.5, 0.1, 16, 64]} />
        <meshStandardMaterial
          color={visuals.accent_color}
          emissive={visuals.accent_color}
          emissiveIntensity={0.3}
        />
      </mesh>

      {/* Second ring (perpendicular) */}
      <mesh rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[2.2, 0.08, 16, 64]} />
        <meshStandardMaterial
          color={visuals.accent_color}
          emissive={visuals.accent_color}
          emissiveIntensity={0.2}
        />
      </mesh>

      {/* Point light at core */}
      <pointLight
        color={visuals.emission_color}
        intensity={animation.core_glow_intensity * 2}
        distance={10}
        decay={2}
      />
    </group>
  );
}

// =============================================================================
// THE CURRENT (Trend Stream)
// =============================================================================

function TheCurrent() {
  const meshRef = useRef<THREE.Mesh>(null);
  const { animation, visuals } = useVisualState();

  useFrame((state, delta) => {
    if (meshRef.current) {
      // Flow animation
      const time = state.clock.elapsedTime;
      meshRef.current.position.x = 6 + Math.sin(time * animation.flow_speed) * 0.2;
      meshRef.current.rotation.z = animation.flow_direction * 0.3;
    }
  });

  return (
    <group position={[6, 2, 0]}>
      {/* Main flow tube */}
      <mesh ref={meshRef}>
        <cylinderGeometry args={[0.3 * animation.flow_thickness, 0.3 * animation.flow_thickness, 8, 32]} />
        <meshStandardMaterial
          color={visuals.trend_color}
          emissive={visuals.trend_color}
          emissiveIntensity={animation.flow_glow_intensity}
          transparent
          opacity={0.8}
        />
      </mesh>

      {/* Glow effect */}
      <mesh>
        <cylinderGeometry args={[0.5, 0.5, 8, 32]} />
        <meshStandardMaterial
          color={visuals.trend_color}
          transparent
          opacity={0.2}
        />
      </mesh>
    </group>
  );
}

// =============================================================================
// THE PULSE (Momentum Wave)
// =============================================================================

function ThePulse() {
  const groupRef = useRef<THREE.Group>(null);
  const { animation, visuals } = useVisualState();

  useFrame((state) => {
    if (groupRef.current) {
      const time = state.clock.elapsedTime;
      // Wave animation
      groupRef.current.children.forEach((child, i) => {
        if (child instanceof THREE.Mesh) {
          child.position.y = Math.sin(time * animation.pulse_frequency + i * 0.5) * animation.pulse_amplitude;
          child.scale.setScalar(0.8 + Math.sin(time * animation.pulse_frequency * 2 + i) * 0.2);
        }
      });
    }
  });

  return (
    <group ref={groupRef} position={[6, 0.7, 0]}>
      {/* Wave segments */}
      {Array.from({ length: 16 }).map((_, i) => (
        <mesh key={i} position={[(i - 8) * 0.5, 0, 0]}>
          <sphereGeometry args={[0.15, 16, 16]} />
          <meshStandardMaterial
            color={visuals.momentum_color}
            emissive={visuals.momentum_color}
            emissiveIntensity={0.6}
          />
        </mesh>
      ))}
    </group>
  );
}

// =============================================================================
// THE WEATHER (Volatility Cloud)
// =============================================================================

function TheWeather() {
  const cloudRef = useRef<THREE.Mesh>(null);
  const { animation, visuals } = useVisualState();

  useFrame((state, delta) => {
    if (cloudRef.current) {
      // Turbulence animation
      cloudRef.current.rotation.y += animation.cloud_turbulence * delta * 0.5;
      cloudRef.current.rotation.x = Math.sin(state.clock.elapsedTime * 0.5) * animation.cloud_turbulence * 0.1;
    }
  });

  return (
    <group position={[6, -0.7, 0]}>
      {/* Cloud volume */}
      <mesh ref={cloudRef}>
        <sphereGeometry args={[1 * animation.cloud_height, 16, 16]} />
        <meshStandardMaterial
          color={visuals.volatility_color}
          transparent
          opacity={animation.cloud_density * 0.5}
          roughness={1}
        />
      </mesh>

      {/* Inner glow */}
      <mesh>
        <sphereGeometry args={[0.8, 16, 16]} />
        <meshStandardMaterial
          color={visuals.volatility_color}
          emissive={visuals.volatility_color}
          emissiveIntensity={0.3}
          transparent
          opacity={0.3}
        />
      </mesh>
    </group>
  );
}

// =============================================================================
// THE FORCE (Volume Channel)
// =============================================================================

function TheForce() {
  const groupRef = useRef<THREE.Group>(null);
  const { animation, visuals } = useVisualState();

  useFrame((state) => {
    if (groupRef.current) {
      // Particle animation
      groupRef.current.children.forEach((child, i) => {
        if (child instanceof THREE.Mesh) {
          // Move particles through channel
          child.position.x += animation.particle_speed * 0.02;
          if (child.position.x > 4) {
            child.position.x = -4;
          }
        }
      });
    }
  });

  // Generate particles based on density
  const particleCount = Math.floor(animation.particle_density * 50);

  return (
    <group position={[6, -2, 0]}>
      {/* Channel tube */}
      <mesh>
        <cylinderGeometry args={[0.4, 0.4, 8, 32]} />
        <meshStandardMaterial
          color={visuals.volume_color}
          transparent
          opacity={0.3}
          emissive={visuals.volume_color}
          emissiveIntensity={animation.channel_glow * 0.3}
        />
      </mesh>

      {/* Particles */}
      <group ref={groupRef}>
        {Array.from({ length: particleCount }).map((_, i) => (
          <mesh
            key={i}
            position={[(Math.random() - 0.5) * 8, (Math.random() - 0.5) * 0.3, (Math.random() - 0.5) * 0.3]}
          >
            <sphereGeometry args={[0.05, 8, 8]} />
            <meshStandardMaterial
              color={visuals.volume_color}
              emissive={visuals.volume_color}
              emissiveIntensity={1}
            />
          </mesh>
        ))}
      </group>
    </group>
  );
}

// =============================================================================
// POST-PROCESSING
// =============================================================================

function PostProcessingEffects() {
  const { visuals, defcon } = useVisualState();

  // Disable effects in high DEFCON
  if (defcon === 'RED' || defcon === 'BLACK') {
    return null;
  }

  return (
    <EffectComposer>
      <Bloom
        intensity={visuals.bloom_intensity}
        luminanceThreshold={visuals.bloom_threshold}
        luminanceSmoothing={0.9}
      />
      <Vignette
        offset={0.5}
        darkness={visuals.vignette_intensity}
      />
      {visuals.film_grain_intensity > 0 && (
        <Noise opacity={visuals.film_grain_intensity} />
      )}
    </EffectComposer>
  );
}

// =============================================================================
// CAMERA CONTROLLER
// =============================================================================

function CameraController() {
  const { animation } = useVisualState();
  const { camera } = useThree();

  useFrame((state) => {
    // Apply camera shake if volatility is high
    if (animation.camera_shake_amplitude > 0) {
      const time = state.clock.elapsedTime;
      camera.position.x += Math.sin(time * animation.camera_shake_frequency) * animation.camera_shake_amplitude;
      camera.position.y += Math.cos(time * animation.camera_shake_frequency * 1.1) * animation.camera_shake_amplitude;
    }
  });

  return null;
}

// =============================================================================
// DEFCON OVERLAY
// =============================================================================

function DEFCONOverlay() {
  const { defcon } = useVisualState();

  if (defcon !== 'RED' && defcon !== 'BLACK') {
    return null;
  }

  const text = defcon === 'BLACK' ? 'SYSTEM LOCKDOWN' : 'DEFENSIVE MODE';
  const opacity = defcon === 'BLACK' ? 0.95 : 0.8;

  return (
    <mesh position={[0, 0, 5]}>
      <planeGeometry args={[20, 10]} />
      <meshBasicMaterial
        color="#000000"
        transparent
        opacity={opacity}
      />
    </mesh>
  );
}

// =============================================================================
// MAIN SCENE
// =============================================================================

function Scene() {
  return (
    <>
      <DatacenterEnvironment />

      <Suspense fallback={<LoadingFallback />}>
        {/* IoS-001: Asset Grid (Left) */}
        <IoS001AssetGrid />

        {/* IoS-002: Indicator Core (Center) */}
        <IoS002Core />

        {/* The Four Streams (Right) */}
        <TheCurrent />
        <ThePulse />
        <TheWeather />
        <TheForce />

        {/* DEFCON Overlay */}
        <DEFCONOverlay />
      </Suspense>

      {/* Camera */}
      <PerspectiveCamera makeDefault position={[0, 2, 15]} fov={60} />
      <OrbitControls
        enablePan={false}
        enableZoom={true}
        minDistance={8}
        maxDistance={25}
        autoRotate
        autoRotateSpeed={0.5}
      />

      <CameraController />
      <PostProcessingEffects />
    </>
  );
}

// =============================================================================
// CANVAS COMPONENT
// =============================================================================

interface CinematicCanvasProps {
  className?: string;
}

export function CinematicCanvas({ className = '' }: CinematicCanvasProps) {
  const { visuals, loading, error } = useVisualState();

  if (error) {
    return (
      <div className={`flex items-center justify-center bg-black text-red-500 ${className}`}>
        <div className="text-center">
          <p className="text-xl font-bold">Engine Error</p>
          <p className="text-sm opacity-70">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`relative ${className}`}>
      <Canvas
        gl={{
          antialias: true,
          toneMapping: THREE.ACESFilmicToneMapping,
          toneMappingExposure: 1.0,
        }}
        style={{ background: visuals.background_color }}
      >
        <Scene />
      </Canvas>

      {/* Loading overlay */}
      {loading && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/50">
          <div className="text-white text-center">
            <div className="animate-pulse text-2xl">Loading Visual State...</div>
          </div>
        </div>
      )}
    </div>
  );
}

export default CinematicCanvas;
