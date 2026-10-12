/**
 * The one place that knows how to talk to the gateway.
 *
 * Every call goes to the .NET gateway on :5000, never to
 * FastAPI on :8000. That is the whole reason the gateway
 * exists: the browser must never hold the API key. If this
 * file ever grew an X-API-Key header, the key would ship
 * inside the bundle where anyone could read it, and the
 * gateway's only job would be undone.
 *
 * A relative base with a dev proxy keeps this true in both
 * environments. In development the proxy forwards /api to
 * the gateway; in production the built app is served behind
 * the gateway itself. Either way the browser only ever
 * addresses its own origin.
 */

import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { firstValueFrom, map } from 'rxjs';

/** Mirrors api/schemas.py AnalysisResponse. */
export interface AnalysisPayload {
  answer: string;
  analysis_type: string;
  datasets_used: string[];
  calculations_performed: string[];
  key_findings: string[];
  sources: string[];
  confidence: number;
}

export interface ChatResponse {
  session_id: string;
  response: AnalysisPayload;
  visualisations: string[];
  tools_used: string[];
  source_labels: string[];
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

/**
 * The evidence stored alongside a recorded answer.
 *
 * Everything a live turn shows is kept, so a restored turn
 * renders the same panels rather than degrading to answer
 * text alone. Optional throughout: a turn recorded before
 * evidence was captured has none, and that is different
 * from a turn whose evidence was genuinely empty.
 */
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

export interface TurnPayload {
  role: string;
  content: string;
  created_at: string | null;
  evidence?: TurnEvidence | null;
}

/** A report as it appears in the list. Mirrors api/schemas.py ReportSummaryPayload. */
export interface ReportSummary {
  report_id: string;
  session_id: string | null;
  dataset_name: string | null;
  created_at: string | null;
  preview: string;
}

/** The four evidence layers, in the order the report asserts them. */
export interface ReportLayers {
  facts?: string[];
  calculated_findings?: string[];
  interpretations?: string[];
  recommendations?: string[];
}

/**
 * One generated report. Mirrors api/schemas.py ReportPayload.
 *
 * `chart_images` carries each chart as a data URL: the browser's
 * only route to the backend is the gateway, whose proxy forwards
 * JSON and text rather than PNG bytes, so the image travels
 * inside the JSON.
 */
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

export interface SessionDetail {
  session_id: string;
  turns: TurnPayload[];
}

export interface DatasetListResponse {
  datasets: {
    name: string;
    path: string;
    rows: number | null;
    columns: string[];
    registered: boolean;
  }[];
}

/**
 * What an upload returns.
 *
 * A dataset answers with its shape; a document answers with
 * indexing state. Both are optional here because the two
 * endpoints share one call site, and the caller knows which
 * kind it sent.
 */
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

/**
 * A failure worth showing the user.
 *
 * The gateway deliberately passes the analysis engine's own
 * error text through rather than replacing it, so `detail` is
 * usually the real explanation. Flattening it into a message
 * string at the throw site keeps every caller from having to
 * remember the shape.
 */
export class GatewayError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = 'GatewayError';
  }
}

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);
  private readonly base = '/api';

  /**
   * Turn any failure into a GatewayError with a readable
   * message.
   *
   * Three cases are handled separately because they need
   * different words: the service being down, a timeout, and
   * the engine rejecting the request. Telling a user "the
   * request failed" when the real problem is that the stack
   * is not running wastes their time.
   */
  private async call<T>(
    work: Promise<T>,
  ): Promise<T> {
    try {
      return await work;
    } catch (error) {
      if (error instanceof HttpErrorResponse) {
        if (error.status === 0) {
          throw new GatewayError(
            'Cannot reach the gateway on port 5000. Is the ' +
              'stack running? Start it with ' +
              'scripts/run_services.py',
            0,
          );
        }

        if (error.status === 429) {
          throw new GatewayError(
            'The model\'s token quota is exhausted. ' +
              'This resets daily - try again later, or set ' +
              'LLM_PROVIDER=ollama to use your local model ' +
              'instead of Groq.',
            429,
          );
        }

        if (error.status === 504) {
          throw new GatewayError(
            'The analysis took too long and was stopped. ' +
              'The question may still be running upstream.',
            504,
          );
        }

        const detail = (error.error as { detail?: string })
          ?.detail;

        throw new GatewayError(
          detail ?? `Request failed with status ${error.status}`,
          error.status,
        );
      }

      throw new GatewayError(
        error instanceof Error
          ? error.message
          : 'Unknown error',
        -1,
      );
    }
  }

  health(): Promise<HealthResponse> {
    return this.call(
      firstValueFrom(
        this.http.get<HealthResponse>(`${this.base}/health`),
      ),
    );
  }

  sessions(): Promise<SessionPayload[]> {
    return this.call(
      firstValueFrom(
        this.http.get<SessionPayload[]>(`${this.base}/sessions`),
      ),
    );
  }

  createSession(
    sessionId: string,
    name?: string,
  ): Promise<SessionPayload> {
    return this.call(
      firstValueFrom(
        this.http.post<SessionPayload>(
          `${this.base}/sessions`,
          { session_id: sessionId, name: name ?? null },
        ),
      ),
    );
  }

  /**
   * Rename a conversation.
   *
   * Goes through createSession deliberately: the API treats
   * a named create of an existing session as a rename, so
   * there is one code path for naming rather than two that
   * can drift. A blank name is sent as null, which the API
   * reads as "leave the stored name alone" rather than
   * "clear it" - clearing would silently rename the
   * conversation to the default label.
   */
  renameSession(
    sessionId: string,
    name: string,
  ): Promise<SessionPayload> {
    return this.call(
      firstValueFrom(
        this.http.post<SessionPayload>(
          `${this.base}/sessions`,
          {
            session_id: sessionId,
            name: name.trim() || null,
          },
        ),
      ),
    );
  }

  reports(): Promise<ReportSummary[]> {
    return this.call(
      firstValueFrom(
        this.http.get<ReportSummary[]>(`${this.base}/reports`),
      ),
    );
  }

  report(reportId: string): Promise<ReportDetail> {
    return this.call(
      firstValueFrom(
        this.http.get<ReportDetail>(
          `${this.base}/reports/${encodeURIComponent(reportId)}`,
        ),
      ),
    );
  }

  /**
   * Generate a report for the loaded dataset.
   *
   * Passes null rather than omitting the key when there is no
   * active session, so the request shape is identical either way
   * and the API's optional field is explicit.
   */
  generateReport(sessionId: string | null): Promise<ReportDetail> {
    return this.call(
      firstValueFrom(
        this.http.post<ReportDetail>(`${this.base}/reports`, {
          session_id: sessionId,
        }),
      ),
    );
  }

  deleteSession(sessionId: string): Promise<void> {
    return this.call(
      firstValueFrom(
        this.http.delete<void>(
          `${this.base}/sessions/${encodeURIComponent(sessionId)}`,
        ),
      ),
    );
  }

  getSession(sessionId: string): Promise<SessionDetail> {
    return this.call(
      firstValueFrom(
        this.http.get<SessionDetail>(
          `${this.base}/sessions/${encodeURIComponent(sessionId)}`,
        ),
      ),
    );
  }

  chat(
    sessionId: string,
    message: string,
  ): Promise<ChatResponse> {
    return this.call(
      firstValueFrom(
        this.http.post<ChatResponse>(`${this.base}/chat`, {
          session_id: sessionId,
          message,
        }),
      ),
    );
  }

  datasets(): Promise<DatasetListResponse> {
    return this.call(
      firstValueFrom(
        this.http.get<DatasetListResponse>(
          `${this.base}/datasets`,
        ),
      ),
    );
  }

  /**
   * Filenames of the documents available for retrieval.
   *
   * The engine stores a document under its filename and
   * retrieves it by the same name, so the filename is also
   * the label the UI shows.
   */
  documents(): Promise<string[]> {
    return this.call(
      firstValueFrom(
        this.http
          .get<{ documents: string[] }>(`${this.base}/documents`)
          .pipe(map((payload) => payload.documents)),
      ),
    );
  }

  deleteDocument(name: string): Promise<void> {
    return this.call(
      firstValueFrom(
        this.http.delete<void>(
          `${this.base}/documents/${encodeURIComponent(name)}`,
        ),
      ),
    );
  }

  deleteDataset(name: string): Promise<void> {
    return this.call(
      firstValueFrom(
        this.http.delete<void>(
          `${this.base}/datasets/${encodeURIComponent(name)}`,
        ),
      ),
    );
  }

  /**
   * Upload a dataset or document.
   *
   * Sent as FormData with the filename intact. The gateway
   * streams it to FastAPI, which enforces the size and
   * extension limits; a rejection comes back as a 400 whose
   * `detail` explains which rule was broken.
   */
  upload(
    kind: 'datasets' | 'documents',
    file: File,
  ): Promise<UploadResult> {
    const form = new FormData();
    form.append('file', file, file.name);

    return this.call(
      firstValueFrom(
        this.http.post<UploadResult>(
          `${this.base}/${kind}`,
          form,
        ),
      ),
    );
  }
}
