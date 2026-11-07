import type { EvidenceSource, QueryResult } from './api'

const API = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8018/api/v1').replace(/\/$/, '')

type StreamEvent =
  | { type: 'chunk'; text: string }
  | { type: 'sources'; sources: EvidenceSource[] }
  | { type: 'done'; query_id: string; status: string }
  | { type: 'error'; message: string }

export async function askQuestionStream(
  question: string,
  onChunk: (text: string) => void,
  onSources: (sources: EvidenceSource[]) => void,
): Promise<QueryResult> {
  let response: Response
  try {
    response = await fetch(API + '/query/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Accept': 'text/event-stream' },
      body: JSON.stringify({ question, top_k: 6 }),
    })
  } catch {
    throw new Error('Cannot reach the RAG API. Start the backend on port 8018.')
  }

  if (!response.ok) {
    let message = 'Request failed (' + response.status + ')'
    try {
      const body = await response.json()
      if (typeof body.detail === 'string') message = body.detail
    } catch {}
    throw new Error(message)
  }
  if (!response.body) throw new Error('The API returned an empty streaming response.')

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let answer = ''
  let sources: EvidenceSource[] = []
  let queryId: string = crypto.randomUUID()
  let status = 'answered'

  const processEvent = (raw: string) => {
    const dataLine = raw.split('\n').find(line => line.startsWith('data: '))
    if (!dataLine) return
    const event = JSON.parse(dataLine.slice(6)) as StreamEvent
    if (event.type === 'chunk') {
      answer += event.text
      onChunk(event.text)
    } else if (event.type === 'sources') {
      sources = event.sources
      onSources(sources)
    } else if (event.type === 'done') {
      queryId = event.query_id
      status = event.status
    } else if (event.type === 'error') {
      throw new Error(event.message || 'Streaming answer generation failed.')
    }
  }

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const events = buffer.split('\n\n')
    buffer = events.pop() || ''
    events.forEach(processEvent)
  }
  buffer += decoder.decode()
  if (buffer.trim()) processEvent(buffer)
  return { query_id: queryId, status, answer: answer || null, insufficient_evidence: status === 'insufficient_evidence', sources }
}
