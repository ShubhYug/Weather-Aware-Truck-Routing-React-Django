import { LEVELS, LEVEL_COLORS, ROUTE_COLORS, fmtDuration, fmtTime } from '../risk'

function RiskBar({ miles, total }) {
  return (
    <div className="riskbar" title="Miles by risk level">
      {LEVELS.map((name, i) =>
        miles[name] > 0 ? (
          <span key={name} style={{ width: `${(miles[name] / total) * 100}%`, background: LEVEL_COLORS[i] }} />
        ) : null,
      )}
    </div>
  )
}

export default function RouteList({ result, selectedId, onSelect }) {
  const selected = result.routes.find((r) => r.id === selectedId)
  return (
    <>
      <div className="card recommendation">
        <strong>Recommendation</strong>
        <p>{result.recommendation}</p>
      </div>
      {result.routes.map((r) => (
        <button
          key={r.id}
          className={`card route ${r.id === selectedId ? 'selected' : ''}`}
          style={{ borderLeftColor: ROUTE_COLORS[r.id % 3] }}
          onClick={() => onSelect(r.id)}
        >
          <div className="route-head">
            <strong>{r.name}</strong>
            {r.recommended && <span className="badge">Recommended</span>}
            {!r.travel_allowed && <span className="badge danger">No Travel</span>}
            <span className="rank">#{r.rank}</span>
          </div>
          <div className="stats">
            <span>{Math.round(r.distance_miles)} mi</span>
            <span>{fmtDuration(r.duration_hours)}</span>
            <span>Arrive {fmtTime(r.arrival)}</span>
          </div>
          <RiskBar miles={r.miles_by_level} total={r.distance_miles} />
          <div className="stats small">
            <span>Severe {Math.round(r.miles_by_level.Severe)} mi</span>
            <span>High {Math.round(r.miles_by_level.High)} mi</span>
            <span>Avg risk {r.average_risk.toFixed(2)}</span>
          </div>
        </button>
      ))}
      {selected && (
        <div className="card">
          <strong>{selected.name} checkpoints</strong>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Mile</th><th>ETA</th><th>Risk</th><th>Wind</th><th>Rain</th><th>Snow</th></tr></thead>
              <tbody>
                {selected.checkpoints.map((c) => (
                  <tr key={c.mile}>
                    <td>{Math.round(c.mile)}</td>
                    <td>{fmtTime(c.eta)}</td>
                    <td><span className="dot" style={{ background: LEVEL_COLORS[c.risk_level] }} />{c.risk}</td>
                    <td>{c.wind_mph}</td><td>{c.rain_in_hr}</td><td>{c.snow_in_hr}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  )
}
