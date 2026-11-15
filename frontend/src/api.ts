export const API_URL: string = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export async function fetchHealth(): Promise<{ status: string }> {
  const response = await fetch(`${API_URL}/api/health/`)
  if (!response.ok) {
    throw new Error(`Backend responded with ${response.status}`)
  }
  return response.json()
}
