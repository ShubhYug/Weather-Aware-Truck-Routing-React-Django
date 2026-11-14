import { legend } from '../risk'

export default function HeatSlider({ departure, hour, setHour, showHeat, setShowHeat }) {
  const at = new Date(new Date(departure).getTime() + hour * 3600e3)
  return (
    <div className="slider-bar">
      <div className="slider-top">
        <label className="toggle">
          <input type="checkbox" checked={showHeat} onChange={(e) => setShowHeat(e.target.checked)} /> Weather heatmap
        </label>
        <strong>
          {hour === 0 ? 'Departure' : `+${hour}h`} · {at.toLocaleString([], { weekday: 'short', hour: 'numeric', minute: '2-digit' })}
        </strong>
        <span className="legend">
          {legend.map((l) => (
            <span key={l.name}><i style={{ background: l.color }} />{l.name}</span>
          ))}
        </span>
      </div>
      <input
        type="range" min="0" max="48" step="1" value={hour} disabled={!showHeat}
        onChange={(e) => setHour(Number(e.target.value))} aria-label="Forecast hour"
      />
    </div>
  )
}
