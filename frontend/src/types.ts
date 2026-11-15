export type RiskKey = 'low' | 'moderate' | 'high' | 'severe' | 'no_travel'

export interface Place {
  label: string
  lat: number
  lon: number
}

export interface Checkpoint {
  index: number
  mile: number
  lat: number
  lon: number
  eta: string
  segment_miles: number
  wind_mph: number
  rain_in_hr: number
  risk: RiskKey
}

export interface RouteResult {
  id: string
  name: string
  rank: number
  recommended: boolean
  distance_miles: number
  duration_seconds: number
  arrival_time: string
  has_no_travel: boolean
  max_risk: RiskKey
  average_risk: number
  miles_by_risk: Record<RiskKey, number>
  /** [lat, lon] pairs */
  geometry: [number, number][]
  checkpoints: Checkpoint[]
}

export interface Recommendation {
  route_id: string
  reason: string
  all_routes_blocked: boolean
}

export interface RoutesResponse {
  origin: Place
  destination: Place
  departure_time: string
  load_weight_lb: number
  checkpoint_interval_miles: number
  recommendation: Recommendation
  routes: RouteResult[]
}

export type CheckpointInterval = 10 | 25 | 50

export interface RoutesRequest {
  /** A place chosen from suggestions, or free text the backend will geocode. */
  origin: Place | string
  destination: Place | string
  departure_time: string
  load_weight_lb: number
  checkpoint_interval_miles: CheckpointInterval
}
