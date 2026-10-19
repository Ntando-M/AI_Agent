/** Mirrors api/schemas.py AnalysisPayload. */
export interface AnalysisPayload {
  answer: string;
  analysis_type: AnalysisType;
  datasets_used: string[];
  calculations_performed: string[];
  key_findings: string[];
  sources: string[];
  confidence: number;
}

export type AnalysisType = 'general' | 'document' | 'dataset' | 'database' | 'visualisation';

export interface ChatResponse {
  session_id: string;
  response: AnalysisPayload;
  visualisations: string[];
  tools_used: string[];
  source_labels: string[];
  warnings: string[];
}

export interface AnalyseResponse {
  response: AnalysisPayload;
  visualisations: string[];
  tools_used: string[];
  plan: Record<string, any>;
  warnings: string[];
}

export interface SessionPayload {
  session_id: string;
  message_count: number;
  created_at: string | null;
  last_activity_at: string | null;
  preview: string | null;
  name: string;
}

export interface TurnPayload {
  role: 'user' | 'assistant';
  content: string;
  created_at: string | null;
  evidence?: TurnEvidence | null;
}

export interface TurnEvidence {
  analysis_type?: string;
  confidence?: number;
  sources?: string[];
  datasets_used?: string[];
  calculations_performed?: string[];
  key_findings?: string[];
  visualisations?: string[];
  tools_used?: string[];
  source_labels?: string[];
}

export interface SessionDetail {
  session_id: string;
  turns: TurnPayload[];
}

export interface DatasetListResponse {
  datasets: DatasetPayload[];
}

export interface DatasetPayload {
  name: string;
  path: string;
  rows: number | null;
  columns: string[];
  registered: boolean;
}

export interface UploadResult {
  name?: string;
  path?: string;
  rows?: number | null;
  columns?: string[];
  filename?: string;
  stored_path?: string;
  size_bytes?: number;
  indexed?: boolean;
  chunks?: number;
  message?: string;
}

export interface HealthResponse {
  status: string;
  provider: string;
  dataset_loaded: boolean;
  database_loaded: boolean;
  documents_indexed: boolean;
  version: string;
}

export interface ReportSummary {
  report_id: string;
  session_id: string | null;
  dataset_name: string | null;
  created_at: string | null;
  preview: string;
}

export interface ReportLayers {
  facts?: string[];
  calculated_findings?: string[];
  interpretations?: string[];
  recommendations?: string[];
}

export interface ReportDetail {
  report_id: string;
  session_id: string | null;
  content: string;
  created_at: string | null;
  dataset_name: string | null;
  summary: Record<string, unknown>;
  layers: ReportLayers;
  charts: Record<string, string>;
  chart_images: Record<string, string>;
}
