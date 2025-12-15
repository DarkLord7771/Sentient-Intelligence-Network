import {
  BloomHookContext,
  EmotionHookContext,
  GlyphHookContext,
  PluginDiagnostics,
  PluginHost,
  ReasoncoreLitePlugin,
  SandboxEvaluator,
  createPluginFromSource,
  createPluginHost,
  type SparseRuntimeSnapshot,
  type SparseTarget,
  type BaselineSparsitySnapshot,
  setLatestSparsitySnapshot
} from './plugins/api';
import {
  computeSparsityTelemetry,
  sparsifyWithPolicyResult
} from './core/sparsity/sparse_utils';
import type {
  SparsifyResult,
  SparsityPolicy,
  SparsityTelemetryExtras,
  SparsityBaselineDetails
} from './core/sparsity/sparse_utils';

type MutableSparsityTelemetryExtras = {
  -readonly [K in keyof SparsityTelemetryExtras]?: SparsityTelemetryExtras[K];
};

declare const module: { require?: (id: string) => unknown } | undefined;
declare const require: ((id: string) => unknown) | undefined;

const MAX_ITERATIONS = 8;
const DEFAULT_TIMEOUT_MS = 50;
type SparsityPolicyLoader = () => SparsityPolicy | undefined;

let defaultReasoncoreSparsityPolicyLoader: SparsityPolicyLoader | undefined;

export const setReasoncoreLiteSparsityPolicyLoader = (
  loader?: SparsityPolicyLoader
): void => {
  defaultReasoncoreSparsityPolicyLoader = loader;
};

type Range = {
  readonly min: number;
  readonly max: number;
};

type DriftClampPolicy = Range & {
  readonly spikeThreshold: number;
};

type BloomClampPolicy = Range;

type EmotionClampPolicy = Range;

type DriftPolicy = {
  readonly intensity: Range;
  readonly momentum: Range;
  readonly anchor: Range;
  readonly bias: Range;
};

type BloomPolicy = {
  readonly seeds: Range;
  readonly density: Range;
  readonly variance: Range;
};

type EmotionPolicy = {
  readonly baseline: Range;
  readonly target: Range;
};

type GlyphPolicy = {
  readonly contextuality: Range;
  readonly limit: Range;
};

export interface ReasoncoreContract {
  readonly version: string;
  readonly sparsityPolicyName: string;
  readonly maxActiveChannelsDrift?: number;
  readonly maxActiveChannelsEmotion?: number;
  readonly maxActiveGlyphs?: number;
  readonly drift: DriftPolicy;
  readonly bloom: BloomPolicy;
  readonly emotion: EmotionPolicy;
  readonly glyph: GlyphPolicy;
  readonly clampPolicy: {
    readonly drift: DriftClampPolicy;
    readonly bloom: BloomClampPolicy;
    readonly emotion: EmotionClampPolicy;
  };
  readonly prohibitedBehaviors: readonly string[];
  readonly notes?: readonly string[];
}

export interface DriftInput {
  readonly intensity: number;
  readonly momentum: number;
  readonly anchor: number;
  readonly bias: number;
}

export interface BloomInput {
  readonly seeds: number;
  readonly density: number;
  readonly variance: number;
}

export interface EmotionInput {
  readonly baseline: number;
  readonly target: number;
}

export interface GlyphInput {
  readonly contextuality: number;
  readonly limit: number;
  readonly context?: readonly string[];
}

export interface ReasoncoreLiteInput {
  readonly drift: DriftInput;
  readonly bloom: BloomInput;
  readonly emotion: EmotionInput;
  readonly glyph: GlyphInput;
}

export interface DriftResult {
  readonly value: number;
  readonly spikesFiltered: boolean;
  readonly overshootApplied: boolean;
  readonly overshootCurl: number;
  readonly iterations: number;
}

export interface BloomResult {
  readonly probability: number;
  readonly clamps: {
    readonly floor: number;
    readonly ceiling: number;
    readonly adjustments: readonly number[];
  };
  readonly rationale: readonly string[];
}

export interface GlyphResult {
  readonly suggestions: readonly string[];
  readonly diagnostics: readonly PluginDiagnostics[];
}

export interface EmotionResult {
  readonly delta: number;
  readonly resolution: 'stabilized' | 'muted' | 'amplified';
  readonly labels: readonly string[];
  readonly clampApplied: boolean;
}

export interface ReasoncoreLiteOutput {
  readonly drift: DriftResult;
  readonly bloom: BloomResult;
  readonly glyphs: GlyphResult;
  readonly emotion: EmotionResult;
  readonly diagnostics: {
    readonly contractVersion: string;
    readonly plugin: readonly PluginDiagnostics[];
  };
}

