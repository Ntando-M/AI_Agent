import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { firstValueFrom, map } from 'rxjs';
import type {
  AnalysisPayload, ChatResponse, AnalyseResponse, SessionPayload,
  TurnPayload, TurnEvidence, SessionDetail, DatasetListResponse,
  DatasetPayload, UploadResult, HealthResponse, ReportSummary,
  ReportLayers, ReportDetail,
} from '../../shared/models/api.models';

export type { AnalysisPayload, ChatResponse, AnalyseResponse, SessionPayload, TurnPayload, TurnEvidence, SessionDetail, DatasetListResponse, DatasetPayload, UploadResult, HealthResponse, ReportSummary, ReportLayers, ReportDetail };

/**
 * A failure worth showing the user.
 *
 * The gateway deliberately passes the analysis engine's own
 * error text through rather than replacing it, so `detail` is
 * usually the real explanation.
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

  private async call<T>(work: Promise<T>): Promise<T> {
    try {
      return await work;
    } catch (error) {
      if (error instanceof HttpErrorResponse) {
        if (error.status === 0) {
          throw new GatewayError(
            'Cannot reach the gateway on port 5000. Is the stack running?',
            0,
          );
        }
        if (error.status === 429) {
          throw new GatewayError(
            'The model\'s token quota is exhausted. Try again later, or set LLM_PROVIDER=ollama.',
            429,
          );
        }
        if (error.status === 504) {
          throw new GatewayError(
            'The analysis took too long and was stopped.',
            504,
          );
        }
        const detail = (error.error as { detail?: string })?.detail;
        throw new GatewayError(
          detail ?? `Request failed with status ${error.status}`,
          error.status,
        );
      }
      throw new GatewayError(
        error instanceof Error ? error.message : 'Unknown error',
        -1,
      );
    }
  }

  // ── Health ──
  health(): Promise<HealthResponse> {
    return this.call(
      firstValueFrom(this.http.get<HealthResponse>(`${this.base}/health`)),
    );
  }

  // ── Sessions ──
  listSessions(): Promise<SessionPayload[]> {
    return this.call(
      firstValueFrom(this.http.get<SessionPayload[]>(`${this.base}/sessions`)),
    );
  }

  createSession(sessionId: string, name?: string): Promise<SessionPayload> {
    return this.call(
      firstValueFrom(
        this.http.post<SessionPayload>(`${this.base}/sessions`, {
          session_id: sessionId,
          name: name ?? null,
        }),
      ),
    );
  }

  renameSession(sessionId: string, name: string): Promise<SessionPayload> {
    return this.call(
      firstValueFrom(
        this.http.post<SessionPayload>(`${this.base}/sessions`, {
          session_id: sessionId,
          name: name.trim() || null,
        }),
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

  deleteSession(sessionId: string): Promise<void> {
    return this.call(
      firstValueFrom(
        this.http.delete<void>(
          `${this.base}/sessions/${encodeURIComponent(sessionId)}`,
        ),
      ),
    );
  }

  // ── Chat ──
  chat(sessionId: string, message: string): Promise<ChatResponse> {
    return this.call(
      firstValueFrom(
        this.http.post<ChatResponse>(`${this.base}/chat`, {
          session_id: sessionId,
          message,
        }),
      ),
    );
  }

  // ── Analyse ──
  analyse(question: string, sessionId?: string | null): Promise<AnalyseResponse> {
    return this.call(
      firstValueFrom(
        this.http.post<AnalyseResponse>(`${this.base}/analyse`, {
          question,
          session_id: sessionId ?? null,
        }),
      ),
    );
  }

  // ── Datasets ──
  listDatasets(): Promise<DatasetListResponse> {
    return this.call(
      firstValueFrom(
        this.http.get<DatasetListResponse>(`${this.base}/datasets`),
      ),
    );
  }

  uploadDataset(file: File): Promise<UploadResult> {
    const form = new FormData();
    form.append('file', file, file.name);
    return this.call(
      firstValueFrom(
        this.http.post<UploadResult>(`${this.base}/datasets`, form),
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

  // ── Documents ──
  listDocuments(): Promise<string[]> {
    return this.call(
      firstValueFrom(
        this.http
          .get<{ documents: string[] }>(`${this.base}/documents`)
          .pipe(map((payload) => payload.documents)),
      ),
    );
  }

  uploadDocument(file: File): Promise<UploadResult> {
    const form = new FormData();
    form.append('file', file, file.name);
    return this.call(
      firstValueFrom(
        this.http.post<UploadResult>(`${this.base}/documents`, form),
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

  // ── Reports ──
  listReports(): Promise<ReportSummary[]> {
    return this.call(
      firstValueFrom(this.http.get<ReportSummary[]>(`${this.base}/reports`)),
    );
  }

  getReport(reportId: string): Promise<ReportDetail> {
    return this.call(
      firstValueFrom(
        this.http.get<ReportDetail>(
          `${this.base}/reports/${encodeURIComponent(reportId)}`,
        ),
      ),
    );
  }

  /**
   * Generate a report. Pass null for dataset to use whatever the
   * engine has loaded. Pass null for session_id for standalone.
   */
  generateReport(
    sessionId: string | null,
    dataset: string | null = null,
  ): Promise<ReportDetail> {
    return this.call(
      firstValueFrom(
        this.http.post<ReportDetail>(`${this.base}/reports`, {
          session_id: sessionId,
          dataset,
        }),
      ),
    );
  }

  deleteReport(reportId: string): Promise<void> {
    return this.call(
      firstValueFrom(
        this.http.delete<void>(
          `${this.base}/reports/${encodeURIComponent(reportId)}`,
        ),
      ),
    );
  }

  // ── Helper: Chart URL from base64 ──
  getChartUrl(base64Data: string): string {
    if (base64Data.startsWith('data:')) return base64Data;
    return `data:image/png;base64,${base64Data}`;
  }
}
