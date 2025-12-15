import createReasoncoreLite, {
  DEFAULT_CONTRACT,
  type ReasoncoreContract,
  type ReasoncoreLiteInput,
  type ReasoncoreLiteOutput,
  type ReasoncoreLiteRuntime
} from './reasoncore_lite';

export type PublicShellOptions = {
  /** Optional contract override scoped to the safe, lite envelope. */
  readonly contract?: ReasoncoreContract;
  /** Execution timeout forwarded to the lite runtime. */
  readonly timeoutMs?: number;
};

export type PublicReasoncoreShell = Pick<ReasoncoreLiteRuntime, 'evaluate' | 'getContract'>;

/**
 * PUBLIC_CONTRACT keeps only the observable Reasoncore Lite surface and tightens the
 * bloom ceiling for the web-facing shell.
 */
export const PUBLIC_CONTRACT: ReasoncoreContract = {
  ...DEFAULT_CONTRACT,
  clampPolicy: {
    ...DEFAULT_CONTRACT.clampPolicy,
    bloom: { ...DEFAULT_CONTRACT.clampPolicy.bloom, max: 0.9 }
  },
  prohibitedBehaviors: ['drift-recursion', 'sealed-integrations', 'nightmare-loops'],
  notes: [
    'Public shell exposes only quaternion drift, lightweight bloom, and low-risk loops.',
    'Private integrity layers and sealed channels are intentionally absent.',
    'Plugins and external seals stay disabled; only pure Reasoncore Lite math is reachable.'
  ]
};

/**
 * Create a public-facing Reasoncore Lite shell. Plugins are disabled and no
 * private sealing hooks can be routed through this entrypoint.
 */
export const createPublicReasoncoreShell = (
  options: PublicShellOptions = {}
): PublicReasoncoreShell => {
  const runtime = createReasoncoreLite({
    contract: options.contract ?? PUBLIC_CONTRACT,
    plugins: [],
    sandbox: undefined,
    baselineSparsity: undefined,
    sparsityPolicy: undefined,
    timeoutMs: options.timeoutMs
  });

  return {
    evaluate: (input: ReasoncoreLiteInput): ReasoncoreLiteOutput => runtime.evaluate(input),
    getContract: () => runtime.getContract()
  };
};

export default createPublicReasoncoreShell;