export interface ReasoncoreLiteOptions {
  readonly contract?: ReasoncoreContract;
  readonly plugins?: readonly (ReasoncoreLitePlugin | string)[];
  readonly sandbox?: SandboxEvaluator;
  readonly timeoutMs?: number;
  readonly sparsityPolicy?: SparsityPolicy;
  readonly baselineSparsity?:
    | BaselineSparsitySnapshot
    | (() => BaselineSparsitySnapshot | undefined);
}

export interface ReasoncoreLiteRuntime {
  readonly evaluate: (input: ReasoncoreLiteInput) => ReasoncoreLiteOutput;
  readonly getContract: () => ReasoncoreContract;
  readonly getPluginHost: () => PluginHost;
}

const makeRange = (min: number, max: number): Range => ({ min, max });
const UNIT_RANGE = makeRange(0, 1);

interface LimitedChannelResult {
  readonly values: number[];
  readonly vector: number[];
  readonly activeIndices: number[];
}

const limitActiveChannels = (values: readonly number[], maxActive?: number): LimitedChannelResult => {
  const length = values.length;
  if (!length) {
    return { values: [], vector: [], activeIndices: [] };
  }
  if (maxActive === undefined) {
    const vector = [...values];
    const activeIndices: number[] = [];
    vector.forEach((value, index) => {
      if (value !== 0) {
        activeIndices.push(index);
      }
    });
    return { values: [...values], vector, activeIndices };
  }
  if (maxActive <= 0) {
    return { values: [], vector: Array.from({ length }, () => 0), activeIndices: [] };
  }
  if (length <= maxActive) {
    const vector = [...values];
    const activeIndices: number[] = [];
    vector.forEach((value, index) => {
      if (value !== 0) {
        activeIndices.push(index);
      }
    });
    return { values: [...values], vector, activeIndices };
  }
  const ranked = values
    .map((value, index) => ({ value, index, magnitude: Math.abs(value) }))
    .sort((a, b) => {
      if (b.magnitude === a.magnitude) {
        return a.index - b.index;
      }
      return b.magnitude - a.magnitude;
    });
  const keep = new Set<number>();
  for (const entry of ranked) {
    keep.add(entry.index);
    if (keep.size >= maxActive) {
      break;
    }
  }
  const vector: number[] = [];
  const limitedValues: number[] = [];
  const activeIndices: number[] = [];
  values.forEach((value, index) => {
    if (keep.has(index)) {
      vector.push(value);
      limitedValues.push(value);
      if (value !== 0) {
        activeIndices.push(index);
      }
    } else {
      vector.push(0);
    }
  });
  return { values: limitedValues, vector, activeIndices };
};

const deriveVectorActiveIndices = (vector: readonly number[]): number[] => {
  const indices: number[] = [];
  vector.forEach((value, index) => {
    if (value !== 0) {
      indices.push(index);
    }
  });
  return indices;
};

const mergeSnapshotWithBaseline = (
  snapshot: SparseRuntimeSnapshot | undefined,
  baseline?: BaselineSparsitySnapshot
): SparseRuntimeSnapshot | undefined => {
  if (!baseline) {
    return snapshot;
  }
  if (!snapshot) {
    return { vectors: {}, telemetry: {}, baseline };
  }
  if (snapshot.baseline === baseline) {
    return snapshot;
  }
  return { vectors: snapshot.vectors, telemetry: snapshot.telemetry, baseline };
};

const toBaselineTelemetryDetails = (
  target: SparseTarget,
  snapshot?: BaselineSparsitySnapshot
): SparsityBaselineDetails | undefined => {
  if (!snapshot) {
    return undefined;
  }
  const vectorDetails = snapshot.targets?.[target];
  const sceneTags = vectorDetails?.sceneTags ?? snapshot.sceneTags;
  const hasMetadata =
    vectorDetails !== undefined || snapshot.tick !== undefined || (sceneTags?.length ?? 0) > 0;
  if (!hasMetadata) {
    return undefined;
  }
  return {
    density: vectorDetails?.density,
    activeIndices: vectorDetails?.activeIndices,
    tick: vectorDetails?.tick ?? snapshot.tick,
    sceneTags
  };
};

const freezeVector = (vector: readonly number[]): readonly number[] => Object.freeze(vector.slice());

const clampWeight = (value: number): number => Math.max(0.05, Math.min(1.5, value));

const deriveBloomWeights = (length: number, context?: BloomHookContext): number[] => {
  if (!length) {
    return [];
  }
  const probability = context ? clamp(context.probability, UNIT_RANGE) : 0.5;
  const density = context ? clamp(context.density, UNIT_RANGE) : 0.5;
  const variance = context ? clamp(context.variance, UNIT_RANGE) : 0.5;
  const seedRotation = context ? (context.seeds % 97) / 97 : 0.5;
  return Array.from({ length }, (_, index) => {
    const oscillator = Math.sin((index + 1) * (variance + 1) + seedRotation * Math.PI * 2);
    const weight = probability * 0.6 + (1 - density) * 0.3 + oscillator * 0.1;
    return clampWeight(weight);
  });
};

