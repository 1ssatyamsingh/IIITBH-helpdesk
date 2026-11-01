import { useEffect, useRef, useState, type DragEvent, type FormEvent, type ReactNode } from 'react'
import {
  Activity, AlertCircle, ArrowRight, BookOpen, Bot, Check, CheckCircle2,
  CircleHelp, Clock3, CloudUpload, FileText, GraduationCap, Layers3, Database,
  LoaderCircle, MessageSquare, PanelLeftClose, Search, Send, ShieldCheck, Trash2,
  Sparkles, UploadCloud, X, RefreshCw,
} from 'lucide-react'
import { askQuestion, checkApi, getIngestionJob, getKnowledgeBase, deleteKnowledgeDocument, retryIngestionFile, uploadDocuments, type EvidenceSource, type IngestionJob, type KnowledgeDocument } from './lib/api'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import 'katex/dist/katex.min.css'
import './App.css'

type View = 'chat' | 'ingestion' | 'knowledgebase'
type Message = { id: string; role: 'assistant' | 'user'; content: string; sources?: EvidenceSource[]; error?: boolean }
const prompts = [
  'What are the B.Tech fee details?',
  'Show me the academic calendar for 2026–27.',
  'Which documents are required during physical reporting?',
  'How do I apply for hostel leave?',
]
const labels: Record<string, string> = {
  queued: 'Queued', processing: 'Processing', completed: 'Completed',
  completed_with_errors: 'Completed with errors', blocked: 'Needs configuration',
  failed: 'Failed', received: 'Received', validating: 'Validating',
  classifying: 'Classifying', extracting: 'Extracting', chunking: 'Chunking',
  embedding: 'Embedding', indexing: 'Indexing', rejected: 'Rejected',
  completed_with_warnings: 'Completed with warnings',
}
const pretty = (value: string) => labels[value] || value.replaceAll('_', ' ')
const terminal = ['completed', 'completed_with_warnings', 'failed', 'rejected', 'blocked']

