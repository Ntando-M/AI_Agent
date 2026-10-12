import { describe, expect, it } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import {
  provideHttpClientTesting,
  HttpTestingController,
} from '@angular/common/http/testing';

import { ApiService, GatewayError } from './api.service';

/**
 * These tests exist to pin one thing above all others: the
 * browser never sends the API key.
 *
 * The .NET gateway exists solely to hold that key server-side.
 * A single header added here would ship the secret inside the
 * JS bundle, where anyone reading dev tools could copy it and
 * then read every dataset and delete every session. That is
 * the one regression worth failing a build over.
 */
describe('ApiService', () => {
  let service: ApiService;
  let http: HttpTestingController;

  function build(): void {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    });

    service = TestBed.inject(ApiService);
    http = TestBed.inject(HttpTestingController);
  }

  function settle(): void {
    http.verify();
  }

  describe('security', () => {
    it('never sends an API key header', async () => {
      build();

      // The promise is created but not awaited before the
      // request is flushed. Awaiting first would wait on a
      // response the test has not sent yet.
      const pending = service.health();

      const request = http.expectOne('/api/health');

      expect(
        request.request.headers.has('X-API-Key'),
      ).toBe(false);

      request.flush({ status: 'ok' });

      await pending;
      settle();
    });

    it('targets its own origin, not FastAPI directly', () => {
      build();

      service.health().catch(() => undefined);

      const request = http.expectOne('/api/health');

      // A relative URL means the browser only ever addresses
      // the dev server, which proxies to the gateway. An
      // absolute http://127.0.0.1:8000 would bypass the
      // gateway entirely and break CORS.
      expect(request.request.url).toBe('/api/health');

      request.flush({ status: 'ok' });
      settle();
    });

    it('never puts the key in a query string', () => {
      build();

      service.sessions().catch(() => undefined);

      const request = http.expectOne('/api/sessions');

      expect(request.request.url).not.toContain('key');
      expect(request.request.urlWithParams).not.toContain(
        'api_key',
      );

      request.flush([]);
      settle();
    });
  });

  describe('health', () => {
    it('reports the engine state', async () => {
      build();

      const pending = service.health();

      http.expectOne('/api/health').flush({
        status: 'ok',
        provider: 'groq',
        dataset_loaded: true,
        database_loaded: true,
        documents_indexed: false,
        version: '0.9.0',
      });

      const health = await pending;

      expect(health.provider).toBe('groq');
      expect(health.dataset_loaded).toBe(true);
      expect(health.documents_indexed).toBe(false);

      settle();
    });
  });

  describe('failure messages', () => {
    it('explains that the stack is not running when unreachable', async () => {
      build();

      const pending = service.health();

      http.expectOne('/api/health').error(
        new ProgressEvent('error'),
        { status: 0, statusText: 'Unknown Error' },
      );

      await expect(pending).rejects.toThrow(
        /Cannot reach the gateway/,
      );

      settle();
    });

    it('explains a timeout rather than saying "failed"', async () => {
      build();

      const pending = service.chat('s1', 'hi');

      http
        .expectOne('/api/chat')
        .flush(
          { detail: 'too slow' },
          { status: 504, statusText: 'Gateway Timeout' },
        );

      await expect(pending).rejects.toThrow(
        /took too long/,
      );

      settle();
    });

    it("surfaces the engine's own error detail", async () => {
      build();

      const pending = service.upload('datasets', fakeFile());

      http.expectOne('/api/datasets').flush(
        {
          detail:
            "Unsupported dataset type: '.exe' is not accepted.",
        },
        { status: 400, statusText: 'Bad Request' },
      );

      // The analysis service explains which rule was broken,
      // and that explanation is more useful than any generic
      // message the browser could invent.
      await expect(pending).rejects.toThrow(
        /Unsupported dataset type/,
      );

      settle();
    });

    it('falls back to the status code when there is no detail', async () => {
      build();

      const pending = service.sessions();

      http
        .expectOne('/api/sessions')
        .flush(null, { status: 500, statusText: 'Server Error' });

      await expect(pending).rejects.toThrow(/500/);

      settle();
    });

    it('throws a GatewayError carrying the status', async () => {
      build();

      const pending = service.health();

      http
        .expectOne('/api/health')
        .flush(null, { status: 404, statusText: 'Not Found' });

      await expect(pending).rejects.toBeInstanceOf(
        GatewayError,
      );

      settle();
    });
  });

  describe('sessions', () => {
    it('sends the requested session id', async () => {
      build();

      const pending = service.createSession('abc');

      const request = http.expectOne('/api/sessions');

      expect(request.request.method).toBe('POST');
      expect(request.request.body).toEqual({
        session_id: 'abc',
        name: null,
      });

      request.flush({
        session_id: 'abc',
        message_count: 0,
        created_at: null,
        last_activity_at: null,
        preview: null,
        name: 'Untitled conversation',
      });

      await pending;
      settle();
    });

    it('sends a name when one is given', async () => {
      build();

      const pending = service.createSession('abc', 'Q3 review');

      const request = http.expectOne('/api/sessions');

      expect(request.request.body).toEqual({
        session_id: 'abc',
        name: 'Q3 review',
      });

      request.flush({
        session_id: 'abc',
        message_count: 0,
        created_at: null,
        last_activity_at: null,
        preview: null,
        name: 'Q3 review',
      });

      await pending;
      settle();
    });

    it('escapes a session id in the path', async () => {
      build();

      service
        .deleteSession('id with/slash')
        .catch(() => undefined);

      // Without escaping the slash would change the route and
      // delete a different session, or 404.
      const request = http.expectOne(
        '/api/sessions/id%20with%2Fslash',
      );

      expect(request.request.method).toBe('DELETE');

      request.flush({});
      settle();
    });
  });

  describe('documents', () => {
    it('unwraps the documents envelope', async () => {
      build();

      const pending = service.documents();

      const request = http.expectOne('/api/documents');

      expect(request.request.method).toBe('GET');

      // The endpoint answers {"documents": [...]}; callers
      // want the list, not the envelope.
      request.flush({
        documents: ['policy.pdf', 'notes.txt'],
      });

      await expect(pending).resolves.toEqual([
        'policy.pdf',
        'notes.txt',
      ]);

      settle();
    });
  });

  describe('chat', () => {
    it('posts the question to the session', async () => {
      build();

      const pending = service.chat(
        'demo',
        'Which region earned the most?',
      );

      const request = http.expectOne('/api/chat');

      expect(request.request.body).toEqual({
        session_id: 'demo',
        message: 'Which region earned the most?',
      });

      request.flush({
        session_id: 'demo',
        response: {
          answer: 'Gauteng.',
          analysis_type: 'dataset',
          datasets_used: [],
          calculations_performed: [],
          key_findings: [],
          sources: [],
          confidence: 1,
        },
        visualisations: [],
        tools_used: ['execute_read_only_sql'],
        source_labels: [],
        warnings: [],
      });

      const result = await pending;

      expect(result.tools_used).toEqual([
        'execute_read_only_sql',
      ]);

      settle();
    });
  });

  describe('renameSession', () => {
    it('posts the new name to the sessions endpoint', async () => {
      build();

      const pending = service.renameSession(
        'web-abc',
        'Q3 revenue',
      );

      const request = http.expectOne('/api/sessions');

      expect(request.request.method).toBe('POST');
      expect(request.request.body).toEqual({
        session_id: 'web-abc',
        name: 'Q3 revenue',
      });

      request.flush({});

      await pending;
    });

    it('trims the name before sending it', async () => {
      build();

      const pending = service.renameSession(
        'web-abc',
        '   padded   ',
      );

      const request = http.expectOne('/api/sessions');

      expect(request.request.body.name).toBe('padded');

      request.flush({});

      await pending;
    });

    it('sends null for an empty name rather than an empty string', async () => {
      build();

      // The API reads a null name as "leave the stored name
      // alone". Sending "" would be a different request with
      // the same shape, so this pins the distinction: an
      // empty rename must not silently become a clear.
      const pending = service.renameSession(
        'web-abc',
        '   ',
      );

      const request = http.expectOne('/api/sessions');

      expect(request.request.body.name).toBeNull();

      request.flush({});

      await pending;
    });
  });

  describe('reports', () => {
    it('lists reports from the reports endpoint', async () => {
      build();

      const pending = service.reports();

      const request = http.expectOne('/api/reports');

      expect(request.request.method).toBe('GET');

      request.flush([]);

      await pending;
    });

    it('fetches one report by id', async () => {
      build();

      const pending = service.report('abc123');

      const request = http.expectOne('/api/reports/abc123');

      expect(request.request.method).toBe('GET');

      request.flush({});

      await pending;
    });

    it('generates a report with the session id', async () => {
      build();

      const pending = service.generateReport('web-1');

      const request = http.expectOne('/api/reports');

      expect(request.request.method).toBe('POST');
      expect(request.request.body).toEqual({
        session_id: 'web-1',
      });

      request.flush({});

      await pending;
    });

    it('sends null when generating outside a session', async () => {
      build();

      const pending = service.generateReport(null);

      const request = http.expectOne('/api/reports');

      expect(request.request.body).toEqual({
        session_id: null,
      });

      request.flush({});

      await pending;
    });
  });

  describe('upload', () => {
    it('sends multipart form data with the filename intact', async () => {
      build();

      const file = fakeFile('sales.csv');

      service
        .upload('datasets', file)
        .catch(() => undefined);

      const request = http.expectOne('/api/datasets');

      expect(request.request.body).toBeInstanceOf(FormData);

      const form = request.request.body as FormData;

      // The filename is what the analysis service checks
      // against its allow-list, so losing it here would turn
      // every upload into a rejected one.
      expect((form.get('file') as File).name).toBe(
        'sales.csv',
      );

      request.flush({});
      settle();
    });
  });
});

function fakeFile(name = 'payload.exe'): File {
  return new File(['id,name\n1,x'], name, {
    type: 'text/csv',
  });
}