const deriveEmotionWeights = (length: number, context?: EmotionHookContext): number[] => {
  if (!length) {
    return [];
  }
  const baseline = context?.baseline ?? 0;
  const delta = context?.delta ?? 0;
  const intensity = 0.5 + 0.4 * stableTanh(delta * 1.8);
  const anchor = 0.4 + 0.3 * stableTanh(baseline);
  return Array.from({ length }, (_, index) => {
    const oscillator = Math.cos((index + 1) * 0.35 + delta * 0.5);
    const weight = intensity + anchor * 0.5 + oscillator * 0.1;
    return clampWeight(weight);
  });
};

const blendChannelWeights = (
  length: number,
  sources: readonly (readonly number[])[]
): number[] => {
  if (!length) {
    return [];
  }
  return Array.from({ length }, (_, index) => {
    let aggregate = 0;
    let count = 0;
    for (const source of sources) {
      if (source.length > index) {
        aggregate += source[index];
        count += 1;
      }
    }
    if (!count) {
      return 1;
    }
    return clampWeight(aggregate / count);
  });
};

const applyBloomUpdateGate = (
  values: readonly number[],
  bloomProbability: number,
  bloomInput: BloomInput,
  contract: ReasoncoreContract
): number[] => {
  if (!values.length) {
    return [];
  }
  const normalizedProbability = clamp(bloomProbability, UNIT_RANGE);
  const normalizedDensity = clamp(bloomInput.density, contract.bloom.density);
  const normalizedVariance = clamp(bloomInput.variance, contract.bloom.variance);
  const seedRange = contract.bloom.seeds.max - contract.bloom.seeds.min || 1;
  const normalizedSeeds =
    (clamp(bloomInput.seeds, contract.bloom.seeds) - contract.bloom.seeds.min) / seedRange;
  return values.map((value, index) => {
    if (value === 0) {
      return 0;
    }
    const oscillator = Math.sin((index + 1 + normalizedSeeds * 13) * (normalizedVariance + 1));
    const densityGate = 1 - normalizedDensity * 0.35;
    const gate = clamp(
      normalizedProbability * 0.65 + densityGate * 0.25 + oscillator * 0.1,
      UNIT_RANGE
    );
    return value * gate;
  });
};

const ensureCooldownVector = (vector: readonly number[], length: number): number[] => {
  if (vector.length >= length) {
    return vector.slice();
  }
  const next = vector.slice();
  while (next.length < length) {
    next.push(0);
  }
  return next;
};

const applyCooldownToValues = (
  values: readonly number[],
  cooldowns: readonly number[]
): { values: number[]; snapshot: number[] } => {
  const snapshot: number[] = [];
  const cooledValues = values.map((value, index) => {
    const penalty = clamp(cooldowns[index] ?? 0, UNIT_RANGE);
    snapshot.push(penalty);
    if (penalty === 0) {
      return value;
    }
    const gate = 1 - penalty;
    return value * gate;
  });
  return { values: cooledValues, snapshot };
};

const updateCooldownTimers = (
  current: readonly number[],
  activeIndices: readonly number[],
  driftValue: number
): number[] => {
  const normalizedDrift = Math.min(1, Math.abs(driftValue));
  const decay = 0.05 + normalizedDrift * 0.15;
  const spike = 0.25 + normalizedDrift * 0.5;
  const next = current.map((value) => Math.max(0, value - decay));
  for (const index of activeIndices) {
    if (index >= next.length) {
      next[index] = 0;
    }
    next[index] = Math.min(1, (next[index] ?? 0) + spike);
  }
  return next;
};

const computeDecisionPulse = (vector: readonly number[]): number[] => {
  if (!vector.length) {
    return [];
  }
  const magnitudes = vector.map((value) => Math.abs(value));
  const total = magnitudes.reduce((acc, value) => acc + value, 0);
  if (!total) {
    return Array.from({ length: vector.length }, () => 0);
  }
  const normalized = magnitudes.map((value) => value / total);
  const entropy = normalized.reduce((acc, value) => (value ? acc - value * Math.log(value) : acc), 0);
  const maxEntropy = Math.log(Math.max(1, vector.length));
  const entropyNorm = maxEntropy > 0 ? Math.min(1, entropy / maxEntropy) : 0;
  const pulseScale = 1 - entropyNorm;
  return normalized.map((value) => value * pulseScale);
};

