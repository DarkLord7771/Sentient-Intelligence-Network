export interface SparsityPolicyWindow {
  readonly duration: number;
  readonly stride: number;
}

export interface SparsityPolicyMetadata {
  readonly owner?: string;
  readonly contact?: string;
  readonly notes?: string;
}

export interface SparsityPolicy {
  readonly version: "1.0";
  readonly preset?: string;
  readonly target: string;
  readonly mode: "topk" | "threshold" | "block";
  readonly k?: number;
  readonly threshold?: number;
  readonly blockSize?: number;
  readonly maxActiveFraction?: number;
  readonly minActiveFraction?: number;
  readonly seed?: number;
  readonly window?: SparsityPolicyWindow;
  readonly metadata?: SparsityPolicyMetadata;
  readonly annotations?: readonly string[];
}

export interface SparsifyOptions {
  readonly keepMagnitude?: boolean;
}

export interface SparsifyResult {
  readonly mask: boolean[];
  readonly values: number[];
}

export interface SparsityTelemetry {
  readonly density: number;
  readonly activeCount: number;
  readonly vectorLength: number;
  readonly target: string;
  readonly policyName: string;
  readonly heldChannels: number;
  readonly stabilityWindowMs: number;
  readonly stabilityHoldMsRemaining: number;
  readonly channelWeights: readonly number[];
  readonly channelCooldowns: readonly number[];
  readonly decisionPulse: readonly number[];
  readonly baselineDensity?: number;
  readonly densityDeltaFromBaseline?: number;
  readonly baselineActiveCount?: number;
  readonly activeDeltaFromBaseline?: number;
  readonly missingBaselineActivations?: number;
  readonly unexpectedActivations?: number;
  readonly baselineSceneTags: readonly string[];
  readonly baselineTick?: number;
}

export interface SparsityTelemetryExtras {
  readonly heldChannels?: number;
  readonly stabilityWindowMs?: number;
  readonly stabilityHoldMsRemaining?: number;
  readonly channelWeights?: readonly number[];
  readonly channelCooldowns?: readonly number[];
  readonly decisionPulse?: readonly number[];
  readonly baseline?: SparsityBaselineDetails;
  readonly liveActiveIndices?: readonly number[];
}

export interface SparsityBaselineDetails {
  readonly density?: number;
  readonly activeIndices?: readonly number[];
  readonly tick?: number;
  readonly sceneTags?: readonly string[];
}

interface RankedEntry {
  readonly index: number;
  readonly magnitude: number;
  readonly tieBreaker: number;
}

const DEFAULT_THRESHOLD = 0;

const pseudoRandom = (index: number, seed = 0): number => {
  const value = Math.sin(seed + index * 374761393);
  return value - Math.floor(value);
};

const rankEntries = (values: readonly number[], seed = 0): RankedEntry[] =>
  values.map((value, index) => ({
    index,
    magnitude: Math.abs(value),
    tieBreaker: pseudoRandom(index, seed)
  })).sort((a, b) => {
    if (b.magnitude === a.magnitude) {
      return b.tieBreaker - a.tieBreaker;
    }
    return b.magnitude - a.magnitude;
  });

const materializeValues = (
  values: readonly number[],
  mask: readonly boolean[],
  keepMagnitude: boolean
): number[] =>
  values.map((value, index) => {
    if (!mask[index]) {
      return 0;
    }
    if (keepMagnitude) {
      return value;
    }
    const sign = Math.sign(value);
    return sign === 0 ? 0 : sign;
  });

const emptyResult = (length: number): SparsifyResult => ({
  mask: Array.from({ length }, () => false),
  values: Array.from({ length }, () => 0)
});

const deriveActiveIndices = (vector: readonly number[]): number[] => {
  const indices: number[] = [];
  for (let index = 0; index < vector.length; index += 1) {
    if (vector[index] !== 0) {
      indices.push(index);
    }
  }
  return indices;
};

const sanitizeSceneTags = (tags: readonly string[] | undefined): string[] => {
  if (!tags || !tags.length) {
    return [];
  }
  const seen = new Set<string>();
  for (const tag of tags) {
    if (typeof tag !== 'string') {
      continue;
    }
    const trimmed = tag.trim();
    if (!trimmed) {
      continue;
    }
    seen.add(trimmed);
  }
  return Array.from(seen).sort();
};

const sanitizeActiveIndices = (indices: readonly number[] | undefined): number[] | undefined => {
  if (!indices || !indices.length) {
    return undefined;
  }
  const seen = new Set<number>();
  for (const entry of indices) {
    if (typeof entry !== 'number' || !Number.isFinite(entry)) {
      continue;
    }
    const normalized = Math.max(0, Math.trunc(entry));
    seen.add(normalized);
  }
  if (!seen.size) {
    return undefined;
  }
  return Array.from(seen).sort((a, b) => a - b);
};

