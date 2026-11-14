export const LEVELS = ['Low', 'Moderate', 'High', 'Severe', 'No Travel']
export const LEVEL_COLORS = ['#2e9e50', '#e0b400', '#ef7d00', '#d62828', '#6a1b9a']
// Heat intensity per risk level; Low stays faint so risky areas stand out.
export const LEVEL_HEAT = [0.02, 0.3, 0.55, 0.8, 1]
export const ROUTE_COLORS = ['#1d4ed8', '#0f766e', '#9333ea']

export const fmtTime = (iso) =>
  new Date(iso).toLocaleString([], { weekday: 'short', hour: 'numeric', minute: '2-digit' })

export const fmtDuration = (hours) => `${Math.floor(hours)}h ${String(Math.round((hours % 1) * 60)).padStart(2, '0')}m`
export const legend = LEVELS.map((name, i) => ({ name, color: LEVEL_COLORS[i] }))