const toTelemetryExtras = (
  maxActive: number | undefined,
  activeCount: number,
  extras?: {
    readonly weights?: readonly number[];
    readonly cooldowns?: readonly number[];
    readonly decisionPulse?: readonly number[];
    readonly baseline?: SparsityBaselineDetails;
    readonly liveActiveIndices?: readonly number[];
  }
): SparsityTelemetryExtras | undefined => {
  const payload: MutableSparsityTelemetryExtras = {};
  if (maxActive !== undefined) {
    payload.heldChannels = Math.max(0, maxActive - activeCount);
  }
  if (extras?.weights?.length) {
    payload.channelWeights = extras.weights.slice();
  }
  if (extras?.cooldowns?.length) {
    payload.channelCooldowns = extras.cooldowns.slice();
  }
  if (extras?.decisionPulse?.length) {
    payload.decisionPulse = extras.decisionPulse.slice();
  }
  if (extras?.baseline) {
    payload.baseline = extras.baseline;
  }
  if (extras?.liveActiveIndices?.length) {
    payload.liveActiveIndices = extras.liveActiveIndices.slice();
  }
  if (Object.keys(payload).length === 0) {
    return undefined;
  }
  return payload;
};

const GLYPH_SPARSE_POLICY_NAME = 'reasoncore-lite-glyph-limit';

const limitGlyphSuggestions = (suggestions: readonly string[], limit?: number): string[] => {
  if (limit === undefined) {
    return [...suggestions];
  }
  if (limit <= 0) {
    return [];
  }
  return suggestions.slice(0, limit);
};

export const DEFAULT_CONTRACT: ReasoncoreContract = {
  version: '1.0.0',
  sparsityPolicyName: 'reasoncore-lite-default',
  maxActiveChannelsDrift: 4,
  maxActiveChannelsEmotion: 6,
  maxActiveGlyphs: 3,
  drift: {
    intensity: makeRange(-1, 1),
    momentum: makeRange(-8, 8),
    anchor: makeRange(0, 1),
    bias: makeRange(-0.5, 0.5)
  },
  bloom: {
    seeds: makeRange(0, 512),
    density: makeRange(0, 1),
    variance: makeRange(0, 1)
  },
  emotion: {
    baseline: makeRange(-1, 1),
    target: makeRange(-1, 1)
  },
  glyph: {
    contextuality: makeRange(0, 1),
    limit: makeRange(1, 8)
  },
  clampPolicy: {
    drift: { ...makeRange(-1, 1), spikeThreshold: 0.08 },
    bloom: makeRange(0, 0.97),
    emotion: makeRange(-1, 1)
  },
  prohibitedBehaviors: ['drift-recursion', 'collapse-triggers', 'seal-imports'],
  notes: [
    'Calculations must resolve within 8 iterations without recursion.',
    'Plugins may only annotate results; state mutability is prohibited.',
    'Bloom probability remains bounded regardless of plugin deltas.'
  ]
};

const clamp = (value: number, range: Range): number => {
  if (!Number.isFinite(value)) {
    return range.min;
  }
  return Math.max(range.min, Math.min(range.max, value));
};

const average = (values: readonly number[]): number => {
  if (!values.length) {
    return 0;
  }
  const sum = values.reduce((acc, value) => acc + value, 0);
  return sum / values.length;
};

const stableTanh = (value: number): number => {
  if (value === 0) {
    return 0;
  }
  const limit = value > 0 ? Math.min(value, 6) : Math.max(value, -6);
  const exp = Math.exp(2 * limit);
  return (exp - 1) / (exp + 1);
};

const computeDrift = (
  input: DriftInput,
  contract: ReasoncoreContract,
  pluginBias: number
): DriftResult => {
  const driftClamp = contract.clampPolicy.drift;
  let driftValue = 0;
  let spikesFiltered = false;
  let overshootApplied = false;
  let overshootCurl = 0;

  const normalizedBias = clamp(input.bias + pluginBias, contract.drift.bias);
  const normalizedAnchor = clamp(input.anchor, contract.drift.anchor);
  const normalizedMomentum = clamp(input.momentum, contract.drift.momentum);
  const normalizedIntensity = clamp(input.intensity, contract.drift.intensity);

  for (let iteration = 0; iteration < MAX_ITERATIONS; iteration += 1) {
    const blend = 1 - normalizedAnchor;
    const projected = normalizedIntensity * blend + normalizedMomentum * 0.05 + normalizedBias;
    const clamped = clamp(projected, driftClamp);
    const delta = projected - clamped;
    if (Math.abs(delta) > driftClamp.spikeThreshold) {
      spikesFiltered = true;
      overshootApplied = true;
      overshootCurl = -delta * 0.25;
      driftValue = clamp(clamped + overshootCurl, driftClamp);
    } else {
      driftValue = clamped;
    }

    if (Math.abs(delta) <= driftClamp.spikeThreshold || iteration === MAX_ITERATIONS - 1) {
      return {
        value: driftValue,
        spikesFiltered,
        overshootApplied,
        overshootCurl,
        iterations: iteration + 1
      };
    }
  }

  return {
    value: clamp(driftValue, driftClamp),
    spikesFiltered,
    overshootApplied,
    overshootCurl,
    iterations: MAX_ITERATIONS
  };
};

