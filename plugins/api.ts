import type { SparsityTelemetry } from '../core/sparsity/sparse_utils';

export interface GlyphHookContext {
  readonly glyphs: readonly string[];
  readonly context: readonly string[];
  readonly limit: number;
}

export interface EmotionHookContext {
  readonly baseline: number;
  readonly delta: number;
}

export interface BloomHookContext {
  readonly probability: number;
  readonly seeds: number;
  readonly density: number;
  readonly variance: number;
}

export interface GlyphHookResult {
  readonly add?: readonly string[];
  readonly replace?: readonly string[];
}

export interface EmotionHookResult {
  readonly delta?: number;
  readonly bias?: number;
  readonly label?: string;
}

export interface BloomHookResult {
  readonly delta?: number;
  readonly floor?: number;
  readonly ceiling?: number;
  readonly rationale?: string;
}

export interface ReasoncoreLitePlugin {
  readonly name?: string;
  readonly onGlyph?: (context: Readonly<GlyphHookContext>) => GlyphHookResult | void;
  readonly onEmotion?: (context: Readonly<EmotionHookContext>) => EmotionHookResult | void;
  readonly onBloom?: (context: Readonly<BloomHookContext>) => BloomHookResult | void;
}

export interface SandboxEvaluator {
  evaluate(code: string): ReasoncoreLitePlugin;
}

export interface PluginDiagnostics {
  readonly plugin: string;
  readonly hook: 'glyph' | 'emotion' | 'bloom';
  readonly type: 'applied' | 'skipped' | 'error';
  readonly detail?: string;
}

interface PluginEntry {
  readonly plugin: ReasoncoreLitePlugin;
  readonly name: string;
}

export interface PluginHostResult<T> {
  readonly value: T;
  readonly diagnostics: readonly PluginDiagnostics[];
}

export type SparseTarget = 'emotion' | 'drift' | 'glyph';

export interface BaselineSparsityVector {
  readonly density?: number;
  readonly activeIndices?: readonly number[];
  readonly tick?: number;
  readonly sceneTags?: readonly string[];
}

export interface BaselineSparsitySnapshot {
  readonly tick?: number;
  readonly sceneTags?: readonly string[];
  readonly targets: Partial<Record<SparseTarget, BaselineSparsityVector>>;
}

export interface SparseRuntimeSnapshot {
  readonly vectors: Partial<Record<SparseTarget, readonly number[]>>;
  readonly telemetry: Partial<Record<SparseTarget, SparsityTelemetry>>;
  readonly baseline?: BaselineSparsitySnapshot;
}

const EMPTY_SNAPSHOT: SparseRuntimeSnapshot = { vectors: {}, telemetry: {} };

let activeSparseSnapshot: SparseRuntimeSnapshot = EMPTY_SNAPSHOT;
let latestSparseSnapshot: SparseRuntimeSnapshot = EMPTY_SNAPSHOT;
let activeSnapshotDepth = 0;

const resolveSnapshot = (): SparseRuntimeSnapshot =>
  activeSnapshotDepth > 0 ? activeSparseSnapshot : latestSparseSnapshot;

const cloneTelemetry = (snapshot: SparseRuntimeSnapshot): Partial<Record<SparseTarget, SparsityTelemetry>> => {
  const clone: Partial<Record<SparseTarget, SparsityTelemetry>> = {};
  for (const [key, value] of Object.entries(snapshot.telemetry) as [SparseTarget, SparsityTelemetry][]) {
    clone[key] = { ...value };
  }
  return clone;
};

export const getSparsityTelemetry = (): Partial<Record<SparseTarget, SparsityTelemetry>> =>
  cloneTelemetry(resolveSnapshot());

export const getActiveIndices = (target: SparseTarget): number[] => {
  const vector = resolveSnapshot().vectors[target];
  if (!vector) {
    return [];
  }
  const indices: number[] = [];
  for (let index = 0; index < vector.length; index += 1) {
    if (vector[index] !== 0) {
      indices.push(index);
    }
  }
  return indices;
};

