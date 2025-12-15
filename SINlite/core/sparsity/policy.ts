import { sparsifyWithPolicy } from './sparse_utils';
import type { SparsityPolicy, SparsityTelemetryExtras } from './sparse_utils';
export type {
  SparsityPolicy,
  SparsityPolicyMetadata,
  SparsityPolicyWindow,
  SparsifyOptions,
  SparsifyResult,
  SparsityTelemetry,
  SparsityTelemetryExtras
} from './sparse_utils';
export {
  applyBlockSparsity,
  applyMagnitudeThreshold,
  applyTopK,
  density,
  sparsifyWithPolicy,
  sparsifyWithPolicyResult,
  computeSparsityTelemetry
} from './sparse_utils';

// Lightweight, SINlite-local policy helpers mirroring the core implementation.
export const applySparsity = (
  values: readonly number[],
  policy: SparsityPolicy
): number[] => sparsifyWithPolicy(values, policy);

export const applySparsityToRecord = <T extends Record<string, number>>(
  record: T,
  policy: SparsityPolicy
): T => {
  const entries = Object.entries(record);
  const values = entries.map(([, value]) => value);
  const gated = applySparsity(values, policy);
  const next: Record<string, number> = {};
  entries.forEach(([key], index) => {
    next[key] = gated[index];
  });
  return { ...record, ...next } as T;
};
