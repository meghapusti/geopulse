/**
 * Shared tension colour helpers.
 * Used by the globe renderer and all chart components.
 */

/** Returns an rgba string based on 0–100 tension score. */
export function tensionColor(score: number, alpha = 1): string {
  // Low (0–33): green → amber (33–66) → red (66–100)
  if (score < 33) {
    const t = score / 33
    const r = Math.round(34 + t * (245 - 34))
    const g = Math.round(197 - t * (197 - 158))
    const b = Math.round(94 - t * 94)
    return `rgba(${r},${g},${b},${alpha})`
  } else if (score < 66) {
    const t = (score - 33) / 33
    const r = Math.round(245 + t * (239 - 245))
    const g = Math.round(158 - t * (158 - 68))
    const b = Math.round(0 + t * 68)
    return `rgba(${r},${g},${b},${alpha})`
  } else {
    const t = (score - 66) / 34
    const r = Math.round(239 - t * 30)
    const g = Math.round(68 - t * 68)
    const b = Math.round(68 - t * 68)
    return `rgba(${r},${g},${b},${alpha})`
  }
}

/** Returns Tailwind text class for severity badge. */
export function severityClass(score: number): string {
  if (score >= 66) return 'text-red-400'
  if (score >= 40) return 'text-amber-400'
  return 'text-emerald-400'
}

/** Returns label for tension score. */
export function tensionLabel(score: number): string {
  if (score >= 75) return 'Critical'
  if (score >= 55) return 'High'
  if (score >= 35) return 'Elevated'
  return 'Low'
}

/** Returns bias icon for market signals. */
export function biasIcon(bias: string | null): string {
  if (bias === 'bullish' || bias === 'up') return '↑'
  if (bias === 'bearish' || bias === 'down') return '↓'
  return '→'
}

export function biasColor(bias: string | null): string {
  if (bias === 'bullish' || bias === 'up') return 'text-emerald-400'
  if (bias === 'bearish' || bias === 'down') return 'text-red-400'
  return 'text-slate-400'
}
