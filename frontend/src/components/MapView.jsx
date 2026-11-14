import L from 'leaflet'
import { HeatLayer } from 'leaflet.heat'
import { useEffect, useRef } from 'react'
import { LEVEL_COLORS, LEVEL_HEAT, ROUTE_COLORS, fmtTime } from '../risk'

const pin = (letter) =>
  L.divIcon({ className: 'pin', html: letter, iconSize: [26, 26], iconAnchor: [13, 13] })

const HEAT_GRADIENT = { 0: '#2e9e50', 0.25: '#e0b400', 0.5: '#ef7d00', 0.75: '#d62828', 1: '#6a1b9a' }

export default function MapView({ result, selectedId, onSelect, hour, showHeat }) {
  const el = useRef(null)
  const map = useRef(null)
  const routeLayer = useRef(null)
  const heat = useRef(null)
  const frame = useRef(0)

  // One canvas-rendered map for the lifetime of the component.
  useEffect(() => {
    map.current = L.map(el.current, { preferCanvas: true, zoomControl: true }).setView([39.5, -98.35], 4)
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors',
      maxZoom: 18,
    }).addTo(map.current)
    routeLayer.current = L.layerGroup().addTo(map.current)
    return () => map.current.remove()
  }, [])

  // Routes + checkpoints: rebuilt only when results or the selected route change.
  useEffect(() => {
    const layer = routeLayer.current
    layer.clearLayers()
    if (!result) return
    const bounds = L.latLngBounds([])
    // Draw the selected route last so it sits on top.
    const ordered = [...result.routes].sort((a, b) => (a.id === selectedId) - (b.id === selectedId))
    for (const r of ordered) {
      const active = r.id === selectedId
      const latlngs = r.geometry.coordinates.map(([lon, lat]) => [lat, lon])
      const line = L.polyline(latlngs, {
        color: ROUTE_COLORS[r.id % 3],
        weight: active ? 6 : 4,
        opacity: active ? 0.9 : 0.45,
      }).on('click', () => onSelect(r.id))
      line.bindTooltip(`${r.name}${r.recommended ? ' (recommended)' : ''}`, { sticky: true })
      layer.addLayer(line)
      bounds.extend(line.getBounds())
      for (const c of r.checkpoints) {
        L.circleMarker([c.lat, c.lon], {
          radius: active ? 6 : 4,
          color: '#fff',
          weight: 1,
          fillColor: LEVEL_COLORS[c.risk_level],
          fillOpacity: 1,
        })
          .bindPopup(
            `<b>${r.name} · mile ${Math.round(c.mile)}</b><br>ETA ${fmtTime(c.eta)}<br>` +
              `<b style="color:${LEVEL_COLORS[c.risk_level]}">${c.risk}</b> (${c.driver})<br>` +
              `Wind ${c.wind_mph} mph · Rain ${c.rain_in_hr} in/hr · Snow ${c.snow_in_hr} in/hr`,
          )
          .addTo(layer)
      }
    }
    for (const [p, label] of [[result.origin, 'Origin'], [result.destination, 'Destination']]) {
      L.marker([p.lat, p.lon], { title: label, icon: pin(label[0]) }).bindTooltip(`${label}: ${p.query}`).addTo(layer)
    }
    if (bounds.isValid() && selectedId === result.recommended_route_id) map.current.fitBounds(bounds, { padding: [30, 30] })
  }, [result, selectedId, onSelect])

  // Heatmap: only the point intensities change as the slider moves.
  useEffect(() => {
    cancelAnimationFrame(frame.current)
    frame.current = requestAnimationFrame(() => {
      if (!result || !showHeat) {
        heat.current?.remove()
        heat.current = null
        return
      }
      const points = result.routes.flatMap((r) => r.checkpoints.map((c) => [c.lat, c.lon, LEVEL_HEAT[c.forecast[hour]]]))
      if (!heat.current) {
        heat.current = new HeatLayer(points, { radius: 26, blur: 22, max: 1, maxZoom: 7, minOpacity: 0.04, gradient: HEAT_GRADIENT })
        heat.current.addTo(map.current)
      } else {
        heat.current.setLatLngs(points)
      }
    })
  }, [result, hour, showHeat])

  return <div ref={el} className="map" />
}
