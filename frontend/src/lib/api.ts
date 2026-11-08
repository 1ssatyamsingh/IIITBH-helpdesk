const API = (import.meta.env.VITE_API_BASE_URL || 'https://iiitbh-helpdesk-1.onrender.com/api/v1').replace(/\/$/, '')

export type EvidenceSource = {
  evidence_id: string; chunk_id: string; source_file: string; document_id: string
  page_number: number | null; excerpt: string; score: number
  extraction_method: string | null; source_url?: string | null; source_type: 'institutional' | 'web'
  metadata: Record<string, unknown>; used_in_answer: boolean
}
export type QueryResult = {
  query_id: string; status: string; answer: string | null
  insufficient_evidence: boolean; sources: EvidenceSource[]
}
export type KnowledgeDocument = {
  document_id: string; source_file: string; file_type: string | null
  chunk_count: number; page_count: number
  metadata: Record<string, unknown>
}
export type KnowledgeBaseResult = {
  collection: string; document_count: number; documents: KnowledgeDocument[]
  limit: number; offset: number; has_more: boolean; next_offset: number | null
  sort_by: 'source_file' | 'chunk_count' | 'page_count'; order: 'asc' | 'desc'
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
  catch { throw new Error('Cannot reach the RAG API. Ensure the backend is running.') }
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
export function getKnowledgeBase(options: { limit?: number; offset?: number; sort_by?: 'source_file' | 'chunk_count' | 'page_count'; order?: 'asc' | 'desc'; refresh?: boolean } = {}) {
  const params = new URLSearchParams({
    limit: String(options.limit ?? 10),
    offset: String(options.offset ?? 0),
    sort_by: options.sort_by ?? 'source_file',
    order: options.order ?? 'asc',
    refresh: String(options.refresh ?? false),
  })
  return request<KnowledgeBaseResult>('/knowledge-base/documents?' + params.toString())
}
export function deleteKnowledgeDocument(documentId: string) {
  return request<{ deleted: boolean; deleted_chunks: number; local_upload_deleted: boolean }>(
    '/knowledge-base/documents/' + encodeURIComponent(documentId),
    { method: 'DELETE', headers: { 'X-Confirm-Delete': documentId } },
  )
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
