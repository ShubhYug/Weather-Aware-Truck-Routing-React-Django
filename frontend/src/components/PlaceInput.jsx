import { useEffect, useId, useState } from 'react'

// Text box with type-ahead suggestions. Picking one stores its coordinates; typing
// anything else is fine too and is geocoded by the backend.
export default function PlaceInput({ label, value, onChange, placeholder }) {
  const listId = useId()
  const [options, setOptions] = useState([])
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)
  const visible = open && !value.coords && value.label.trim().length >= 3 ? options : []

  useEffect(() => {
    const text = value.label.trim()
    if (text.length < 3 || value.coords) return  // coords set = a suggestion was just picked
    const controller = new AbortController()
    const timer = setTimeout(async () => {
      try {
        const res = await fetch(`/api/trucking/suggest/?q=${encodeURIComponent(text)}`, { signal: controller.signal })
        setOptions((await res.json()).suggestions ?? [])
        setActive(-1)
      } catch {
        /* aborted or offline: free typing still works */
      }
    }, 300)
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [value.label, value.coords])

  const choose = (o) => {
    onChange({ label: o.label, coords: `${o.lat},${o.lon}` })
    setOpen(false)
  }

  const onKeyDown = (e) => {
    if (!visible.length) return
    if (e.key === 'ArrowDown') { e.preventDefault(); setActive((a) => (a + 1) % visible.length) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((a) => (a <= 0 ? visible.length - 1 : a - 1)) }
    else if (e.key === 'Enter' && active >= 0) { e.preventDefault(); choose(visible[active]) }
    else if (e.key === 'Escape') setOpen(false)
  }

  return (
    <label className="place">
      {label}
      <input
        value={value.label}
        placeholder={placeholder}
        required
        autoComplete="off"
        role="combobox"
        aria-expanded={visible.length > 0}
        aria-controls={listId}
        onChange={(e) => { onChange({ label: e.target.value, coords: null }); setOpen(true) }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onKeyDown={onKeyDown}
      />
      {visible.length > 0 && (
        <ul id={listId} className="suggestions" role="listbox">
          {visible.map((o, i) => (
            <li key={o.label} role="option" aria-selected={i === active} className={i === active ? 'active' : ''}
              onMouseDown={(e) => { e.preventDefault(); choose(o) }}>
              {o.label}
            </li>
          ))}
        </ul>
      )}
    </label>
  )
}
