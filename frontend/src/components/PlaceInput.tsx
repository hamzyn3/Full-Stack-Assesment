import { useEffect, useId, useState } from 'react'
import type { KeyboardEvent } from 'react'
import { fetchPlaces } from '../api'
import type { Place } from '../types'

export interface PlaceValue {
  text: string
  /** Set when the user picked a suggestion; cleared as soon as they edit the text. */
  place: Place | null
}

interface Props {
  label: string
  value: PlaceValue
  onChange: (value: PlaceValue) => void
  placeholder?: string
}

const MIN_QUERY_LENGTH = 3
const DEBOUNCE_MS = 300

export function PlaceInput({ label, value, onChange, placeholder }: Props) {
  const id = useId()
  const listId = `${id}-list`
  const [suggestions, setSuggestions] = useState<Place[]>([])
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)
  const [unavailable, setUnavailable] = useState(false)

  const query = value.text.trim()
  const shouldSearch = open && value.place === null && query.length >= MIN_QUERY_LENGTH

  useEffect(() => {
    if (!shouldSearch) return
    const controller = new AbortController()
    const timer = setTimeout(() => {
      fetchPlaces(query, controller.signal)
        .then((places) => {
          setSuggestions(places)
          setActive(-1)
          setUnavailable(false)
        })
        .catch((error: unknown) => {
          if (error instanceof DOMException && error.name === 'AbortError') return
          setSuggestions([])
          setUnavailable(true)
        })
    }, DEBOUNCE_MS)
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [shouldSearch, query])

  function choose(place: Place) {
    onChange({ text: place.label, place })
    setOpen(false)
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (!open || suggestions.length === 0) return
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setActive((i) => (i + 1) % suggestions.length)
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActive((i) => (i <= 0 ? suggestions.length - 1 : i - 1))
    } else if (event.key === 'Enter' && active >= 0) {
      event.preventDefault()
      choose(suggestions[active])
    } else if (event.key === 'Escape') {
      setOpen(false)
    }
  }

  const showList = shouldSearch && suggestions.length > 0
  const showHint = shouldSearch && unavailable

  return (
    <div className="field place-input">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        type="text"
        role="combobox"
        aria-expanded={showList}
        aria-controls={listId}
        aria-activedescendant={active >= 0 ? `${id}-opt-${active}` : undefined}
        aria-autocomplete="list"
        autoComplete="off"
        placeholder={placeholder}
        value={value.text}
        onChange={(event) => {
          onChange({ text: event.target.value, place: null })
          setOpen(true)
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={onKeyDown}
      />
      {showList && (
        <ul id={listId} role="listbox" className="suggestions">
          {suggestions.map((place, index) => (
            <li
              key={`${place.lat},${place.lon}`}
              id={`${id}-opt-${index}`}
              role="option"
              aria-selected={index === active}
              className={index === active ? 'active' : undefined}
              // mousedown fires before the input's blur closes the list
              onMouseDown={(event) => {
                event.preventDefault()
                choose(place)
              }}
            >
              {place.label}
            </li>
          ))}
        </ul>
      )}
      {showHint && <p className="hint">Suggestions are unavailable. You can still type a full place name.</p>}
    </div>
  )
}