export const withSparsitySnapshot = <T>(
  snapshot: SparseRuntimeSnapshot | undefined,
  callback: () => T
): T => {
  const previous = activeSparseSnapshot;
  const previousDepth = activeSnapshotDepth;
  activeSparseSnapshot = snapshot ?? latestSparseSnapshot;
  activeSnapshotDepth = previousDepth + 1;
  try {
    return callback();
  } finally {
    activeSnapshotDepth = previousDepth;
    activeSparseSnapshot = previous;
  }
};

export const setLatestSparsitySnapshot = (snapshot: SparseRuntimeSnapshot | undefined): void => {
  latestSparseSnapshot = snapshot ?? EMPTY_SNAPSHOT;
  if (activeSnapshotDepth === 0) {
    activeSparseSnapshot = latestSparseSnapshot;
  }
};

const freezeCache = new WeakSet<object>();

const freezeDeep = <T>(value: T): T => {
  if (value && typeof value === 'object') {
    const obj = value as Record<string, unknown>;
    if (!freezeCache.has(obj)) {
      Object.freeze(obj);
      freezeCache.add(obj);
      for (const key of Object.keys(obj)) {
        const nested = obj[key];
        if (nested && typeof nested === 'object') {
          freezeDeep(nested);
        }
      }
    }
  }
  return value;
};

const sanitizeStrings = (input: readonly string[]): string[] => {
  const seen = new Set<string>();
  const clean: string[] = [];
  for (const entry of input) {
    if (typeof entry !== 'string') {
      continue;
    }
    const trimmed = entry.trim();
    if (!trimmed || seen.has(trimmed)) {
      continue;
    }
    seen.add(trimmed);
    clean.push(trimmed);
  }
  return clean;
};

const toDiagnostic = (
  plugin: string,
  hook: PluginDiagnostics['hook'],
  type: PluginDiagnostics['type'],
  detail?: string
): PluginDiagnostics => ({ plugin, hook, type, detail });

export class PluginHost {
  private readonly plugins: readonly PluginEntry[];
  private readonly driftSpikeThreshold: number;

  constructor(entries: readonly ReasoncoreLitePlugin[], spikeThreshold: number) {
    this.plugins = entries.map((plugin, index) => ({
      plugin,
      name: plugin.name ?? `plugin-${index + 1}`
    }));
    this.driftSpikeThreshold = spikeThreshold;
  }

  runGlyphHooks(
    context: GlyphHookContext,
    sparseState?: SparseRuntimeSnapshot
  ): PluginHostResult<string[]> {
    return withSparsitySnapshot(sparseState, () => {
      const frozen = freezeDeep({ ...context, glyphs: [...context.glyphs], context: [...context.context] });
      const diagnostics: PluginDiagnostics[] = [];
      const suggestions: string[] = [];

      for (const entry of this.plugins) {
        const hook = entry.plugin.onGlyph;
        if (!hook) {
          diagnostics.push(toDiagnostic(entry.name, 'glyph', 'skipped'));
          continue;
        }

        try {
          const result = hook(frozen);
          if (!result) {
            diagnostics.push(toDiagnostic(entry.name, 'glyph', 'skipped'));
            continue;
          }

          const additional = result.replace ? sanitizeStrings(result.replace) : sanitizeStrings(result.add ?? []);
          for (const item of additional) {
            if (suggestions.length >= context.limit) {
              break;
            }
            suggestions.push(item);
          }
          diagnostics.push(toDiagnostic(entry.name, 'glyph', 'applied'));
        } catch (error) {
          diagnostics.push(
            toDiagnostic(entry.name, 'glyph', 'error', error instanceof Error ? error.message : String(error))
          );
        }
      }

      return { value: suggestions.slice(0, context.limit), diagnostics };
    });
  }

