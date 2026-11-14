import { useCallback, useRef, useState } from 'react'
import { planTrip } from './api'
import HeatSlider from './components/HeatSlider'
import MapView from './components/MapView'
import RouteList from './components/RouteList'
import TripForm from './components/TripForm'

function defaultDeparture() {
  const d = new Date(Date.now() + 3600e3)
  d.setMinutes(0, 0, 0)
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset()) // datetime-local wants local time
  return d.toISOString().slice(0, 16)
}

export default function App() {
  const [form, setForm] = useState({
    origin: { label: 'Chicago, IL', coords: null }, destination: { label: 'Denver, CO', coords: null }, departure: defaultDeparture(), loadLbs: 42000, interval: 25,
  })
  const [result, setResult] = useState(null)
  const [selectedId, setSelectedId] = useState(null)
  const [hour, setHour] = useState(0)
  const [showHeat, setShowHeat] = useState(true)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const abort = useRef(null)

  const submit = async () => {
    abort.current?.abort()
    abort.current = new AbortController()
    setLoading(true)
    setError('')
    try {
      const data = await planTrip(form, abort.current.signal)
      // Selected suggestions are sent as coordinates; show the human-readable names.
      data.origin.query = form.origin.label
      data.destination.query = form.destination.label
      setResult(data)
      setSelectedId(data.recommended_route_id)
      setHour(0)
    } catch (e) {
      if (e.name !== 'AbortError') setError(e.message)
    } finally {
      setLoading(false)
    }
  }
  const select = useCallback((id) => setSelectedId(id), [])

  return (
    <div className="layout">
      <aside className="sidebar">
        <h1>Weather-Aware Truck Routing</h1>
        <TripForm form={form} setForm={setForm} onSubmit={submit} loading={loading} />
        {error && <div className="card error" role="alert">{error}</div>}
        {result && <RouteList result={result} selectedId={selectedId} onSelect={select} />}
      </aside>
      <main className="mapwrap">
        <MapView result={result} selectedId={selectedId} onSelect={select} hour={hour} showHeat={showHeat} />
        {result && (
          <HeatSlider departure={result.departure} hour={hour} setHour={setHour} showHeat={showHeat} setShowHeat={setShowHeat} />
        )}
        {loading && <div className="overlay">Fetching routes and forecasts…</div>}
      </main>
    </div>
  )
}
