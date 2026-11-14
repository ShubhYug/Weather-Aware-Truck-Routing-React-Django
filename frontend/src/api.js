export async function planTrip(form, signal) {
  const res = await fetch('/api/trucking/plan/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    signal,
    body: JSON.stringify({
      origin: form.origin.coords || form.origin.label,
      destination: form.destination.coords || form.destination.label,
      departure: new Date(form.departure).toISOString(),
      load_lbs: Number(form.loadLbs),
      interval_miles: Number(form.interval),
    }),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`)
  return data
}