  runEmotionHooks(
    context: EmotionHookContext,
    sparseState?: SparseRuntimeSnapshot
  ): PluginHostResult<{ deltaAdjustments: number[]; biases: number[]; labels: string[]; }> {
    return withSparsitySnapshot(sparseState, () => {
      const frozen = freezeDeep({ ...context });
      const diagnostics: PluginDiagnostics[] = [];
      const deltaAdjustments: number[] = [];
      const biases: number[] = [];
      const labels: string[] = [];

      for (const entry of this.plugins) {
        const hook = entry.plugin.onEmotion;
        if (!hook) {
          diagnostics.push(toDiagnostic(entry.name, 'emotion', 'skipped'));
          continue;
        }
        try {
          const result = hook(frozen);
          if (!result) {
            diagnostics.push(toDiagnostic(entry.name, 'emotion', 'skipped'));
            continue;
          }
          if (typeof result.delta === 'number' && Number.isFinite(result.delta)) {
            const bounded = Math.max(-1, Math.min(1, result.delta));
            deltaAdjustments.push(bounded);
          }
          if (typeof result.bias === 'number' && Number.isFinite(result.bias)) {
            const boundedBias = Math.max(-this.driftSpikeThreshold, Math.min(this.driftSpikeThreshold, result.bias));
            biases.push(boundedBias);
          }
          if (result.label) {
            labels.push(result.label);
          }
          diagnostics.push(toDiagnostic(entry.name, 'emotion', 'applied'));
        } catch (error) {
          diagnostics.push(
            toDiagnostic(entry.name, 'emotion', 'error', error instanceof Error ? error.message : String(error))
          );
        }
      }

      return { value: { deltaAdjustments, biases, labels }, diagnostics };
    });
  }

  runBloomHooks(
    context: BloomHookContext,
    sparseState?: SparseRuntimeSnapshot
  ): PluginHostResult<{ adjustments: number[]; floors: number[]; ceilings: number[]; rationales: string[]; }> {
    return withSparsitySnapshot(sparseState, () => {
      const frozen = freezeDeep({ ...context });
      const diagnostics: PluginDiagnostics[] = [];
      const adjustments: number[] = [];
      const floors: number[] = [];
      const ceilings: number[] = [];
      const rationales: string[] = [];

      for (const entry of this.plugins) {
        const hook = entry.plugin.onBloom;
        if (!hook) {
          diagnostics.push(toDiagnostic(entry.name, 'bloom', 'skipped'));
          continue;
        }
        try {
          const result = hook(frozen);
          if (!result) {
            diagnostics.push(toDiagnostic(entry.name, 'bloom', 'skipped'));
            continue;
          }
          if (typeof result.delta === 'number' && Number.isFinite(result.delta)) {
            adjustments.push(result.delta);
          }
          if (typeof result.floor === 'number' && Number.isFinite(result.floor)) {
            floors.push(result.floor);
          }
          if (typeof result.ceiling === 'number' && Number.isFinite(result.ceiling)) {
            ceilings.push(result.ceiling);
          }
          if (typeof result.rationale === 'string' && result.rationale.trim()) {
            rationales.push(result.rationale.trim());
          }
          diagnostics.push(toDiagnostic(entry.name, 'bloom', 'applied'));
        } catch (error) {
          diagnostics.push(
            toDiagnostic(entry.name, 'bloom', 'error', error instanceof Error ? error.message : String(error))
          );
        }
      }

      return { value: { adjustments, floors, ceilings, rationales }, diagnostics };
    });
  }
}

export const createPluginHost = (
  plugins: readonly ReasoncoreLitePlugin[],
  spikeThreshold: number
): PluginHost => new PluginHost(plugins, spikeThreshold);

export const createPluginFromSource = (
  source: string,
  sandbox: SandboxEvaluator
): ReasoncoreLitePlugin => {
  if (!sandbox) {
    throw new Error('Sandbox evaluator is required to load plugin sources.');
  }
  const plugin = sandbox.evaluate(source);
  return plugin;
};
