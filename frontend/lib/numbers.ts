// frontend/lib/numbers.ts
// Safe number conversion utility - handles strings, null, undefined, NaN

/**
 * Safely converts any value to a number.
 * Handles strings (from API), null, undefined, and NaN.
 * 
 * @param value - Any value to convert
 * @param fallback - Default value if conversion fails (default: 0)
 * @returns A valid number
 * 
 * @example
 * toSafeNumber("0.5")     // 0.5
 * toSafeNumber(null)      // 0
 * toSafeNumber(undefined) // 0
 * toSafeNumber("abc")     // 0
 * toSafeNumber(NaN)       // 0
 */
export function toSafeNumber(value: unknown, fallback = 0): number {
  if (value == null) return fallback;
  const num = Number(value);
  return isNaN(num) ? fallback : num;
}