export const computeSparsityTelemetry = (
  vector: readonly number[],
  policyName: string,
  target: string,
  extras: SparsityTelemetryExtras = {}
): SparsityTelemetry => {
  const vectorLength = vector.length;
  const activeCount = vector.reduce(
    (total, value) => total + (value !== 0 ? 1 : 0),
    0
  );
  const vectorDensity = vectorLength ? activeCount / vectorLength : 0;
  const liveActiveIndices = extras.liveActiveIndices
    ? extras.liveActiveIndices.slice()
    : deriveActiveIndices(vector);
  const baselineSceneTags = sanitizeSceneTags(extras.baseline?.sceneTags);
  const baselineActiveIndices = sanitizeActiveIndices(extras.baseline?.activeIndices);
  const baselineActiveCount = baselineActiveIndices?.length;
  const baselineDensity =
    typeof extras.baseline?.density === 'number' && Number.isFinite(extras.baseline.density)
      ? extras.baseline.density
      : undefined;
  const densityDelta =
    baselineDensity !== undefined ? vectorDensity - baselineDensity : undefined;
  const activeDelta =
    baselineActiveCount !== undefined ? activeCount - baselineActiveCount : undefined;
  let missingBaselineActivations: number | undefined;
  let unexpectedActivations: number | undefined;
  if (baselineActiveIndices && baselineActiveIndices.length) {
    const baselineSet = new Set(baselineActiveIndices);
    const liveSet = new Set(liveActiveIndices);
    missingBaselineActivations = 0;
    for (const index of baselineSet) {
      if (!liveSet.has(index)) {
        missingBaselineActivations += 1;
      }
    }
    unexpectedActivations = 0;
    for (const index of liveSet) {
      if (!baselineSet.has(index)) {
        unexpectedActivations += 1;
      }
    }
  }
  return {
    density: vectorDensity,
    activeCount,
    vectorLength,
    target,
    policyName,
    heldChannels: extras.heldChannels ?? 0,
    stabilityWindowMs: extras.stabilityWindowMs ?? 0,
    stabilityHoldMsRemaining: Math.max(0, extras.stabilityHoldMsRemaining ?? 0),
    channelWeights: extras.channelWeights ? extras.channelWeights.slice() : [],
    channelCooldowns: extras.channelCooldowns ? extras.channelCooldowns.slice() : [],
    decisionPulse: extras.decisionPulse ? extras.decisionPulse.slice() : [],
    baselineDensity,
    densityDeltaFromBaseline: densityDelta,
    baselineActiveCount,
    activeDeltaFromBaseline: activeDelta,
    missingBaselineActivations,
    unexpectedActivations,
    baselineSceneTags,
    baselineTick: extras.baseline?.tick
  };
};

const countActive = (mask: readonly boolean[]): number =>
  mask.reduce((total, flag) => total + (flag ? 1 : 0), 0);

const selectTopKMask = (
  values: readonly number[],
  k: number,
  ranked: readonly RankedEntry[],
  threshold: number | undefined
): boolean[] => {
  const limit = Math.min(values.length, Math.max(0, k));
  const mask = Array.from({ length: values.length }, () => false);
  if (!limit) {
    return mask;
  }
  let selected = 0;
  for (const entry of ranked) {
    if (selected >= limit) {
      break;
    }
    if (threshold !== undefined && entry.magnitude < threshold) {
      continue;
    }
    if (!mask[entry.index]) {
      mask[entry.index] = true;
      selected += 1;
    }
  }
  return mask;
};

const selectThresholdMask = (
  values: readonly number[],
  threshold: number
): boolean[] =>
  values.map((value) => Math.abs(value) >= threshold);

const selectBlockMask = (
  values: readonly number[],
  blockSize: number,
  threshold: number
): boolean[] => {
  const length = values.length;
  const mask = Array.from({ length }, () => false);
  if (!length) {
    return mask;
  }
  const normalizedBlockSize = Math.max(1, blockSize);
  for (let offset = 0; offset < length; offset += normalizedBlockSize) {
    let aggregate = 0;
    let count = 0;
    for (let index = offset; index < Math.min(length, offset + normalizedBlockSize); index += 1) {
      aggregate += Math.abs(values[index]);
      count += 1;
    }
    const average = count ? aggregate / count : 0;
    if (average >= threshold) {
      for (let index = offset; index < Math.min(length, offset + normalizedBlockSize); index += 1) {
        mask[index] = true;
      }
    }
  }
  return mask;
};

const cloneMask = (mask: readonly boolean[]): boolean[] => mask.slice();

