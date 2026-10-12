/**
 * Application state.
 *
 * Signals throughout rather than a service with observables:
 * the view is a handful of independent pieces of state and
 * signals make each one readable at its point of use without
 * a subscription to keep track of.
 *
 * One rule holds everywhere: nothing here computes an answer.
 * Every figure the user sees was produced by the Python tools
 * and is only being displayed. This layer formats and
 * nothing more, which is what keeps the same numbers
 * appearing whichever client asks.
 */

import {
  Component,
  ElementRef,
  OnInit,
  computed,
  effect,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { KeyValuePipe } from '@angular/common';
import {
  AnalysisPayload,
  ApiService,
  DatasetListResponse,
  GatewayError,
  HealthResponse,
  ReportDetail,
  ReportSummary,
  SessionDetail,
  SessionPayload,
} from './api.service';

/** One question and the answer it produced. */
interface Turn {
  question: string;
  answer: AnalysisPayload | null;
  visualisations: string[];
  toolsUsed: string[];
  error: string | null;
  pending: boolean;
  /**
   * True when this turn came from stored history rather than
   * from a live analysis.
   *
   * A stored conversation keeps the answer's evidence too
   * when it was recorded after evidence began being stored,
   * so a restored turn shows its confidence, sources and
   * panels exactly as the live one did. Only a turn older
   * than that renders as answer text alone, which is the
   * truth about it rather than a missing feature.
   */
  restored?: boolean;
  /**
   * Whether this turn has evidence worth rendering.
   *
   * A live turn always does. A restored turn only does when
   * the stored evidence exists; otherwise the tags and
   * panels are suppressed rather than shown empty.
   */
  hasEvidence?: boolean;
}

@Component({
  selector: 'app-root',
  imports: [FormsModule, KeyValuePipe],
  styleUrl: './app.css',
  templateUrl: './app.html',
})
export class App implements OnInit {
  private readonly api = inject(ApiService);

  // ====================================================
  // STATE
  // ====================================================

  protected readonly health = signal<HealthResponse | null>(null);
  protected readonly healthError = signal<string | null>(null);

  protected readonly sessions = signal<SessionPayload[]>([]);
  protected readonly activeSession = signal<string | null>(null);

  protected readonly datasets = signal<DatasetListResponse | null>(
    null,
  );
  protected readonly uploadMessage = signal<string | null>(null);
  protected readonly uploading = signal(false);

  protected readonly turns = signal<Turn[]>([]);
  protected readonly question = signal('');
  protected readonly asking = signal(false);
  protected readonly banner = signal<string | null>(null);

  /**
   * The new-conversation dialog.
   *
   * `namingOpen` drives the modal; `newName` is its field.
   * Held as component state rather than in the template so
   * the dialog survives a re-render and can be reset in one
   * place.
   */
  protected readonly namingOpen = signal(false);
  protected readonly newName = signal('');

  /**
   * The conversation being renamed, or null when the dialog
   * is creating a new one.
   *
   * One dialog serves both. Renaming and naming a new
   * conversation are the same interaction - type a name,
   * confirm - so a second modal would be duplicated markup
   * and duplicated focus handling that could drift apart.
   */
  protected readonly renamingSession = signal<string | null>(null);

  /** True when the dialog is renaming rather than creating. */
  protected readonly isRenaming = computed(
    () => this.renamingSession() !== null,
  );

  /** The conversation being renamed, for the dialog's hint. */
  protected readonly renamingLabel = computed(() => {
    const id = this.renamingSession();

    if (!id) {
      return null;
    }

    return (
      this.sessions().find((entry) => entry.session_id === id)
        ?.name ?? null
    );
  });

  protected readonly documents = signal<string[]>([]);

  /** Stored reports, newest first. */
  protected readonly reports = signal<ReportSummary[]>([]);

  /**
   * The report being read, or null for the list.
   *
   * One signal for list-and-detail rather than a separate
   * view value: "reports" is one tab, and which report is
   * open within it is not a navigation the user should have
   * to back out of.
   */
  protected readonly activeReport = signal<ReportDetail | null>(null);

  /** True while a report is being generated. */
  protected readonly generatingReport = signal(false);

  /** Report generation problems, shown inside the reports tab. */
  protected readonly reportError = signal<string | null>(null);

  /**
   * Which view is showing.
   *
   * "chat" is the conversation; "manage" is the uploads
   * tab. One signal rather than a boolean per view, so a
   * third view later cannot produce two views open at once.
   */
  protected readonly view = signal<'chat' | 'manage' | 'reports'>('chat');

  /** The sidebar can be collapsed to give the chat full width. */
  protected readonly sidebarOpen = signal(true);

  /**
   * How many documents are indexed.
   *
   * Shown as a badge on the Data tab so the count is visible
   * from the chat view, where the list itself is not.
   */
  protected readonly documentCount = computed(
    () => this.documents().length,
  );

  /** True while a delete is in flight, keyed by item name. */
  protected readonly deleting = signal<string | null>(null);

  /**
   * The scrolling transcript, so a new turn can be brought
   * into view.
   *
   * A question and its answer are appended below the fold on
   * a long conversation, so without this the user types a
   * question and sees nothing change.
   */
  private readonly transcript =
    viewChild<ElementRef<HTMLElement>>('transcript');

  constructor() {
    effect(() => {
      // Both read as dependencies: the transcript grows when
      // turns change, and it is only rendered at all while the
      // chat view is showing. Without the view dependency,
      // loading a conversation from the Data tab would render
      // the transcript later and never scroll it.
      this.turns();
      this.view();

      // After the DOM update rather than during it, so the
      // element exists and its height is final.
      requestAnimationFrame(() => {
        const element = this.transcript()?.nativeElement;

        if (element) {
          element.scrollTop = element.scrollHeight;
        }
      });
    });
  }

  /**
   * The pending upload awaiting confirmation.
   *
   * A file is chosen first and sent only when the user
   * confirms, so picking the wrong file costs nothing. There
   * is no name field: an upload is labelled by its filename,
   * which is what the engine stores and retrieves it by.
   */
  protected readonly pendingUpload = signal<{
    kind: 'datasets' | 'documents';
    file: File;
  } | null>(null);

  /**
   * The name shown for the conversation being viewed.
   *
   * Derived from the loaded list rather than stored twice,
   * so a rename is reflected everywhere at once.
   */
  protected readonly activeSessionName = computed(() => {
    const id = this.activeSession();

    if (!id) {
      return null;
    }

    return (
      this.sessions().find((entry) => entry.session_id === id)
        ?.name ?? null
    );
  });

  /** True while any request is in flight, to disable input. */
  protected readonly busy = computed(
    () => this.asking() || this.uploading(),
  );

  // ====================================================
  // LIFECYCLE
  // ====================================================

  async ngOnInit(): Promise<void> {
    // Health first: if the stack is not up there is no point
    // listing sessions, and the user needs to be told why the
    // page is empty rather than shown an empty list.
    try {
      this.health.set(await this.api.health());
      this.healthError.set(null);
    } catch (error) {
      this.healthError.set(this.describe(error));
      return;
    }

    await this.refreshSessions();
    await this.loadDatasets();
    await this.loadDocuments();
    await this.loadReports();
  }

  // ====================================================
  // LOADING
  // ====================================================

  protected async refreshSessions(): Promise<void> {
    try {
      const sessions = await this.api.sessions();
      this.sessions.set(sessions);

      if (
        this.activeSession() === null &&
        sessions.length > 0
      ) {
        this.activeSession.set(sessions[0].session_id);
      }
    } catch (error) {
      this.banner.set(this.describe(error));
    }
  }

  protected async loadDatasets(): Promise<void> {
    try {
      this.datasets.set(await this.api.datasets());
    } catch (error) {
      this.banner.set(this.describe(error));
    }
  }

  protected async loadDocuments(): Promise<void> {
    try {
      this.documents.set(await this.api.documents());
    } catch (error) {
      this.banner.set(this.describe(error));
    }
  }

  protected async loadReports(): Promise<void> {
    try {
      this.reports.set(await this.api.reports());
    } catch (error) {
      this.banner.set(this.describe(error));
    }
  }

  protected async openReport(reportId: string): Promise<void> {
    try {
      this.activeReport.set(await this.api.report(reportId));
    } catch (error) {
      this.banner.set(this.describe(error));
    }
  }

  protected closeReport(): void {
    this.activeReport.set(null);
  }

  protected async generateReport(): Promise<void> {
    this.generatingReport.set(true);
    this.reportError.set(null);

    try {
      const report = await this.api.generateReport(
        this.activeSession(),
      );

      this.activeReport.set(report);

      await this.loadReports();
    } catch (error) {
      // Shown inside the tab rather than only in the banner:
      // generation is the tab's primary action, so its
      // failure belongs next to the button that caused it.
      this.reportError.set(this.describe(error));
    } finally {
      this.generatingReport.set(false);
    }
  }

  /**
   * The evidence layers in the order a report asserts them,
   * strongest claim first.
   *
   * Fixed order rather than iterating the object: the layers
   * deliberately differ in claim strength, and rendering
   * them in whatever order JSON happened to preserve would
   * present a recommendation before the fact it rests on.
   */
  protected readonly reportSections = [
    {
      key: 'facts' as const,
      title: 'Facts',
      hint: 'What the data contains.',
    },
    {
      key: 'calculated_findings' as const,
      title: 'Calculated findings',
      hint: 'Derived by deterministic arithmetic.',
    },
    {
      key: 'interpretations' as const,
      title: 'Interpretations',
      hint: 'What the pattern appears to mean.',
    },
    {
      key: 'recommendations' as const,
      title: 'Recommendations',
      hint: 'Suggested actions.',
    },
  ];

  /** A short date for a report row, or a dash when unknown. */
  protected reportDate(createdAt: string | null): string {
    if (!createdAt) {
      return '—';
    }

    const parsed = new Date(createdAt);

    return Number.isNaN(parsed.getTime())
      ? '—'
      : parsed.toLocaleString();
  }

  /**
   * Human-readable size for a chosen file.
   *
   * Shown in the confirmation dialog so the user can tell
   * two similarly named files apart before committing.
   */
  protected fileSize(bytes: number): string {
    if (bytes < 1024) {
      return `${bytes} B`;
    }

    if (bytes < 1024 * 1024) {
      return `${(bytes / 1024).toFixed(1)} KB`;
    }

    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  // ====================================================
  // ACTIONS
  // ====================================================

  /**
   * Open the naming dialog for a new conversation.
   *
   * The field starts empty; the placeholder shows the name
   * that will be used if the user just presses Create.
   */
  protected openNamingDialog(): void {
    this.renamingSession.set(null);
    this.newName.set('');
    this.namingOpen.set(true);
  }

  /**
   * Open the same dialog pre-filled with the current name.
   *
   * Pre-filling matters: renaming is usually a correction,
   * so starting from the existing name beats starting from
   * an empty field and retyping it.
   */
  protected openRenameDialog(sessionId: string): void {
    const existing =
      this.sessions().find(
        (entry) => entry.session_id === sessionId,
      )?.name ?? '';

    this.renamingSession.set(sessionId);
    this.newName.set(existing);
    this.namingOpen.set(true);
  }

  protected closeNamingDialog(): void {
    this.namingOpen.set(false);
    this.newName.set('');
    this.renamingSession.set(null);
  }

  protected onNamingKeydown(event: KeyboardEvent): void {
    if (event.key === 'Enter') {
      event.preventDefault();
      void this.confirmNaming();
    } else if (event.key === 'Escape') {
      event.preventDefault();
      this.closeNamingDialog();
    }
  }

  /** The dialog's confirm action, in whichever mode it is in. */
  protected async confirmNaming(): Promise<void> {
    if (this.isRenaming()) {
      await this.renameSession();
    } else {
      await this.startSession();
    }
  }

  protected async renameSession(): Promise<void> {
    const sessionId = this.renamingSession();

    if (!sessionId) {
      return;
    }

    const name = this.newName().trim();

    // An empty field would be read by the API as "leave the
    // name alone", which looks like a silent failure, so it
    // is refused here with an explanation instead.
    if (!name) {
      this.banner.set(
        'A conversation needs a name to be renamed.',
      );
      return;
    }

    try {
      await this.api.renameSession(sessionId, name);

      this.closeNamingDialog();

      await this.refreshSessions();
    } catch (error) {
      // The dialog stays open with the typed name so the
      // user can correct it rather than start again.
      this.banner.set(this.describe(error));
    }
  }

  protected async startSession(): Promise<void> {
    // A blank name is allowed: the conversation is created
    // unnamed and the API supplies the default label, which
    // is what the dialog's placeholder promised.
    const name = this.newName().trim();

    const id = `web-${Date.now().toString(36)}`;

    try {
      await this.api.createSession(id, name || undefined);

      this.activeSession.set(id);
      this.turns.set([]);

      this.closeNamingDialog();

      await this.refreshSessions();
    } catch (error) {
      this.banner.set(this.describe(error));
    }
  }

  protected async removeSession(
    sessionId: string,
  ): Promise<void> {
    try {
      await this.api.deleteSession(sessionId);

      if (this.activeSession() === sessionId) {
        this.activeSession.set(null);
        this.turns.set([]);
      }

      await this.refreshSessions();
    } catch (error) {
      this.banner.set(this.describe(error));
    }
  }

  protected showView(next: 'chat' | 'manage' | 'reports'): void {
    this.view.set(next);
  }

  protected toggleSidebar(): void {
    this.sidebarOpen.update((open) => !open);
  }

  protected async removeDocument(name: string): Promise<void> {
    await this.removeUpload(name, () => this.api.deleteDocument(name));
  }

  protected async removeDataset(name: string): Promise<void> {
    await this.removeUpload(name, () => this.api.deleteDataset(name));
  }

  /**
   * Delete an upload and refresh the list it came from.
   *
   * The confirm is a browser prompt rather than a modal: a
   * delete is destructive and irreversible, and one extra
   * click is the right cost. The row shows a busy state while
   * the request is in flight so a slow delete cannot be
   * double-fired.
   */
  private async removeUpload(
    name: string,
    remove: () => Promise<void>,
  ): Promise<void> {
    if (!confirm(`Delete "${name}"? This cannot be undone.`)) {
      return;
    }

    this.deleting.set(name);

    try {
      await remove();

      await this.loadDocuments();
      await this.loadDatasets();

      this.uploadMessage.set(`Deleted ${name}.`);
    } catch (error) {
      this.banner.set(this.describe(error));
    } finally {
      this.deleting.set(null);
    }
  }

  protected async loadSession(sessionId: string): Promise<void> {
    this.activeSession.set(sessionId);
    this.turns.set([]);

    try {
      const detail: SessionDetail = await this.api.getSession(sessionId);

      const loaded: Turn[] = [];

      for (const turn of detail.turns) {
        if (turn.role === 'user') {
          loaded.push({
            question: turn.content,
            answer: null,
            visualisations: [],
            toolsUsed: [],
            error: null,
            pending: false,
          });
        } else if (turn.role === 'assistant') {
          // Evidence is present only for turns recorded after
          // it began being stored. A turn without it is
          // rendered as answer text alone rather than with
          // zero confidence, which would be a claim the
          // engine never made.
          const evidence = turn.evidence ?? null;

          loaded.push({
            question: '',
            answer: {
              answer: turn.content,
              analysis_type: evidence?.analysis_type ?? '',
              datasets_used: evidence?.datasets_used ?? [],
              calculations_performed:
                evidence?.calculations_performed ?? [],
              key_findings: evidence?.key_findings ?? [],
              sources: evidence?.sources ?? [],
              confidence: evidence?.confidence ?? 0,
            },
            visualisations: evidence?.visualisations ?? [],
            toolsUsed: evidence?.tools_used ?? [],
            error: null,
            pending: false,
            restored: true,
            // Drives whether the evidence panels render at
            // all. Without evidence there is nothing truthful
            // to show, so the turn stays answer-only.
            hasEvidence: evidence !== null,
          });
        }
      }

      this.turns.set(loaded);
    } catch (error) {
      this.banner.set(this.describe(error));
    }
  }

  protected useSample(text: string): void {
    this.question.set(text);
  }

  protected async ask(): Promise<void> {
    const text = this.question().trim();

    if (!text || this.busy()) {
      return;
    }

    // Start a session implicitly so a first question works
    // without a setup step, mirroring POST /chat on the
    // Python side.
    let sessionId = this.activeSession();

    if (sessionId === null) {
      sessionId = `web-${Date.now().toString(36)}`;

      try {
        await this.api.createSession(sessionId);
        this.activeSession.set(sessionId);
      } catch (error) {
        this.banner.set(this.describe(error));
        return;
      }
    }

    const turn: Turn = {
      question: text,
      answer: null,
      visualisations: [],
      toolsUsed: [],
      error: null,
      pending: true,
    };

    this.turns.update((turns) => [...turns, turn]);
    this.question.set('');
    this.asking.set(true);

    try {
      const result = await this.api.chat(sessionId, text);

      this.turns.update((turns) =>
        turns.map((entry) =>
          entry === turn
            ? {
                ...entry,
                answer: result.response,
                visualisations: result.visualisations,
                toolsUsed: result.tools_used,
                pending: false,
                hasEvidence: true,
              }
            : entry,
        ),
      );

      await this.refreshSessions();
    } catch (error) {
      this.turns.update((turns) =>
        turns.map((entry) =>
          entry === turn
            ? {
                ...entry,
                error: this.describe(error),
                pending: false,
              }
            : entry,
        ),
      );
    } finally {
      this.asking.set(false);
    }
  }

  /**
   * A file was chosen. Hold it and open the confirmation
   * dialog; nothing is sent until the user confirms.
   */
  protected chooseUpload(
    input: HTMLInputElement,
    kind: 'datasets' | 'documents',
  ): void {
    const file = input.files?.[0];

    // Reset the input immediately so choosing the same file
    // twice in a row still fires a change event.
    input.value = '';

    if (!file) {
      return;
    }

    this.uploadMessage.set(null);
    this.pendingUpload.set({ kind, file });
  }

  protected cancelUpload(): void {
    this.pendingUpload.set(null);
  }

  protected onUploadKeydown(event: KeyboardEvent): void {
    if (event.key === 'Enter') {
      event.preventDefault();
      void this.confirmUpload();
    } else if (event.key === 'Escape') {
      event.preventDefault();
      this.cancelUpload();
    }
  }

  protected async confirmUpload(): Promise<void> {
    const pending = this.pendingUpload();

    if (!pending) {
      return;
    }

    const { kind, file } = pending;

    this.uploading.set(true);
    this.uploadMessage.set(null);

    try {
      const result = await this.api.upload(kind, file);

      this.uploadMessage.set(this.uploadResult(kind, file, result));

      if (kind === 'datasets') {
        await this.loadDatasets();
      } else {
        await this.loadDocuments();
      }

      this.pendingUpload.set(null);
    } catch (error) {
      // The engine explains which limit was broken, so its
      // message is shown rather than a generic failure. The
      // dialog stays open so the user can pick another file.
      this.uploadMessage.set(this.describe(error));
    } finally {
      this.uploading.set(false);
    }
  }

  /**
   * A confirmation line for a finished upload.
   *
   * A document that stored but failed to index is reported
   * as such rather than as a success: it will not be
   * retrievable until it indexes, and saying "uploaded"
   * would hide that.
   */
  private uploadResult(
    kind: 'datasets' | 'documents',
    file: File,
    result: unknown,
  ): string {
    if (kind === 'documents') {
      const payload = result as {
        indexed?: boolean;
        chunks?: number;
        message?: string;
      };

      if (payload.indexed === false) {
        return payload.message ?? `Stored ${file.name} but it was not indexed.`;
      }

      return `Uploaded and indexed ${file.name} (${payload.chunks ?? 0} chunks).`;
    }

    const payload = result as {
      rows?: number | null;
      columns?: string[];
    };

    const rows = payload.rows ?? 0;
    const columns = payload.columns?.length ?? 0;

    return `Uploaded ${file.name} — ${rows} rows, ${columns} columns.`;
  }

  protected dismiss(): void {
    this.banner.set(null);
  }

  /**
   * Confidence as a percentage for display.
   *
   * Formatting only. The confidence value itself was set by
   * the model and validated by Pydantic on the Python side.
   */
  protected confidencePercent(value: number): string {
    return `${Math.round(value * 100)}%`;
  }

  /**
   * A chart path is a server filesystem path, not a URL the
   * browser can fetch. Showing just the filename is honest:
   * it identifies the artefact for someone with filesystem
   * access, and pretending it is a link would produce a
   * broken image.
   */
  protected chartName(path: string): string {
    const parts = path.split(/[\\/]/);

    return parts[parts.length - 1] || path;
  }

  private describe(error: unknown): string {
    if (error instanceof GatewayError) {
      return error.message;
    }

    return error instanceof Error
      ? error.message
      : 'Unknown error';
  }
}