const computeBloomProbability = (
  input: BloomInput,
  contract: ReasoncoreContract,
  drift: DriftResult,
  adjustments: readonly number[],
  floors: readonly number[],
  ceilings: readonly number[]
): BloomResult => {
  const seeds = clamp(input.seeds, contract.bloom.seeds);
  const density = clamp(input.density, contract.bloom.density);
  const variance = clamp(input.variance, contract.bloom.variance);

  const normalizedSeeds = seeds / contract.bloom.seeds.max;
  const driftInfluence = 0.2 * stableTanh(drift.value * 2);
  const baseProbability = Math.abs(
    0.42 * normalizedSeeds +
      0.38 * density +
      0.2 * Math.sqrt(variance + 1e-6) +
      driftInfluence
  );

  const aggregatedAdjustment = adjustments.reduce((acc, value) => acc + value, 0);
  const contractBloom = contract.clampPolicy.bloom;
  const pluginFloor = floors.length ? Math.max(...floors) : contractBloom.min;
  const pluginCeiling = ceilings.length ? Math.min(...ceilings) : contractBloom.max;

  const normalizedFloor = Math.max(contractBloom.min, Math.min(contractBloom.max, pluginFloor));
  const normalizedCeiling = Math.max(contractBloom.min, Math.min(contractBloom.max, pluginCeiling));
  const envelopeFloor = Math.min(normalizedFloor, normalizedCeiling);
  const envelopeCeiling = Math.max(normalizedFloor, normalizedCeiling);

  const boundedProbability = clamp(baseProbability + aggregatedAdjustment, {
    min: envelopeFloor,
    max: envelopeCeiling
  });

  return {
    probability: boundedProbability,
    clamps: {
      floor: envelopeFloor,
      ceiling: envelopeCeiling,
      adjustments
    },
    rationale: adjustments.length ? ['plugin-adjustment'] : []
  };
};

const resolveEmotionDelta = (
  input: EmotionInput,
  contract: ReasoncoreContract,
  adjustments: readonly number[],
  labels: readonly string[]
): EmotionResult => {
  const baseline = clamp(input.baseline, contract.emotion.baseline);
  const target = clamp(input.target, contract.emotion.target);
  const rawDelta = target - baseline + adjustments.reduce((acc, value) => acc + value, 0);
  const boundedDelta = clamp(rawDelta, contract.clampPolicy.emotion);
  const magnitude = Math.abs(boundedDelta);
  const clampApplied = boundedDelta !== rawDelta;

  const resolution: EmotionResult['resolution'] =
    magnitude < 0.12 ? 'stabilized' : magnitude < 0.45 ? 'muted' : 'amplified';

  return {
    delta: boundedDelta,
    resolution,
    labels,
    clampApplied
  };
};

const BASE_GLYPHS = [
  'solace',
  'ember',
  'lumen',
  'veil',
  'pulse',
  'echo',
  'strand',
  'harbor'
];

const suggestGlyphs = (
  input: GlyphInput,
  contract: ReasoncoreContract,
  pluginSuggestions: readonly string[]
): GlyphResult => {
  const contextuality = clamp(input.contextuality, contract.glyph.contextuality);
  const limit = Math.round(clamp(input.limit, contract.glyph.limit));
  const context = input.context ? [...input.context] : [];

  const normalizedContext = context
    .filter((item) => typeof item === 'string' && item.trim())
    .map((item) => item.trim());

  const baseGlyphs = [...BASE_GLYPHS];
  if (normalizedContext.length) {
    baseGlyphs.unshift(...normalizedContext);
  }

  const unique = new Set<string>();
  const selections: string[] = [];

  const allCandidates = [...pluginSuggestions, ...baseGlyphs];
  for (const glyph of allCandidates) {
    if (selections.length >= limit) {
      break;
    }
    if (!glyph || unique.has(glyph)) {
      continue;
    }
    const weight = normalizedContext.includes(glyph) ? 0.85 : contextuality;
    if (weight >= 0.2 || pluginSuggestions.includes(glyph)) {
      unique.add(glyph);
      selections.push(glyph);
    }
  }

  return {
    suggestions: selections.slice(0, limit),
    diagnostics: []
  };
};

const toGlyphContext = (glyphs: readonly string[], glyphInput: GlyphInput): GlyphHookContext => ({
  glyphs,
  context: glyphInput.context ?? [],
  limit: Math.round(glyphInput.limit)
});

const toEmotionContext = (emotion: EmotionInput, delta: number): EmotionHookContext => ({
  baseline: emotion.baseline,
  delta
});

const toBloomContext = (probability: number, bloom: BloomInput): BloomHookContext => ({
  probability,
  seeds: bloom.seeds,
  density: bloom.density,
  variance: bloom.variance
});

const optionalRequire = (moduleId: string): unknown => {
  try {
    if (typeof module !== 'undefined' && typeof module.require === 'function') {
      return module.require(moduleId);
    }
  } catch (error) {
    if (!(error instanceof Error)) {
      throw error;
    }
  }
  try {
    if (typeof require === 'function') {
      return require(moduleId);
    }
  } catch (error) {
    if (!(error instanceof Error)) {
      throw error;
    }
  }
  return undefined;
};

