// Shared API types — mirrors backend/app/schemas.py

export interface DocumentItem {
  id: string;
  filename: string;
  original_name: string;
  file_type: string;
  size_bytes: number;
  checksum: string;
  status: string;
  error_message: string | null;
  ocr_used: boolean;
  page_count: number;
  char_count: number;
  chunk_count: number;
  validation_status: string;
  created_at: string | null;
  updated_at: string | null;
}

export interface PageOut {
  page_number: number;
  text: string;
  source: string;
  confidence: number | null;
}

export interface DocumentDetail extends DocumentItem {
  pages: PageOut[];
  extracted_text: string | null;
}

export interface SourceOut {
  document_id: string;
  filename: string;
  page: number | null;
  chunk_index: number | null;
  score: number | null;
  snippet: string;
}

export interface RAGAnswer {
  question: string;
  answer: string;
  grounded: boolean;
  sources: SourceOut[];
  model: string;
  took_ms: number;
  mode: string;
}

export interface OCRPageOut {
  page_number: number;
  text: string;
  confidence: number;
}

export interface OCRResult {
  text: string;
  pages: OCRPageOut[];
  language: string;
  engine: string;
  took_ms: number;
}

export interface AgentInfo {
  id: string;
  name: string;
  description: string;
  category: string;
  icon: string;
  input_schema: {
    type: string;
    properties: Record<string, { type: string; description?: string; enum?: string[]; default?: string }>;
    required?: string[];
  };
  output: string;
  tools: string[];
  instructions: string;
  requires_llm: boolean;
}

export interface AgentRun {
  agent_id: string;
  status: string;
  output: Record<string, unknown>;
  logs: string[];
  took_ms: number;
  mode: string;
}

export interface ValidationIssue {
  severity: string;
  category: string;
  field: string | null;
  message: string;
}

export interface ValidationResult {
  document_id: string;
  status: string;
  score: number;
  issues: ValidationIssue[];
  fields: Record<string, string>;
  took_ms: number;
}

export interface SandboxResult {
  status: string;
  stdout: string;
  stderr: string;
  exit_code: number | null;
  duration_ms: number;
  language: string;
  log: string[];
}

export interface Activity {
  id: number;
  action: string;
  actor: string;
  entity_type: string;
  entity_id: string;
  message: string;
  details: Record<string, unknown> | null;
  created_at: string | null;
}

export interface Dashboard {
  documents: Record<string, number>;
  rag_queries: number;
  agent_runs: number;
  sandbox_runs: number;
  vectors_indexed: number;
  health: {
    status: string;
    version: string;
    uptime_s: number;
    cpu_percent: number;
    memory: { used_gb: number; total_gb: number; percent: number };
    disk: { used_gb: number; total_gb: number; percent: number };
    services: Record<string, string>;
  };
  recent_activity: Activity[];
  activity_series: { day: string; count: number }[];
}

export interface SettingsInfo {
  llm_provider: string;
  llm_model: string;
  llm_configured: boolean;
  embedding_provider: string;
  embedding_model: string;
  vector_db: string;
  ocr_lang: string;
  max_upload_mb: number;
  auth_enabled: boolean;
  sandbox_executor: string;
  chunk_size: number;
  chunk_overlap: number;
  top_k: number;
}

export interface AuthUser {
  id?: string;
  username: string;
  full_name?: string;
  is_active?: boolean;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  username: string;
  full_name: string;
}