import { Injectable, signal, computed, inject } from '@angular/core';
import { ApiService } from '../../../core/services/api.service';
import type { SessionPayload, TurnPayload } from '../../../shared/models/api.models';

@Injectable({ providedIn: 'root' })
export class ChatStateService {
  private readonly api = inject(ApiService);

  readonly sessions = signal<SessionPayload[]>([]);
  readonly activeSession = signal<string | null>(null);
  readonly turns = signal<TurnPayload[]>([]);
  readonly asking = signal(false);
  readonly question = signal('');

  readonly activeSessionName = computed(() =>
    this.sessions().find(s => s.session_id === this.activeSession())?.name ?? null,
  );
  readonly turnCount = computed(() => this.turns().length);
  readonly busy = computed(() => this.asking());

  async loadSessions(): Promise<void> {
    this.sessions.set(await this.api.listSessions());
  }

  async loadSession(sessionId: string): Promise<void> {
    const detail = await this.api.getSession(sessionId);
    this.turns.set(detail.turns);
    this.activeSession.set(sessionId);
  }

  async createSession(name?: string): Promise<string> {
    const sessionId = crypto.randomUUID().slice(0, 8);
    const created = await this.api.createSession(sessionId, name);
    this.sessions.update(s => [created, ...s]);
    this.activeSession.set(sessionId);
    this.turns.set([]);
    return sessionId;
  }

  async renameSession(sessionId: string, name: string): Promise<void> {
    const updated = await this.api.renameSession(sessionId, name);
    this.sessions.update(s =>
      s.map(x => x.session_id === sessionId ? updated : x),
    );
  }

  async deleteSession(sessionId: string): Promise<void> {
    await this.api.deleteSession(sessionId);
    this.sessions.update(s => s.filter(x => x.session_id !== sessionId));
    if (this.activeSession() === sessionId) {
      const next = this.sessions()[0]?.session_id ?? null;
      if (next) {
        await this.loadSession(next);
      } else {
        this.activeSession.set(null);
        this.turns.set([]);
      }
    }
  }

  async ask(sessionId: string, question: string): Promise<void> {
    this.asking.set(true);
    this.question.set('');

    // Add user turn immediately
    const userTurn: TurnPayload = {
      role: 'user',
      content: question,
      created_at: new Date().toISOString(),
    };
    this.turns.update(t => [...t, userTurn]);

    // Add pending assistant turn
    const pendingTurn: TurnPayload = {
      role: 'assistant',
      content: '',
      created_at: new Date().toISOString(),
      evidence: null,
    };
    this.turns.update(t => [...t, pendingTurn]);

    try {
      const response = await this.api.chat(sessionId, question);
      const answer = response.response.answer;

      // Stream answer character-by-character
      const fullAnswer = answer;
      const chunkSize = 3;
      const tickMs = 15;

      for (let i = 0; i < fullAnswer.length; i += chunkSize) {
        const partial = fullAnswer.slice(0, i + chunkSize);
        const evidence = {
          analysis_type: response.response.analysis_type,
          confidence: response.response.confidence,
          sources: response.response.sources,
          datasets_used: response.response.datasets_used,
          calculations_performed: response.response.calculations_performed,
          key_findings: response.response.key_findings,
          visualisations: response.visualisations,
          tools_used: response.tools_used,
          source_labels: response.source_labels,
        };
        this.turns.update(turns =>
          turns.map((t, idx) =>
            idx === turns.length - 1
              ? { ...t, content: partial, evidence }
              : t,
          ),
        );
        await new Promise(r => setTimeout(r, tickMs));
      }

      // Set final evidence on the complete turn
      this.turns.update(turns =>
        turns.map((t, idx) =>
          idx === turns.length - 1
            ? {
                ...t,
                content: fullAnswer,
                evidence: {
                  analysis_type: response.response.analysis_type,
                  confidence: response.response.confidence,
                  sources: response.response.sources,
                  datasets_used: response.response.datasets_used,
                  calculations_performed: response.response.calculations_performed,
                  key_findings: response.response.key_findings,
                  visualisations: response.visualisations,
                  tools_used: response.tools_used,
                  source_labels: response.source_labels,
                },
              }
            : t,
        ),
      );
    } finally {
      this.asking.set(false);
    }
  }

  setQuestion(text: string): void {
    this.question.set(text);
  }

  clearQuestion(): void {
    this.question.set('');
  }
}
