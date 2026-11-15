import { useState } from 'react'
import type { FormEvent } from 'react'
import { nextFullHour, toLocalInputValue } from '../format'
import type { CheckpointInterval, RoutesRequest } from '../types'
import { PlaceInput } from './PlaceInput'
import type { PlaceValue } from './PlaceInput'

interface Props {
  loading: boolean
  onSubmit: (request: RoutesRequest) => void
}

const EMPTY_PLACE: PlaceValue = { text: '', place: null }
const INTERVALS: CheckpointInterval[] = [10, 25, 50]
const MAX_LOAD_LB = 200_000

export function RouteForm({ loading, onSubmit }: Props) {
  const [origin, setOrigin] = useState<PlaceValue>(EMPTY_PLACE)
  const [destination, setDestination] = useState<PlaceValue>(EMPTY_PLACE)
  const [departure, setDeparture] = useState(() => toLocalInputValue(nextFullHour()))
  const [load, setLoad] = useState('40000')
  const [checkpointInterval, setCheckpointInterval] = useState<CheckpointInterval>(25)
  const [error, setError] = useState<string | null>(null)

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const departureDate = new Date(departure)
    const loadLb = Number(load)

    if (!origin.text.trim() || !destination.text.trim()) {
      setError('Enter both an origin and a destination.')
    } else if (Number.isNaN(departureDate.getTime())) {
      setError('Enter a valid departure date and time.')
    } else if (!load.trim() || !Number.isInteger(loadLb) || loadLb < 0 || loadLb > MAX_LOAD_LB) {
      setError(`Load weight must be a whole number between 0 and ${MAX_LOAD_LB.toLocaleString()} lb.`)
    } else {
      setError(null)
      onSubmit({
        origin: origin.place ?? origin.text.trim(),
        destination: destination.place ?? destination.text.trim(),
        departure_time: departureDate.toISOString(),
        load_weight_lb: loadLb,
        checkpoint_interval_miles: checkpointInterval,
      })
    }
  }

  return (
    <form className="route-form" onSubmit={handleSubmit} noValidate>
      <PlaceInput label="Origin" value={origin} onChange={setOrigin} placeholder="e.g. Dallas, TX" />
      <PlaceInput label="Destination" value={destination} onChange={setDestination} placeholder="e.g. Atlanta, GA" />

      <div className="field">
        <label htmlFor="departure">Departure</label>
        <input id="departure" type="datetime-local" value={departure} onChange={(e) => setDeparture(e.target.value)} />
      </div>

      <div className="field-row">
        <div className="field">
          <label htmlFor="load">Load weight (lb)</label>
          <input
            id="load"
            type="number"
            inputMode="numeric"
            min={0}
            max={MAX_LOAD_LB}
            step={500}
            value={load}
            onChange={(e) => setLoad(e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="interval">Checkpoint every</label>
          <select
            id="interval"
            value={checkpointInterval}
            onChange={(e) => setCheckpointInterval(Number(e.target.value) as CheckpointInterval)}
          >
            {INTERVALS.map((miles) => (
              <option key={miles} value={miles}>
                {miles} miles
              </option>
            ))}
          </select>
        </div>
      </div>

      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}

      <button type="submit" className="primary" disabled={loading}>
        {loading ? 'Analyzing…' : 'Find safest route'}
      </button>
    </form>
  )
}