export const createSandboxEvaluator = (timeoutMs = DEFAULT_TIMEOUT_MS): SandboxEvaluator => {
  const vm2: { VM: new (config: Record<string, unknown>) => { run: (code: string) => unknown; setGlobal: (name: string, value: unknown) => unknown } } | undefined =
    optionalRequire('vm2') as never;
  if (vm2 && typeof vm2.VM === 'function') {
    return {
      evaluate: (code: string) => {
        const vm = new vm2.VM({
          timeout: timeoutMs,
          sandbox: {
            module: { exports: {} },
            exports: {},
            globalThis: {}
          },
          eval: false,
          wasm: false,
          allowAsync: false
        });

        vm.run(`"use strict";\n${code}\n;globalThis.__plugin = module.exports || exports.default || exports;`);
        let pluginName: unknown;
        try {
          pluginName = vm.run(
            `(function(){ const plugin = globalThis.__plugin; return plugin && plugin.name; })()`
          );
        } catch (error) {
          pluginName = undefined;
        }

        const callHook = (
          hook: 'onGlyph' | 'onEmotion' | 'onBloom',
          context: unknown
        ): unknown => {
          vm.setGlobal('__hookContext', context);
          try {
            return vm.run(
              `(function(){ const plugin = globalThis.__plugin; const hook = plugin && plugin.${hook}; return typeof hook === 'function' ? hook(__hookContext) : undefined; })()`
            );
          } finally {
            vm.setGlobal('__hookContext', undefined);
          }
        };

        const wrapped: ReasoncoreLitePlugin = {
          name: typeof pluginName === 'string' ? pluginName : undefined,
          onGlyph: (context) => callHook('onGlyph', context) as ReturnType<NonNullable<ReasoncoreLitePlugin['onGlyph']>>,
          onEmotion: (context) => callHook('onEmotion', context) as ReturnType<NonNullable<ReasoncoreLitePlugin['onEmotion']>>,
          onBloom: (context) => callHook('onBloom', context) as ReturnType<NonNullable<ReasoncoreLitePlugin['onBloom']>>
        };

        return wrapped;
      }
    };
  }

  return {
    evaluate: () => {
      throw new Error('Sandbox runtime is unavailable in this environment.');
    }
  };
};

const ensurePluginHost = (
  plugins: readonly (ReasoncoreLitePlugin | string)[],
  sandbox: SandboxEvaluator,
  spikeThreshold: number
): PluginHost => {
  const resolved: ReasoncoreLitePlugin[] = [];
  for (const entry of plugins) {
    if (typeof entry === 'string') {
      resolved.push(createPluginFromSource(entry, sandbox));
    } else {
      resolved.push(entry);
    }
  }
  return createPluginHost(resolved, spikeThreshold);
};

const validateContract = (contract: ReasoncoreContract): ReasoncoreContract => {
  if (contract.prohibitedBehaviors.some((item) => item === 'drift-recursion') === false) {
    throw new Error('Contract must explicitly prohibit drift recursion.');
  }
  return contract;
};

