export const contextModes = ["manuscript", "characters", "world"] as const;

export type ContextMode = (typeof contextModes)[number];

export function parseContextMode(value: unknown): ContextMode | undefined {
  return contextModes.find((mode) => mode === value);
}
