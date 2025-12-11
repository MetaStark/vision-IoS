/**
 * Visual Cinematic Engine - Main Export
 * ADR-024: Retail Observer Cinematic Engine
 *
 * 2026 AAA-quality visual market data visualization
 */

// Core types
export * from './core/types';

// State management
export { StateProvider, useVisualState, useAnimation, useVisuals, useEvents, useSystemState, useVerification } from './core/StateProvider';

// Mapping functions
export * from './core/mapping';

// Main canvas
export { CinematicCanvas } from './core/CinematicCanvas';