export const createReasoncoreLite = (options: ReasoncoreLiteOptions = {}): ReasoncoreLiteRuntime => {
  const contract = validateContract(options.contract ?? DEFAULT_CONTRACT);
  const sandbox = options.sandbox ?? createSandboxEvaluator(options.timeoutMs ?? DEFAULT_TIMEOUT_MS);
  const pluginHost = ensurePluginHost(options.plugins ?? [], sandbox, contract.clampPolicy.drift.spikeThreshold);
  const sparsityPolicy = options.sparsityPolicy ?? defaultReasoncoreSparsityPolicyLoader?.();
  const baselineOption = options.baselineSparsity;
  const baselineSnapshotResolver: (() => BaselineSparsitySnapshot | undefined) | undefined =
    typeof baselineOption === 'function'
      ? baselineOption
      : baselineOption
        ? () => baselineOption
        : undefined;

  const applyReasoncoreSparsityResult = (
    values: readonly number[],
    weights?: readonly number[]
  ): SparsifyResult => {
    if (!values.length) {
      return { mask: [], values: [] };
    }
    if (!sparsityPolicy) {
      const mask = values.map(() => true);
      return {
        mask,
        values: [...values]
      };
    }
    const weightedValues = weights
      ? values.map((value, index) => value * (weights[index] ?? 1))
      : values;
    const result = sparsifyWithPolicyResult(weightedValues, sparsityPolicy);
    if (!weights) {
      return result;
    }
    const rematerialized = values.map((value, index) => (result.mask[index] ? value : 0));
    return {
      mask: result.mask,
      values: rematerialized
    };
  };

  const applyReasoncoreSparsity = (values: readonly number[], weights?: readonly number[]): number[] =>
    applyReasoncoreSparsityResult(values, weights).values;

  let sparseSnapshot: SparseRuntimeSnapshot | undefined;
  let driftCooldowns: number[] = [];
  let emotionCooldowns: number[] = [];

  const evaluate = (input: ReasoncoreLiteInput): ReasoncoreLiteOutput => {
    const driftBias = 0;
    const drift = computeDrift(input.drift, contract, driftBias);

    const baselineSnapshot = baselineSnapshotResolver?.();
    const hookSnapshot = mergeSnapshotWithBaseline(sparseSnapshot, baselineSnapshot);

    const glyphContext = toGlyphContext([], input.glyph);
    const glyphPlugins = pluginHost.runGlyphHooks(glyphContext, hookSnapshot);

    const bloomBase = computeBloomProbability(input.bloom, contract, drift, [], [], []);
    const bloomContext = toBloomContext(bloomBase.probability, input.bloom);
    const bloomPlugins = pluginHost.runBloomHooks(bloomContext, hookSnapshot);
    const bloomAdjustmentWeights = deriveBloomWeights(bloomPlugins.value.adjustments.length, bloomContext);
    const sparseBloomAdjustments = applyReasoncoreSparsity(
      bloomPlugins.value.adjustments,
      bloomAdjustmentWeights
    );
    const bloomFloorWeights = deriveBloomWeights(bloomPlugins.value.floors.length, bloomContext);
    const sparseBloomFloors = applyReasoncoreSparsity(bloomPlugins.value.floors, bloomFloorWeights);
    const bloomCeilingWeights = deriveBloomWeights(bloomPlugins.value.ceilings.length, bloomContext);
    const sparseBloomCeilingResult = applyReasoncoreSparsityResult(
      bloomPlugins.value.ceilings,
      bloomCeilingWeights
    );
    const sparseBloomCeilings = bloomPlugins.value.ceilings.filter(
      (_, index) => sparseBloomCeilingResult.mask[index]
    );
    const bloom = computeBloomProbability(
      input.bloom,
      contract,
      drift,
      sparseBloomAdjustments,
      sparseBloomFloors,
      sparseBloomCeilings
    );
    const clampRange = contract.clampPolicy.bloom;
    const finalBloomProbability = clamp(bloom.probability, clampRange);
    const clampChanged = !Number.isFinite(bloom.probability) || finalBloomProbability !== bloom.probability;
    const clampBoundaryHit =
      finalBloomProbability === clampRange.min || finalBloomProbability === clampRange.max;
    const bloomFinal =
      clampChanged || clampBoundaryHit
        ? {
            ...bloom,
            probability: finalBloomProbability,
            rationale: bloom.rationale.includes('clamp-enforced')
              ? bloom.rationale
              : [...bloom.rationale, 'clamp-enforced']
          }
        : bloom;

    const emotionContext = toEmotionContext(input.emotion, bloomFinal.probability - 0.5);
    const emotionPlugins = pluginHost.runEmotionHooks(emotionContext, hookSnapshot);
    const emotionBiasWeights = deriveEmotionWeights(emotionPlugins.value.biases.length, emotionContext);
    const bloomBiasWeights = deriveBloomWeights(emotionPlugins.value.biases.length, bloomContext);
    const biasWeights = blendChannelWeights(emotionPlugins.value.biases.length, [
      emotionBiasWeights,
      bloomBiasWeights
    ]);
    const biasSparsityResult = applyReasoncoreSparsityResult(
      emotionPlugins.value.biases,
      biasWeights
    );
    const bloomAwareBiases = applyBloomUpdateGate(
      biasSparsityResult.values,
      bloomFinal.probability,
      input.bloom,
      contract
    );
    driftCooldowns = ensureCooldownVector(driftCooldowns, bloomAwareBiases.length);
    const cooledBiases = applyCooldownToValues(bloomAwareBiases, driftCooldowns);
    const driftCooldownSnapshot = cooledBiases.snapshot;
    const limitedBiases = limitActiveChannels(cooledBiases.values, contract.maxActiveChannelsDrift);
    driftCooldowns = updateCooldownTimers(driftCooldowns, limitedBiases.activeIndices, drift.value);
    const pluginBias = average(limitedBiases.values);
    const driftGuarded = computeDrift(input.drift, contract, pluginBias);

    const emotionDeltaWeights = deriveEmotionWeights(
      emotionPlugins.value.deltaAdjustments.length,
      emotionContext
    );
    const bloomEmotionWeights = deriveBloomWeights(
      emotionPlugins.value.deltaAdjustments.length,
      bloomContext
    );
    const emotionWeights = blendChannelWeights(emotionPlugins.value.deltaAdjustments.length, [
      emotionDeltaWeights,
      bloomEmotionWeights
    ]);
    const emotionAdjustmentResult = applyReasoncoreSparsityResult(
      emotionPlugins.value.deltaAdjustments,
      emotionWeights
    );
    const bloomAwareEmotionAdjustments = applyBloomUpdateGate(
      emotionAdjustmentResult.values,
      bloomFinal.probability,
      input.bloom,
      contract
    );
    emotionCooldowns = ensureCooldownVector(
      emotionCooldowns,
      bloomAwareEmotionAdjustments.length
    );
    const cooledEmotionAdjustments = applyCooldownToValues(
      bloomAwareEmotionAdjustments,
      emotionCooldowns
    );
    const emotionCooldownSnapshot = cooledEmotionAdjustments.snapshot;
    const limitedEmotionAdjustments = limitActiveChannels(
      cooledEmotionAdjustments.values,
      contract.maxActiveChannelsEmotion
    );
    emotionCooldowns = updateCooldownTimers(
      emotionCooldowns,
      limitedEmotionAdjustments.activeIndices,
      drift.value
    );
    const emotion = resolveEmotionDelta(
      input.emotion,
      contract,
      limitedEmotionAdjustments.values,
      emotionPlugins.value.labels
    );

    const pluginGlyphs = limitGlyphSuggestions(glyphPlugins.value, contract.maxActiveGlyphs);
    const glyphs = suggestGlyphs(input.glyph, contract, pluginGlyphs);
    const finalGlyphSuggestions = contract.maxActiveGlyphs === undefined
      ? glyphs.suggestions
      : glyphs.suggestions.slice(0, contract.maxActiveGlyphs);
    const diagnostics = [
      ...glyphPlugins.diagnostics,
      ...bloomPlugins.diagnostics,
      ...emotionPlugins.diagnostics
    ];

    const driftVector = freezeVector(limitedBiases.vector);
    const emotionVector = freezeVector(limitedEmotionAdjustments.vector);
    const glyphActivationVector = glyphPlugins.value.map((_, index) =>
      index < pluginGlyphs.length ? 1 : 0
    );
    const gatedGlyphVector = applyReasoncoreSparsity(glyphActivationVector);
    const glyphVector = freezeVector(gatedGlyphVector);
    const driftPulse = computeDecisionPulse(driftVector);
    const emotionPulse = computeDecisionPulse(emotionVector);
    const glyphPulse = computeDecisionPulse(glyphVector);

    const baselineDetails = {
      drift: toBaselineTelemetryDetails('drift', baselineSnapshot),
      emotion: toBaselineTelemetryDetails('emotion', baselineSnapshot),
      glyph: toBaselineTelemetryDetails('glyph', baselineSnapshot)
    };
    const glyphActiveIndices = deriveVectorActiveIndices(gatedGlyphVector);

    const nextSnapshot: SparseRuntimeSnapshot = {
      vectors: {
        drift: driftVector,
        emotion: emotionVector,
        glyph: glyphVector
      },
      telemetry: {
        drift: computeSparsityTelemetry(
          driftVector,
          contract.sparsityPolicyName,
          'drift',
          toTelemetryExtras(contract.maxActiveChannelsDrift, limitedBiases.activeIndices.length, {
            weights: biasWeights,
            cooldowns: driftCooldownSnapshot,
            decisionPulse: driftPulse,
            baseline: baselineDetails.drift,
            liveActiveIndices: limitedBiases.activeIndices
          })
        ),
        emotion: computeSparsityTelemetry(
          emotionVector,
          contract.sparsityPolicyName,
          'emotion',
          toTelemetryExtras(
            contract.maxActiveChannelsEmotion,
            limitedEmotionAdjustments.activeIndices.length,
            {
              weights: emotionWeights,
              cooldowns: emotionCooldownSnapshot,
              decisionPulse: emotionPulse,
              baseline: baselineDetails.emotion,
              liveActiveIndices: limitedEmotionAdjustments.activeIndices
            }
          )
        ),
        glyph: computeSparsityTelemetry(
          glyphVector,
          GLYPH_SPARSE_POLICY_NAME,
          'glyph',
          toTelemetryExtras(contract.maxActiveGlyphs, finalGlyphSuggestions.length, {
            decisionPulse: glyphPulse,
            baseline: baselineDetails.glyph,
            liveActiveIndices: glyphActiveIndices
          })
        )
      },
      baseline: baselineSnapshot
    };

    sparseSnapshot = nextSnapshot;
    setLatestSparsitySnapshot(nextSnapshot);

    return {
      drift: driftGuarded,
      bloom: bloomFinal,
      glyphs: {
        suggestions: finalGlyphSuggestions,
        diagnostics
      },
      emotion,
      diagnostics: {
        contractVersion: contract.version,
        plugin: diagnostics
      }
    };
  };

  return {
    evaluate,
    getContract: () => contract,
    getPluginHost: () => pluginHost
  };
};

export type {
  SandboxEvaluator,
  ReasoncoreLitePlugin,
  PluginDiagnostics,
  BaselineSparsitySnapshot,
  BaselineSparsityVector
} from './plugins/api';
export { getSparsityTelemetry, getActiveIndices } from './plugins/api';

export default createReasoncoreLite;
