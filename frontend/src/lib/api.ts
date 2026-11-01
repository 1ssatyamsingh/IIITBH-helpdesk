const API = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8018/api/v1').replace(/\/$/, '')

export type EvidenceSource = {
  evidence_id: string; chunk_id: string; source_file: string
  page_number: number | null; excerpt: string; score: number
  extraction_method: string | null
  metadata: Record<string, unknown>; used_in_answer: boolean
}
export type QueryResult = {
  query_id: string; status: string; answer: string | null
  insufficient_evidence: boolean; sources: EvidenceSource[]
}
export type IngestionFile = {
  file_id: string; original_filename: string; file_type: string | null
  status: string; error?: string | null; metadata: Record<string, unknown>
  created_at: string; updated_at: string
}
export type IngestionJob = {
  job_id: string; status: string; created_at: string; updated_at: string
  files: IngestionFile[]
}
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try { response = await fetch(API + path, init) }
  catch { throw new Error('Cannot reach the RAG API. Start the backend on port 8018.') }
  if (!response.ok) {
    let message = 'Request failed (' + response.status + ')'
    try { const body = await response.json(); if (typeof body.detail === 'string') message = body.detail } catch {}
    throw new Error(message)
  }
  return response.json() as Promise<T>
}
export function checkApi() { return fetch(API + '/health').then(r => r.ok).catch(() => false) }
export function askQuestion(question: string) {
  return request<QueryResult>('/query', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question, top_k: 6 }) })
}
export function uploadDocuments(files: File[]) {
  const body = new FormData()
  files.forEach(file => body.append('files', file))
  return request<IngestionJob>('/ingestion/jobs', { method: 'POST', body })
}
export function getIngestionJob(id: string) {
  return request<IngestionJob>('/ingestion/jobs/' + encodeURIComponent(id))
}
export function retryIngestionFile(jobId: string, fileId: string) {
  return request<IngestionJob>(
    '/ingestion/jobs/' + encodeURIComponent(jobId) + '/files/' + encodeURIComponent(fileId) + '/retry',
    { method: 'POST' },
  )
}
