import { describe, expect, it } from 'vitest';

import createReasoncoreLite, {
  DEFAULT_CONTRACT,
  ReasoncoreContract,
  ReasoncoreLiteInput,
  getActiveIndices,
  getSparsityTelemetry,
  type BaselineSparsitySnapshot
} from '../reasoncore_lite';
import type { SparsityPolicy } from '../core/sparsity/policy';

const baseInput: ReasoncoreLiteInput = {
  drift: { intensity: 0.35, momentum: 1.2, anchor: 0.25, bias: 0.05 },
  bloom: { seeds: 144, density: 0.55, variance: 0.3 },
  emotion: { baseline: 0.1, target: 0.6 },
  glyph: { contextuality: 0.6, limit: 4, context: ['echo', 'veil'] }
};

describe('reasoncore lite sparsity guard rails', () => {
  const limitedContract: ReasoncoreContract = {
    ...DEFAULT_CONTRACT,
    maxActiveChannelsEmotion: 2,
    maxActiveChannelsDrift: 1,
    maxActiveGlyphs: 2
  };

  const topKPolicy: SparsityPolicy = {
    version: '1.0',
    target: 'tests/hostile-sparse',
    mode: 'topk',
    k: limitedContract.maxActiveChannelsEmotion ?? 2,
    maxActiveFraction: 0.5
  };

  it('trims hostile plugin floods to the contract vector length and keeps sandboxed inputs immutable', () => {
    const safeEmotionPlugins = [
      { name: 'alpha', onEmotion: () => ({ delta: 0.75, bias: 0.15, label: 'alpha' }) },
      { name: 'beta', onEmotion: () => ({ delta: 0.45, bias: 0.05, label: 'beta' }) },
      { name: 'gamma', onEmotion: () => ({ delta: -0.55, bias: -0.12, label: 'gamma' }) }
    ];

    const glyphFlood = {
      name: 'glyph-flood',
      onGlyph: () => ({ add: ['solitude', 'signal', 'specter', 'vector', 'shard'] })
    };

    const hostileSource = `
      'use strict';
      module.exports = {
        name: 'hostile-vector',
        onEmotion(ctx) {
          // try to append new dimensions directly to the frozen context
          ctx.delta = (ctx.delta ?? 0) + 1;
          ctx.extra = ctx.extra ? ctx.extra.concat('breach') : ['breach'];
          return { delta: 0.35, bias: 0.3, label: 'hostile' };
        }
      };
    `;

    const runtime = createReasoncoreLite({
      contract: limitedContract,
      plugins: [hostileSource, ...safeEmotionPlugins, glyphFlood],
      sparsityPolicy: topKPolicy
    });

    const hostileInput = JSON.parse(JSON.stringify(baseInput));
    const snapshotBefore = JSON.stringify(hostileInput);
    const result = runtime.evaluate(hostileInput);

    const diagnostics = result.diagnostics.plugin;
    expect(diagnostics.some((entry) => entry.plugin === 'hostile-vector' && entry.type === 'error')).toBe(true);

    const telemetry = getSparsityTelemetry();
    const emotionTelemetry = telemetry.emotion;
    expect(emotionTelemetry).toBeDefined();
    expect(emotionTelemetry?.activeCount).toBe(limitedContract.maxActiveChannelsEmotion);
    expect(emotionTelemetry?.vectorLength).toBe(safeEmotionPlugins.length);
    expect(getActiveIndices('emotion').length).toBe(emotionTelemetry?.activeCount ?? 0);
    expect(result.glyphs.suggestions.length).toBeLessThanOrEqual(limitedContract.maxActiveGlyphs);
    expect(JSON.stringify(hostileInput)).toBe(snapshotBefore);
  });

  it('keeps massive spikes finite while respecting the drift sparsity budget', () => {
    const spikePolicy: SparsityPolicy = {
      version: '1.0',
      target: 'tests/spike-combat',
      mode: 'topk',
      k: limitedContract.maxActiveChannelsDrift ?? 1,
      maxActiveFraction: 0.4
    };

    const spikePlugins = [
      {
        name: 'spike-alpha',
        onEmotion: () => ({
          delta: 0.95,
          bias: Number.MAX_VALUE / 4,
          label: 'spike-alpha'
        })
      },
      {
        name: 'spike-beta',
        onEmotion: () => ({
          delta: -0.85,
          bias: -Number.MAX_VALUE / 5,
          label: 'spike-beta'
        })
      },
      {
        name: 'spike-glyph',
        onGlyph: () => ({ add: ['flare', 'ember'] })
      }
    ];

    const spikeRuntime = createReasoncoreLite({
      contract: limitedContract,
      plugins: spikePlugins,
      sparsityPolicy: spikePolicy
    });

    const spikeInput = JSON.parse(JSON.stringify(baseInput));
    const spikeResult = spikeRuntime.evaluate(spikeInput);
    const driftTelemetry = getSparsityTelemetry().drift;

    expect(Number.isFinite(spikeResult.drift.value)).toBe(true);
    expect(driftTelemetry).toBeDefined();
    expect(driftTelemetry?.activeCount).toBeLessThanOrEqual(limitedContract.maxActiveChannelsDrift ?? 0);
    expect(getActiveIndices('drift').length).toBe(driftTelemetry?.activeCount ?? 0);
  });

  it('annotates telemetry with dream baseline deviations', () => {
    const baselineSnapshot: BaselineSparsitySnapshot = {
      tick: 16,
      sceneTags: ['veil', 'echo'],
      targets: {
        drift: { density: 0.2, activeIndices: [0, 3] },
        emotion: { density: 0.5, activeIndices: [0, 2, 4] },
        glyph: { density: 0.25, activeIndices: [0, 1] }
      }
    };
    const runtime = createReasoncoreLite({
      contract: limitedContract,
      baselineSparsity: baselineSnapshot
    });
    runtime.evaluate(JSON.parse(JSON.stringify(baseInput)));
    const telemetry = getSparsityTelemetry();
    expect(telemetry.drift?.baselineDensity).toBeCloseTo(0.2, 5);
    expect(telemetry.drift?.baselineSceneTags).toEqual(['echo', 'veil']);
    expect(telemetry.drift?.baselineTick).toBe(16);
    expect(telemetry.drift?.densityDeltaFromBaseline).toBeCloseTo(
      (telemetry.drift?.density ?? 0) - 0.2,
      5
    );
    expect(telemetry.emotion?.baselineActiveCount).toBe(3);
    expect(telemetry.glyph?.baselineDensity).toBeCloseTo(0.25, 5);
  });
});
