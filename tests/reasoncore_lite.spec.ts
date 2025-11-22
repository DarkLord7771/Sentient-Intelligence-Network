import { describe, expect, it } from 'vitest';
import Ajv2020 from 'ajv/dist/2020';
import fc from 'fast-check';
import { readFileSync } from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

import createReasoncoreLite, {
  DEFAULT_CONTRACT,
  ReasoncoreLiteInput,
  ReasoncoreLiteOptions,
  ReasoncoreContract,
  getActiveIndices,
  getSparsityTelemetry
} from '../reasoncore_lite';
import type { SparsityPolicy } from '../core/sparsity/policy';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const schemaPath = path.resolve(__dirname, '../../contracts/reasoncore_lite.v1.json');
const schema = JSON.parse(readFileSync(schemaPath, 'utf-8'));

const baseInput: ReasoncoreLiteInput = {
  drift: { intensity: 0.35, momentum: 1.2, anchor: 0.25, bias: 0.05 },
  bloom: { seeds: 144, density: 0.55, variance: 0.3 },
  emotion: { baseline: 0.1, target: 0.6 },
  glyph: { contextuality: 0.6, limit: 5, context: ['echo', 'veil'] }
};

describe('reasoncore lite contract', () => {
  it('validates the runtime contract against the schema', () => {
    const ajv = new Ajv2020({ allErrors: true, strict: false });
    const validate = ajv.compile(schema);
    expect(validate(DEFAULT_CONTRACT)).toBe(true);
  });
});

