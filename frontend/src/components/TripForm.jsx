import PlaceInput from './PlaceInput'

export default function TripForm({ form, setForm, onSubmit, loading }) {
  const field = (name) => ({
    value: form[name],
    onChange: (e) => setForm({ ...form, [name]: e.target.value }),
  })
  return (
    <form
      className="card form"
      onSubmit={(e) => {
        e.preventDefault()
        onSubmit()
      }}
    >
      <PlaceInput label="Origin" value={form.origin} onChange={(v) => setForm({ ...form, origin: v })} placeholder="Type a city or address" />
      <PlaceInput label="Destination" value={form.destination} onChange={(v) => setForm({ ...form, destination: v })} placeholder="Type a city or address" />
      <label>Departure<input type="datetime-local" {...field('departure')} required /></label>
      <div className="row">
        <label>Load (lb)<input type="number" min="0" step="500" {...field('loadLbs')} required /></label>
        <label>Checkpoint every
          <select {...field('interval')}>
            <option value="10">10 miles</option>
            <option value="25">25 miles</option>
            <option value="50">50 miles</option>
          </select>
        </label>
      </div>
      <button disabled={loading}>{loading ? 'Analyzing weather…' : 'Find safest route'}</button>
    </form>
  )
}