function App() {
  const [view, setView] = useState<View>('chat')
  const [apiOnline, setApiOnline] = useState(false)
  const [messages, setMessages] = useState<Message[]>([{
    id: 'welcome', role: 'assistant',
    content: 'Hello! I’m the IIIT Bhagalpur knowledge assistant. Ask me about academics, admissions, fees, hostels, departments, or institute services. I’ll show the references behind every result.',
  }])
  const [question, setQuestion] = useState('')
  const [asking, setAsking] = useState(false)
  const [files, setFiles] = useState<File[]>([])
  const [uploading, setUploading] = useState(false)
  const [job, setJob] = useState<IngestionJob | null>(null)
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([])
  const [catalogLoading, setCatalogLoading] = useState(false)
  const [catalogError, setCatalogError] = useState('')
  const [deletingDocument, setDeletingDocument] = useState<string | null>(null)
  const [uploadError, setUploadError] = useState('')
  const [dragging, setDragging] = useState(false)
  const [toast, setToast] = useState('')
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const endRef = useRef<HTMLDivElement>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const refresh = () => { void checkApi().then(setApiOnline) }
    refresh()
    const timer = window.setInterval(refresh, 12000)
    return () => window.clearInterval(timer)
  }, [])
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) }, [messages, asking])
  useEffect(() => {
    if (view !== 'knowledgebase') return
    let active = true
    setCatalogLoading(true); setCatalogError('')
    getKnowledgeBase().then(result => { if (active) setDocuments(result.documents) })
      .catch(error => { if (active) setCatalogError(error instanceof Error ? error.message : 'Could not load documents.') })
      .finally(() => { if (active) setCatalogLoading(false) })
    return () => { active = false }
  }, [view])
  useEffect(() => {
    if (!job || !['queued', 'processing'].includes(job.status)) return
    const timer = window.setInterval(async () => {
      try { setJob(await getIngestionJob(job.job_id)) }
      catch (error) { setUploadError(error instanceof Error ? error.message : 'Could not refresh job status.') }
    }, 2200)
    return () => window.clearInterval(timer)
  }, [job])

  const addFiles = (incoming: FileList | File[]) => {
    const incomingFiles = Array.from(incoming)
    const accepted = incomingFiles.filter(file => /\.(pdf|txt)$/i.test(file.name))
    const rejected = incomingFiles.length - accepted.length
    setFiles(current => {
      const unique = new Map([...current, ...accepted].map(file => [file.name + file.size + file.lastModified, file]))
      return Array.from(unique.values()).slice(0, 20)
    })
    setUploadError(rejected ? rejected + ' unsupported file(s) skipped. PDF or TXT only.' : '')
  }

  const submitUpload = async () => {
    if (!files.length || uploading) return
    setUploading(true); setUploadError('')
    try {
      setJob(await uploadDocuments(files))
      setFiles([])
      if (fileRef.current) fileRef.current.value = ''
      setToast('Ingestion batch created')
      window.setTimeout(() => setToast(''), 2800)
    } catch (error) { setUploadError(error instanceof Error ? error.message : 'Upload failed.') }
    finally { setUploading(false) }
  }

  const removeDocument = async (doc: KnowledgeDocument) => {
    if (deletingDocument) return
    const accepted = window.confirm(`Delete “${doc.source_file}” from the knowledge base?\n\nThis removes all ${doc.chunk_count.toLocaleString()} indexed chunks from Qdrant and deletes its local uploaded copy when available. This cannot be undone.`)
    if (!accepted) return
    setDeletingDocument(doc.document_id); setCatalogError('')
    try {
      const result = await deleteKnowledgeDocument(doc.document_id)
      setDocuments(current => current.filter(item => item.document_id !== doc.document_id))
      setToast(`Deleted ${doc.source_file} and ${result.deleted_chunks} Qdrant chunks`)
      window.setTimeout(() => setToast(''), 3500)
    } catch (error) {
      setCatalogError(error instanceof Error ? error.message : 'Could not delete document.')
    } finally { setDeletingDocument(null) }
  }

  const retryFile = async (jobId: string, fileId: string) => {
    setUploadError('')
    try {
      setJob(await retryIngestionFile(jobId, fileId))
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : 'Could not retry this file.')
    }
  }

  const submitQuestion = async (value?: string) => {
    const clean = (value ?? question).trim()
    if (!clean || asking) return
    setQuestion('')
    setMessages(current => [...current, { id: crypto.randomUUID(), role: 'user', content: clean }])
    setAsking(true)
    try {
      const result = await askQuestion(clean)
      const content = result.answer || (result.sources.length
        ? 'I found relevant passages in the indexed institute documents. The answer-generation model is not configured yet, so I’m showing retrieved evidence instead of generating an unsupported answer.'
        : 'I couldn’t find relevant evidence in the currently indexed documents. Try a more specific question, or check whether the source documents have been ingested.')
      setMessages(current => [...current, { id: result.query_id, role: 'assistant', content, sources: result.sources }])
    } catch (error) {
      setMessages(current => [...current, { id: crypto.randomUUID(), role: 'assistant', content: error instanceof Error ? error.message : 'The query failed. Please try again.', error: true }])
    } finally { setAsking(false) }
  }

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault(); setDragging(false); addFiles(event.dataTransfer.files)
  }
  const onAsk = (event: FormEvent<HTMLFormElement>) => { event.preventDefault(); void submitQuestion() }
  const completed = job?.files.filter(file => ['completed', 'completed_with_warnings'].includes(file.status)).length || 0
  const finished = job?.files.filter(file => terminal.includes(file.status)).length || 0
  const progress = job ? Math.round((finished / Math.max(job.files.length, 1)) * 100) : 0

  return (
    <div className="app-shell">
      <aside className={'sidebar ' + (sidebarOpen ? '' : 'collapsed')}>
        <div className="brand">
          <div className="brand-mark"><GraduationCap size={22} /></div>
          {sidebarOpen && <div className="brand-copy"><strong>IIITBH</strong><span>KNOWLEDGE DESK</span></div>}
          <button className="icon-button sidebar-toggle" onClick={() => setSidebarOpen(!sidebarOpen)} aria-label="Toggle sidebar"><PanelLeftClose size={17} /></button>
        </div>
        {sidebarOpen && <div className="workspace-label">WORKSPACE</div>}
        <nav className="main-nav">
          <button className={'nav-item ' + (view === 'chat' ? 'active' : '')} onClick={() => setView('chat')}><MessageSquare size={18} />{sidebarOpen && <span>Ask the institute</span>}{view === 'chat' && <i />}</button>
          <button className={'nav-item ' + (view === 'ingestion' ? 'active' : '')} onClick={() => setView('ingestion')}><Layers3 size={18} />{sidebarOpen && <span>Knowledge ingestion</span>}{view === 'ingestion' && <i />}</button>
          <button className={'nav-item ' + (view === 'knowledgebase' ? 'active' : '')} onClick={() => setView('knowledgebase')}><Database size={18} />{sidebarOpen && <span>Knowledge base</span>}{view === 'knowledgebase' && <i />}</button>
        </nav>
        {sidebarOpen && <>
          <div className="sidebar-divider" />
          <div className="workspace-label">YOUR ASSISTANT</div>
          <div className="assistant-card"><div className="assistant-avatar"><Bot size={18} /></div><div><strong>Campus assistant</strong><span>IIIT Bhagalpur · RAG</span></div><i className={'online-dot ' + (apiOnline ? 'online' : '')} /></div>
          <div className="sidebar-foot"><div className="privacy-note"><ShieldCheck size={15} /><span>Evidence-first responses<br />with source references</span></div><div className="version-label">LOCAL WORKSPACE <span>v0.1</span></div></div>
        </>}
      </aside>

      <main className="main-panel">
        <header className="topbar">
          <div className="breadcrumb">{!sidebarOpen && <button className="icon-button" onClick={() => setSidebarOpen(true)}><PanelLeftClose size={18} /></button>}<span>IIITBH</span><b>/</b><strong>{view === 'chat' ? 'Ask the institute' : view === 'ingestion' ? 'Knowledge ingestion' : 'Knowledge base'}</strong></div>
          <div className="topbar-right"><div className={'connection-pill ' + (apiOnline ? 'connected' : '')}><i />{apiOnline ? 'API connected' : 'API offline'}</div><button className="icon-button" title="About this workspace"><CircleHelp size={18} /></button></div>
        </header>

        {view === 'chat' ? <section className="chat-page">
          <div className="chat-heading"><div className="eyebrow"><Sparkles size={13} /> INSTITUTE KNOWLEDGE ASSISTANT</div><h1>What would you like<br className="mobile-break" /> to know?</h1><p>Get grounded answers from institute documents, with live web verification for current information.</p></div>
          <div className="chat-scroll"><div className="messages-list">
            {messages.map(message => <article className={'message-row ' + message.role} key={message.id}>
              {message.role === 'assistant' && <div className="message-avatar"><Bot size={17} /></div>}
              <div className="message-content"><div className="message-meta">{message.role === 'assistant' ? 'CAMPUS ASSISTANT' : 'YOU'}{message.error && <span className="error-tag">ERROR</span>}</div>
                <div className={'message-bubble ' + message.role}>
                  {message.role === 'assistant'
                    ? <div className="markdown-answer"><ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]} components={{ table: ({ children }) => <div className="markdown-table-wrap"><table>{children}</table></div> }}>{message.content}</ReactMarkdown></div>
                    : message.content}
                </div>
                {!!message.sources?.length && <details className="sources-block">
                  <summary className="sources-title"><BookOpen size={14} /> SOURCES <span>{message.sources.filter(source => source.used_in_answer).length || message.sources.length} references</span></summary>
                  <div className="sources-list">
                    {message.sources.filter(source => source.used_in_answer || !message.sources?.some(item => item.used_in_answer)).map(source => <div className="source-card" key={source.evidence_id}>
                      <div className="source-card-top"><span className="source-ref">{source.evidence_id}</span><strong>{source.source_file}</strong></div>
                      <div className="source-foot">{source.source_type === 'web' && source.source_url ? <><span>LIVE WEB</span> · <a className="source-link" href={source.source_url} target="_blank" rel="noreferrer">Open webpage <ArrowRight size={12} /></a></> : <span>Institute document{source.page_number ? ' · Page ' + source.page_number : ''}</span>}</div>
                    </div>)}
                  </div>
                </details>}
              </div>
            </article>)}
            {asking && <article className="message-row assistant"><div className="message-avatar"><Bot size={17} /></div><div className="message-content"><div className="message-meta">CAMPUS ASSISTANT</div><div className="typing-bubble"><i /><i /><i /></div></div></article>}
            <div ref={endRef} />
          </div></div>
          {messages.length === 1 && <div className="suggestions"><div className="suggestion-label">TRY ASKING</div><div className="suggestion-grid">{prompts.map(prompt => <button className="suggestion-card" key={prompt} onClick={() => void submitQuestion(prompt)}><span>{prompt}</span><ArrowRight size={15} /></button>)}</div></div>}
          <div className="composer-wrap"><form className="composer" onSubmit={onAsk}><Search size={18} /><input value={question} onChange={event => setQuestion(event.target.value)} placeholder="Ask anything about IIIT Bhagalpur..." disabled={!apiOnline || asking} aria-label="Ask a question" /><button className="send-button" type="submit" disabled={!question.trim() || !apiOnline || asking} aria-label="Send question">{asking ? <LoaderCircle className="spin" size={18} /> : <Send size={17} />}</button></form><div className="composer-caption"><ShieldCheck size={12} /> Responses are grounded in indexed sources. Verify time-sensitive notices with the institute.</div></div>
        </section> : view === 'ingestion' ? <section className="ingestion-page">
          <div className="page-title-row"><div><div className="eyebrow"><Layers3 size={13} /> KNOWLEDGE PIPELINE</div><h1>Knowledge ingestion</h1><p>Bring official institute documents into the assistant’s searchable knowledge base.</p></div><div className="pipeline-badge"><Activity size={15} /> INGESTION PIPELINE</div></div>
          <div className="ingestion-layout"><div className="ingestion-main">
            <div className="section-heading"><div><h2>Add source documents</h2><p>Upload PDF or TXT files. Multiple files can be processed in one batch.</p></div><span>01 / UPLOAD</span></div>
            <div className={'dropzone ' + (dragging ? 'dragging' : '')} onDragOver={event => { event.preventDefault(); setDragging(true) }} onDragLeave={() => setDragging(false)} onDrop={onDrop}>
              <input ref={fileRef} type="file" accept=".pdf,.txt,application/pdf,text/plain" multiple hidden onChange={event => { if (event.target.files) addFiles(event.target.files) }} />
              <div className="upload-icon"><CloudUpload size={25} /></div><h3>Drop your files here</h3><p>or <button className="browse-button" type="button" onClick={() => fileRef.current?.click()}>browse files</button> from your computer</p>
              <div className="file-rules"><span><FileText size={13} /> PDF documents</span><span><FileText size={13} /> TXT pages</span><span>Up to 20 files per batch</span></div>
            </div>
            {!!files.length && <div className="selected-files"><div className="selected-heading"><strong>Selected files</strong><span>{files.length} file(s)</span></div>
              {files.map(file => <div className="selected-file" key={file.name + file.size + file.lastModified}><div className="file-type-icon"><FileText size={17} /></div><div className="selected-file-info"><strong>{file.name}</strong><span>{formatBytes(file.size)}</span></div><button className="icon-button remove-file" onClick={() => setFiles(current => current.filter(item => item !== file))} aria-label={'Remove ' + file.name}><X size={16} /></button></div>)}
              <div className="upload-actions"><button className="text-button" onClick={() => setFiles([])}>Clear all</button><button className="primary-button" disabled={uploading || !apiOnline} onClick={() => void submitUpload()}>{uploading ? <><LoaderCircle size={16} className="spin" /> Uploading...</> : <><UploadCloud size={16} /> Start ingestion <ArrowRight size={15} /></>}</button></div>
            </div>}
            {uploadError && <div className="inline-alert error"><AlertCircle size={16} />{uploadError}</div>}
            {toast && <div className="inline-alert success"><CheckCircle2 size={16} />{toast}</div>}
            {job && <div className="job-panel"><div className="job-header"><div><div className="eyebrow">LATEST BATCH</div><h2>Ingestion progress</h2></div><span className={'job-status status-' + job.status}>{pretty(job.status)}</span></div>
              <div className="job-progress-row"><span>{completed} of {job.files.length} files indexed successfully</span><strong>{progress}%</strong></div><div className="progress-track"><div className="progress-value" style={{ width: progress + '%' }} /></div>
              <div className="job-file-list">{job.files.map(file => <div className="job-file" key={file.file_id}><div className="file-type-icon"><FileText size={16} /></div><div className="job-file-info"><strong>{file.original_filename}</strong>{typeof file.metadata.pdf_classification === 'string' && <span>{String(file.metadata.pdf_classification).toUpperCase()} PDF · {String(file.metadata.page_count || 0)} pages · {String(file.metadata.chunk_count || 0)} chunks</span>}{typeof file.metadata.document_category === 'string' && <span>{String(file.metadata.document_category).replaceAll('_', ' ')}</span>}{file.error && <span className="job-error">{file.error}</span>}</div><span className={'file-status status-' + file.status}>{['validating','classifying','extracting','chunking','embedding','indexing'].includes(file.status) && <LoaderCircle size={12} className="spin" />}{pretty(file.status)}</span>{['failed', 'blocked'].includes(file.status) && <button className="retry-button" onClick={() => void retryFile(job.job_id, file.file_id)}><RefreshCw size={12} /> Retry</button>}</div>)}</div>
              <div className="job-footer"><span>Batch ID <code>{job.job_id}</code></span><button className="text-button" onClick={async () => setJob(await getIngestionJob(job.job_id))}><RefreshCw size={13} /> Refresh</button></div>
            </div>}
          </div>
          <aside className="ingestion-aside"><div className="aside-card"><div className="aside-icon"><ShieldCheck size={19} /></div><h3>Safe by design</h3><p>Files are validated before processing. Unsupported formats and oversized files are rejected individually.</p></div>
            <div className="aside-card pipeline-card"><div className="aside-card-heading">PROCESSING PIPELINE</div><div className="pipeline-steps"><Step icon={<FileText size={15} />} title="Document validation" detail="Format & integrity checks" /><Step icon={<Layers3 size={15} />} title="Text extraction" detail="PyMuPDF + vision OCR for scans" /><Step icon={<Sparkles size={15} />} title="Chunk & embed" detail="LangChain · BGE-M3" /><Step icon={<Layers3 size={15} />} title="Vector indexing" detail="Qdrant knowledge store" last /></div></div>
            <div className="aside-note"><Clock3 size={15} /><p>Processing runs in a separate worker. Keep the backend worker running while a batch is queued.</p></div>
          </aside></div>
        </section> : <section className="ingestion-page knowledge-page">
          <div className="page-title-row"><div><div className="eyebrow"><Database size={13} /> INDEXED CONTENT</div><h1>Knowledge base</h1><p>Browse the unique source documents currently represented in the vector collection.</p></div><button className="primary-button" onClick={() => { setCatalogLoading(true); setCatalogError(''); void getKnowledgeBase().then(result => setDocuments(result.documents)).catch(error => setCatalogError(error instanceof Error ? error.message : 'Could not load documents.')).finally(() => setCatalogLoading(false)) }}><RefreshCw size={15} /> Refresh list</button></div>
          <div className="catalog-summary"><div><span>INDEXED DOCUMENTS</span><strong>{documents.length}</strong></div><div><span>VECTOR COLLECTION</span><strong>Qdrant</strong></div></div>
          {catalogLoading && <div className="catalog-state"><LoaderCircle className="spin" size={18} /> Loading indexed documents…</div>}
          {catalogError && <div className="inline-alert error"><AlertCircle size={16} />{catalogError}</div>}
          {toast && <div className="inline-alert success"><CheckCircle2 size={16} />{toast}</div>}
          {!catalogLoading && <div className="catalog-list">{documents.length ? documents.map(doc => <article className="catalog-card" key={doc.document_id}>
            <div className="file-type-icon"><FileText size={18} /></div><div className="catalog-info"><strong>{doc.source_file}</strong><span>{(doc.file_type || 'document').toUpperCase()} · {doc.chunk_count.toLocaleString()} chunks · {doc.page_count ? doc.page_count.toLocaleString() + ' pages' : 'Page count unavailable'}</span><small>ID: {doc.document_id}</small></div>
            <button className="delete-document-button" onClick={() => void removeDocument(doc)} disabled={deletingDocument !== null}><Trash2 size={14} />{deletingDocument === doc.document_id ? 'Deleting…' : 'Delete'}</button>
          </article>) : <div className="catalog-state">No indexed documents found in the configured Qdrant collection.</div>}</div>}
        </section>}
      </main>
    </div>
  )
}

function Step({ icon, title, detail, last = false }: { icon: ReactNode; title: string; detail: string; last?: boolean }) {
  return <div className={'pipeline-step ' + (last ? 'last' : '')}><div className="pipeline-step-icon">{icon}</div><div><strong>{title}</strong><span>{detail}</span></div><Check size={14} className="pipeline-check" /></div>
}
function formatBytes(bytes: number) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}
export default App