describe('reasoncore lite runtime', () => {
  it('produces deterministic outputs for identical inputs', () => {
    const engine = createReasoncoreLite();
    const first = engine.evaluate(baseInput);
    const second = engine.evaluate(baseInput);
    expect(second).toEqual(first);
  });

  it('clamps values that exceed the contract boundaries', () => {
    const engine = createReasoncoreLite();
    const noisyInput: ReasoncoreLiteInput = {
      drift: { intensity: 9, momentum: 18, anchor: -5, bias: 2 },
      bloom: { seeds: 999, density: 5, variance: 5 },
      emotion: { baseline: -9, target: 4 },
      glyph: { contextuality: 7, limit: 32, context: ['ghost', 'ember'] }
    };
    const output = engine.evaluate(noisyInput);

    expect(output.drift.value).toBeGreaterThanOrEqual(DEFAULT_CONTRACT.clampPolicy.drift.min);
    expect(output.drift.value).toBeLessThanOrEqual(DEFAULT_CONTRACT.clampPolicy.drift.max);
    expect(output.bloom.probability).toBeGreaterThanOrEqual(DEFAULT_CONTRACT.clampPolicy.bloom.min);
    expect(output.bloom.probability).toBeLessThanOrEqual(DEFAULT_CONTRACT.clampPolicy.bloom.max);
    expect(output.emotion.delta).toBeGreaterThanOrEqual(DEFAULT_CONTRACT.clampPolicy.emotion.min);
    expect(output.emotion.delta).toBeLessThanOrEqual(DEFAULT_CONTRACT.clampPolicy.emotion.max);
    expect(output.glyphs.suggestions.length).toBeLessThanOrEqual(DEFAULT_CONTRACT.glyph.limit.max);
  });

  it('runs plugins within the sandbox without allowing state mutation', () => {
    const mutableInput: ReasoncoreLiteInput = {
      ...baseInput,
      glyph: { ...baseInput.glyph, context: ['pulse'] }
    };

    const pluginSource = `
      'use strict';
      const seen = [];
      module.exports = {
        name: 'sandbox-check',
        onEmotion(ctx) {
          try { ctx.baseline = 42; } catch (_) {}
          return { delta: 0.9, bias: 0.9, label: 'surge' };
        },
        onGlyph(ctx) {
          try { ctx.context.push('intruder'); } catch (_) {}
          return { add: [' spectral '] };
        }
      };
    `;

    const engine = createReasoncoreLite({ plugins: [pluginSource] });
    const result = engine.evaluate(mutableInput);

    expect(result.emotion.labels).toContain('surge');
    expect(Math.abs(result.drift.overshootCurl)).toBeLessThanOrEqual(
      DEFAULT_CONTRACT.clampPolicy.drift.spikeThreshold
    );
    expect(result.glyphs.suggestions.some((glyph) => glyph.trim() === 'spectral')).toBe(true);
    expect(mutableInput.glyph.context).toEqual(['pulse']);
  });

  it('enforces the sandbox timeout guard for runaway plugins', () => {
    const engine = createReasoncoreLite({
      plugins: ["module.exports = { onBloom(){ for(;;){} } }"],
      timeoutMs: 5
    });
    const result = engine.evaluate(baseInput);
    expect(result.diagnostics.plugin.some((diag) => diag.type === 'error' && diag.hook === 'bloom')).toBe(true);
  });

  it('enforces sparse channel limits declared in the contract', () => {
    const customContract: ReasoncoreContract = {
      ...DEFAULT_CONTRACT,
      sparsityPolicyName: DEFAULT_CONTRACT.sparsityPolicyName,
      maxActiveChannelsEmotion: 1,
      maxActiveChannelsDrift: 1,
      maxActiveGlyphs: 1
    };

    const engine = createReasoncoreLite({
      contract: customContract,
      plugins: [
        { name: 'delta-strong', onEmotion: () => ({ delta: -0.9, bias: -0.6 }) },
        { name: 'delta-weak', onEmotion: () => ({ delta: 0.4, bias: 0.2 }) },
        { name: 'glyph-burst', onGlyph: () => ({ add: ['alpha', 'beta'] }) }
      ]
    });

    const result = engine.evaluate({
      ...baseInput,
      emotion: { baseline: 0, target: 0 },
      glyph: { contextuality: 0.5, limit: 4, context: [] }
    });

    expect(result.emotion.delta).toBeLessThan(0);
    expect(result.glyphs.suggestions).toContain('alpha');
    expect(result.glyphs.suggestions).not.toContain('beta');
    const sparseTelemetry = getSparsityTelemetry();
    expect(sparseTelemetry.emotion?.activeCount).toBeLessThanOrEqual(1);
    expect(sparseTelemetry.drift?.activeCount).toBeLessThanOrEqual(1);
  });

  it('keeps outputs stable when fuzzing plugin contributions', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.record({
          bloomDelta: fc.double({ min: -1, max: 1 }),
          emotionDelta: fc.double({ min: -2, max: 2 }),
          bias: fc.double({ min: -1, max: 1 }),
          glyph: fc.string({ minLength: 1, maxLength: 8 })
        }),
        async (sample) => {
          const engine = createReasoncoreLite({
            plugins: [
              {
                name: 'fuzzer',
                onBloom: () => ({ delta: sample.bloomDelta }),
                onEmotion: () => ({ delta: sample.emotionDelta, bias: sample.bias }),
                onGlyph: () => ({ add: [sample.glyph] })
              }
            ]
          });
          const output = engine.evaluate(baseInput);
          expect(output.bloom.probability).toBeGreaterThanOrEqual(DEFAULT_CONTRACT.clampPolicy.bloom.min - 1e-9);
          expect(output.bloom.probability).toBeLessThanOrEqual(DEFAULT_CONTRACT.clampPolicy.bloom.max + 1e-9);
          expect(Math.abs(output.emotion.delta)).toBeLessThanOrEqual(DEFAULT_CONTRACT.clampPolicy.emotion.max + 1e-9);
          expect(output.glyphs.suggestions.length).toBeGreaterThan(0);
        }
      ),
      { numRuns: 50 }
    );
  });

  it('exposes sparse helper state to plugins without mutating inputs', () => {
    const inspectorCalls: number[][] = [];
    const inspector = {
      name: 'sparse-inspector',
      onEmotion: () => {
        inspectorCalls.push(getActiveIndices('emotion'));
      }
    };

    const runtime = createReasoncoreLite({
      contract: { ...DEFAULT_CONTRACT, maxActiveChannelsEmotion: 1 },
      plugins: [
        { name: 'loud-delta', onEmotion: () => ({ delta: 0.9 }) },
        inspector,
        { name: 'soft-delta', onEmotion: () => ({ delta: 0.2 }) }
      ]
    });

    runtime.evaluate(baseInput);
    runtime.evaluate(baseInput);

    expect(inspectorCalls.length).toBeGreaterThanOrEqual(2);
    expect(inspectorCalls[inspectorCalls.length - 1]).toEqual([0]);

    const telemetry = getSparsityTelemetry();
    expect(telemetry.emotion?.activeCount).toBe(1);
  });

  it('trims dense plugin adjustments with the configured sparsity policy', () => {
    const aggressivePolicy: SparsityPolicy = {
      version: '1.0',
      target: 'reasoncore-lite/tests',
      mode: 'topk',
      k: 1
    };

    const runtime = createReasoncoreLite({
      sparsityPolicy: aggressivePolicy,
      plugins: [
        { name: 'delta-strong', onEmotion: () => ({ delta: 0.2 }) },
        { name: 'delta-medium', onEmotion: () => ({ delta: 0.15 }) },
        { name: 'delta-weak', onEmotion: () => ({ delta: -0.1 }) }
      ]
    });

    const result = runtime.evaluate({
      ...baseInput,
      emotion: { baseline: 0, target: 0 }
    });

    expect(result.emotion.delta).toBeGreaterThan(0);

    const telemetry = getSparsityTelemetry();
    expect(telemetry.emotion?.activeCount).toBeLessThanOrEqual(1);
  });

  it('reclamps bloom probability after sparse plugin deltas', () => {
    const runtime = createReasoncoreLite({
      plugins: [
        {
          name: 'bloom-overdrive',
          onBloom: () => ({ delta: 5, floor: 0.95, ceiling: 1.5, rationale: 'push' })
        }
      ]
    });

    const result = runtime.evaluate(baseInput);
    expect(result.bloom.probability).toBeLessThanOrEqual(DEFAULT_CONTRACT.clampPolicy.bloom.max);
    expect(result.bloom.rationale).toContain('clamp-enforced');
  });
});
