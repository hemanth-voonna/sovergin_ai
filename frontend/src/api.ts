import type {
  AgentInfo,
  AgentRun,
  Dashboard,
  DocumentDetail,
  DocumentItem,
  OCRResult,
  RAGAnswer,
  SandboxResult,
  SettingsInfo,
  ValidationResult,
} from "./types";

const TOKEN_KEY = "sovereignai_token";
const API_BASE_URL = import.meta.env.VITE_API_URL ?? "";

export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) ?? "";
}

export function setToken(token: string): void {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };

  const token = getToken();

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  if (options.body && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    let detail = res.statusText;

    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* keep statusText */
    }

    throw new ApiError(
      res.status,
      typeof detail === "string"
        ? detail
        : JSON.stringify(detail)
    );
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return (await res.json()) as T;
}

// ---- documents ------------------------------------------------------------

export const api = {
  uploadDocument: (file: File) => {
    const form = new FormData();
    form.append("file", file);

    return request<DocumentItem>(
      "/api/documents/upload",
      {
        method: "POST",
        body: form,
      }
    );
  },

  loadSample: () =>
    request<DocumentItem>(
      "/api/documents/sample",
      {
        method: "POST",
      }
    ),

  listDocuments: () =>
    request<{
      items: DocumentItem[];
      total: number;
    }>("/api/documents"),

  getDocument: (id: string) =>
    request<DocumentDetail>(
      `/api/documents/${id}`
    ),

  deleteDocument: (id: string) =>
    request<void>(
      `/api/documents/${id}`,
      {
        method: "DELETE",
      }
    ),

  processDocument: (id: string) =>
    request<DocumentItem>(
      `/api/documents/${id}/process`,
      {
        method: "POST",
      }
    ),

  indexDocument: (id: string) =>
    request<DocumentItem>(
      `/api/documents/${id}/index`,
      {
        method: "POST",
      }
    ),

  pipelineDocument: (id: string) =>
    request<DocumentItem>(
      `/api/documents/${id}/pipeline`,
      {
        method: "POST",
      }
    ),

  // ---- rag -----------------------------------------------------------------

  ragQuery: (
    question: string,
    documentIds?: string[],
    topK?: number
  ) =>
    request<RAGAnswer>(
      "/api/rag/query",
      {
        method: "POST",
        body: JSON.stringify({
          question,
          document_ids: documentIds,
          top_k: topK,
        }),
      }
    ),

  // ---- ocr -----------------------------------------------------------------

  ocrFile: (
    file: File,
    language?: string
  ) => {
    const form = new FormData();
    form.append("file", file);

    const query = language
      ? `?language=${encodeURIComponent(language)}`
      : "";

    return request<OCRResult>(
      `/api/ocr/process${query}`,
      {
        method: "POST",
        body: form,
      }
    );
  },

  ocrDocument: (
    documentId: string,
    language?: string
  ) => {
    const params = new URLSearchParams({
      document_id: documentId,
    });

    if (language) {
      params.set("language", language);
    }

    return request<OCRResult>(
      `/api/ocr/process?${params.toString()}`,
      {
        method: "POST",
      }
    );
  },

  // ---- agents --------------------------------------------------------------

  listAgents: () =>
    request<AgentInfo[]>("/api/agents"),

  getAgent: (id: string) =>
    request<AgentInfo>(
      `/api/agents/${id}`
    ),

  runAgent: (
    agentId: string,
    inputs: Record<string, unknown>
  ) =>
    request<AgentRun>(
      "/api/agents/run",
      {
        method: "POST",
        body: JSON.stringify({
          agent_id: agentId,
          inputs,
        }),
      }
    ),

  // ---- validation ----------------------------------------------------------

  validate: (documentId: string) =>
    request<ValidationResult>(
      "/api/validation/check",
      {
        method: "POST",
        body: JSON.stringify({
          document_id: documentId,
        }),
      }
    ),

  // ---- sandbox -------------------------------------------------------------

  sandboxRun: (
    code: string,
    language: string,
    timeout?: number,
    memoryMb?: number
  ) =>
    request<SandboxResult>(
      "/api/sandbox/run",
      {
        method: "POST",
        body: JSON.stringify({
          code,
          language,
          timeout,
          memory_mb: memoryMb,
        }),
      }
    ),

  // ---- meta ----------------------------------------------------------------

  dashboard: () =>
    request<Dashboard>(
      "/api/dashboard"
    ),

  health: () =>
    request<Record<string, unknown>>(
      "/api/health"
    ),

  settings: () =>
    request<SettingsInfo>(
      "/api/settings"
    ),
};