const enforceFractions = (
  mask: boolean[],
  ranked: readonly RankedEntry[],
  policy: SparsityPolicy
): void => {
  const length = mask.length;
  if (!length) {
    return;
  }
  if (policy.maxActiveFraction !== undefined) {
    const limitRaw = Math.ceil(length * policy.maxActiveFraction);
    const limit = policy.maxActiveFraction === 0 ? 0 : Math.max(0, limitRaw);
    const active = countActive(mask);
    if (limit === 0) {
      for (let index = 0; index < mask.length; index += 1) {
        mask[index] = false;
      }
    } else if (active > limit) {
      const trimmed = Array.from({ length: mask.length }, () => false);
      let kept = 0;
      for (const entry of ranked) {
        if (!mask[entry.index]) {
          continue;
        }
        trimmed[entry.index] = true;
        kept += 1;
        if (kept >= limit) {
          break;
        }
      }
      for (let index = 0; index < mask.length; index += 1) {
        mask[index] = trimmed[index];
      }
    }
  }
  if (policy.minActiveFraction !== undefined) {
    const required = Math.max(0, Math.ceil(length * policy.minActiveFraction));
    const target = Math.min(required, length);
    let active = countActive(mask);
    if (target >= length) {
      for (let index = 0; index < mask.length; index += 1) {
        mask[index] = true;
      }
      return;
    }
    if (active < target) {
      for (const entry of ranked) {
        if (mask[entry.index]) {
          continue;
        }
        mask[entry.index] = true;
        active += 1;
        if (active >= target) {
          break;
        }
      }
    }
  }
};

export const density = (values: readonly number[]): number => {
  if (!values.length) {
    return 0;
  }
  const active = values.reduce((total, value) => total + (value !== 0 ? 1 : 0), 0);
  return active / values.length;
};

export const applyTopK = (
  values: readonly number[],
  k: number,
  options: SparsifyOptions & { readonly threshold?: number; readonly seed?: number } = {}
): SparsifyResult => {
  if (!values.length) {
    return emptyResult(0);
  }
  const ranked = rankEntries(values, options.seed);
  const mask = selectTopKMask(values, k, ranked, options.threshold);
  const keepMagnitude = options.keepMagnitude ?? true;
  return {
    mask,
    values: materializeValues(values, mask, keepMagnitude)
  };
};

export const applyMagnitudeThreshold = (
  values: readonly number[],
  threshold: number,
  options: SparsifyOptions = {}
): SparsifyResult => {
  if (!values.length) {
    return emptyResult(0);
  }
  const mask = selectThresholdMask(values, threshold);
  const keepMagnitude = options.keepMagnitude ?? true;
  return {
    mask,
    values: materializeValues(values, mask, keepMagnitude)
  };
};

export const applyBlockSparsity = (
  values: readonly number[],
  blockSize: number,
  threshold: number,
  options: SparsifyOptions = {}
): SparsifyResult => {
  if (!values.length) {
    return emptyResult(0);
  }
  const mask = selectBlockMask(values, blockSize, threshold);
  const keepMagnitude = options.keepMagnitude ?? true;
  return {
    mask,
    values: materializeValues(values, mask, keepMagnitude)
  };
};

const buildPolicySparsityResult = (
  values: readonly number[],
  policy: SparsityPolicy,
  options: SparsifyOptions = {}
): SparsifyResult => {
  if (!values.length) {
    return emptyResult(0);
  }
  const keepMagnitude = options.keepMagnitude ?? true;
  const ranked = rankEntries(values, policy.seed);
  let mask: boolean[];
  if (policy.mode === "topk") {
    const k = policy.k ?? values.length;
    mask = selectTopKMask(values, k, ranked, policy.threshold);
  } else if (policy.mode === "threshold") {
    const threshold = policy.threshold ?? DEFAULT_THRESHOLD;
    mask = selectThresholdMask(values, threshold);
  } else {
    const blockSize = policy.blockSize ?? values.length;
    const threshold = policy.threshold ?? DEFAULT_THRESHOLD;
    mask = selectBlockMask(values, blockSize, threshold);
  }
  const adjustedMask = cloneMask(mask);
  enforceFractions(adjustedMask, ranked, policy);
  return {
    mask: adjustedMask,
    values: materializeValues(values, adjustedMask, keepMagnitude)
  };
};

export const sparsifyWithPolicyResult = (
  values: readonly number[],
  policy: SparsityPolicy,
  options: SparsifyOptions = {}
): SparsifyResult => buildPolicySparsityResult(values, policy, options);

export const sparsifyWithPolicy = (
  values: readonly number[],
  policy: SparsityPolicy,
  options: SparsifyOptions = {}
): number[] => buildPolicySparsityResult(values, policy, options).values;
