import { Component, OnInit, inject, signal, effect, ViewChild, ElementRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';
import { ChatStateService } from './services/chat-state.service';
import { AppStateService } from '../../core/services/app-state.service';
import { DatasetStateService } from '../datasets/services/dataset-state.service';
import { EmptyStateComponent } from '../../core/components/empty-state/empty-state.component';
import { AppIconComponent } from '../../core/components/app-icon/app-icon.component';
import { ConfirmDialogComponent } from '../../core/components/confirm-dialog/confirm-dialog.component';

@Component({
  selector: 'app-chat',
  standalone: true,
  imports: [CommonModule, FormsModule, EmptyStateComponent, AppIconComponent, ConfirmDialogComponent],
  template: `
    <div class="chat-page">
      <!-- Session Sidebar -->
      <aside class="chat-sidebar" [class.mobile-hidden]="!sidebarVisible()">
        <div class="sidebar-header">
          <h3>Conversations</h3>
          <button class="btn-new" (click)="showNewSession.set(true)">+ New</button>
        </div>

        <div class="session-list">
          @for (session of chatState.sessions(); track session.session_id) {
            <div class="session-item"
                 [class.active]="chatState.activeSession() === session.session_id"
                 (click)="selectSession(session.session_id)">
              <div class="session-info">
                <span class="session-name">{{ session.name }}</span>
                <span class="session-meta">{{ session.message_count }} messages</span>
              </div>
              <div class="session-actions">
                <button class="icon-btn" (click)="renameSession(session.session_id, session.name); $event.stopPropagation()" aria-label="Rename"><app-icon name="edit" class="icon-btn-icon"></app-icon></button>
                <button class="icon-btn" (click)="confirmDelete.set(session.session_id); $event.stopPropagation()" aria-label="Delete"><app-icon name="close" class="icon-btn-icon"></app-icon></button>
              </div>
            </div>
          }
          @if (chatState.sessions().length === 0) {
            <p class="no-sessions">No conversations yet. Start one!</p>
          }
        </div>

        @if (datasetState.hasDatasets()) {
          <div class="sidebar-dataset">
            <label>Active Dataset</label>
            <select [(ngModel)]="selectedDataset" (change)="onDatasetChange()">
              <option value="">Default</option>
              @for (ds of datasetState.datasetList(); track ds.name) {
                <option [value]="ds.name">{{ ds.name }} ({{ ds.rows }} rows)</option>
              }
            </select>
          </div>
        }
      </aside>

      <!-- Main Chat Area -->
      <div class="chat-main">
        <!-- Chat Header -->
        <header class="chat-header">
          <button class="btn-back" (click)="sidebarVisible.set(!sidebarVisible())"><app-icon name="menu" class="icon-btn-icon"></app-icon></button>
          <div class="chat-title">
            <h2>{{ chatState.activeSessionName() || 'New Conversation' }}</h2>
          </div>
        </header>

        <!-- Transcript -->
        <div class="chat-transcript" #transcriptRef role="log" aria-live="polite" aria-label="Conversation transcript">
          @if (chatState.turns().length === 0 && !chatState.asking()) {
            <div class="chat-empty">
              <app-empty-state icon="chat" title="Ask a question to begin analysis" ctaLabel="" />
              <div class="sample-prompts">
                @for (prompt of samplePrompts; track prompt) {
                  <button class="chip" (click)="usePrompt(prompt)">{{ prompt }}</button>
                }
              </div>
            </div>
          }

          @for (turn of chatState.turns(); track $index) {
            <div class="turn" [class]="turn.role">
              <!-- User Turn -->
              @if (turn.role === 'user') {
                <div class="turn-user">
                  <div class="turn-avatar">You</div>
                  <div class="turn-content">{{ turn.content }}</div>
                </div>
              }

              <!-- Assistant Turn -->
              @if (turn.role === 'assistant') {
                <div class="turn-assistant">
                  <app-icon name="robot" class="avatar-icon ai-icon"></app-icon>
                  <div class="turn-content">
                    @if (turn.content) {
                      <p class="answer-text">{{ turn.content }}</p>
                    }

                    @if (turn.evidence) {
                      <div class="evidence-panel">
                        <!-- Confidence Meter -->
                        @if (turn.evidence.confidence) {
                          <div class="confidence-meter">
                            <div class="confidence-label">Confidence</div>
                            <div class="confidence-bar">
                              <div class="confidence-fill" [style.width.%]="(turn.evidence.confidence*100)"></div>
                            </div>
                            <span class="confidence-value">{{ turn.evidence.confidence*100 }}%</span>
                          </div>
                        }

                        <!-- Analysis Type -->
                        @if (turn.evidence.analysis_type) {
                          <div class="analysis-badge">{{ turn.evidence.analysis_type }} analysis</div>
                        }

                        <!-- Key Findings -->
                        @if (turn.evidence.key_findings?.length) {
                          <div class="evidence-section">
                            <h4><app-icon name="search" class="section-icon"></app-icon> Key Findings</h4>
                            <ul>
                              @for (finding of turn.evidence.key_findings; track finding) {
                                <li>{{ finding }}</li>
                              }
                            </ul>
                          </div>
                        }

                        <!-- Calculations -->
                        @if (turn.evidence.calculations_performed?.length) {
                          <div class="evidence-section">
                            <h4><app-icon name="calculator" class="section-icon"></app-icon> Calculations</h4>
                            <ul>
                              @for (calc of turn.evidence.calculations_performed; track calc) {
                                <li><code>{{ calc }}</code></li>
                              }
                            </ul>
                          </div>
                        }

                        <!-- Sources -->
                        @if (turn.evidence.sources?.length) {
                          <div class="evidence-section">
                            <h4><app-icon name="document" class="section-icon"></app-icon> Sources</h4>
                            <ul>
                              @for (source of turn.evidence.sources; track source) {
                                <li>{{ source }}</li>
                              }
                            </ul>
                          </div>
                        }

                        <!-- Tools -->
                        @if (turn.evidence.tools_used?.length) {
                          <div class="evidence-section">
                            <h4><app-icon name="wrench" class="section-icon"></app-icon> Tools Used</h4>
                            <div class="tools-chips">
                              @for (tool of turn.evidence.tools_used; track tool) {
                                <span class="tool-chip">{{ tool }}</span>
                              }
                            </div>
                          </div>
                        }

                        <!-- Charts (filenames in chat view) -->
                        @if (turn.evidence.visualisations?.length) {
                          <div class="evidence-section">
                            <h4><app-icon name="chart-line" class="section-icon"></app-icon> Charts Generated</h4>
                            <div class="chart-filenames">
                              @for (chart of turn.evidence.visualisations; track chart) {
                                <code class="chart-filename">{{ chart }}</code>
                              }
                            </div>
                          </div>
                        }
                      </div>
                    }
                  </div>
                </div>
              }
            </div>
          }

          <!-- Typing Indicator -->
          @if (chatState.asking()) {
            <div class="typing-indicator">
              <div class="typing-dots">
                <span></span><span></span><span></span>
              </div>
              <span class="typing-label">Analyzing...</span>
            </div>
          }
        </div>

        <!-- Composer -->
        <div class="chat-composer">
          <div class="composer-input-wrap">
            <input type="text"
                   class="composer-input"
                   [(ngModel)]="question"
                   placeholder="Ask a question about your data..."
                   (keydown.enter)="send()"
                   [disabled]="chatState.busy()" />
            <button class="btn-send"
                    (click)="send()"
                    [disabled]="!question.trim() || chatState.busy()">
              Send <app-icon name="send" class="icon-inline"></app-icon>
            </button>
          </div>
          <div class="composer-chips">
            @for (prompt of samplePrompts; track prompt) {
              <button class="chip small" (click)="usePrompt(prompt)">{{ prompt }}</button>
            }
          </div>
        </div>
      </div>

      <!-- New Session Dialog -->
      @if (showNewSession()) {
        <div class="dialog-backdrop" (click)="showNewSession.set(false)">
          <div class="dialog" (click)="$event.stopPropagation()">
            <h3>New Conversation</h3>
            <input type="text" [(ngModel)]="newSessionName" placeholder="Session name (optional)" />
            <div class="dialog-actions">
              <button (click)="showNewSession.set(false)">Cancel</button>
              <button class="btn-primary" (click)="createSession()">Create</button>
            </div>
          </div>
        </div>
      }

      <!-- Rename Dialog -->
      @if (showRename()) {
        <div class="dialog-backdrop" (click)="showRename.set(false)">
          <div class="dialog" (click)="$event.stopPropagation()">
            <h3>Rename Session</h3>
            <input type="text" [(ngModel)]="renameValue" />
            <div class="dialog-actions">
              <button (click)="showRename.set(false)">Cancel</button>
              <button class="btn-primary" (click)="confirmRename()">Rename</button>
            </div>
          </div>
        </div>
      }

      <!-- Delete Conversation Dialog -->
      @if (confirmDelete()) {
        <app-confirm-dialog
          title="Delete Conversation"
          message="This action cannot be undone. Delete this conversation and its messages?"
          confirmLabel="Delete"
          [danger]="true"
          (confirm)="deleteSession()"
          (cancel)="confirmDelete.set(null)" />
      }
    </div>
  `,
  styles: [`
    .chat-page { display: flex; height: 100%; gap: 0; }
    .chat-sidebar {
      width: 280px;
      background: var(--bg-surface);
      border-right: 1px solid var(--border-subtle);
      display: flex; flex-direction: column;
      flex-shrink: 0;
    }
    .sidebar-header {
      display: flex; justify-content: space-between; align-items: center;
      padding: var(--space-4);
      border-bottom: 1px solid var(--border-subtle);
    }
    .sidebar-header h3 { font-size: var(--text-md); }
    .btn-new {
      padding: var(--space-1) var(--space-3);
      background: var(--brand-500); color: #fff; border: none;
      border-radius: var(--radius-md); cursor: pointer; font-size: var(--text-sm);
    }
    .session-list { flex: 1; overflow-y: auto; padding: var(--space-2); }
    .session-item {
      display: flex; justify-content: space-between; align-items: center;
      padding: var(--space-3); border-radius: var(--radius-md); cursor: pointer;
      transition: background var(--duration-fast) var(--ease-out);
    }
    .session-item:hover { background: var(--bg-hover); }
    .session-item.active { background: var(--bg-active); }
    .session-name { display: block; font-size: var(--text-sm); font-weight: var(--weight-medium); }
    .session-meta { font-size: var(--text-xs); color: var(--text-tertiary); }
    .session-actions { display: flex; gap: var(--space-1); }
    .icon-btn {
      background: none; border: none; color: var(--text-tertiary);
      cursor: pointer; padding: var(--space-1); font-size: var(--text-sm);
    }
    .icon-btn:hover { color: var(--text-primary); }
    .no-sessions { text-align: center; color: var(--text-tertiary); padding: var(--space-4); font-size: var(--text-sm); }

    .sidebar-dataset { padding: var(--space-4); border-top: 1px solid var(--border-subtle); }
    .sidebar-dataset label { display: block; font-size: var(--text-xs); color: var(--text-tertiary); margin-bottom: var(--space-2); }
    .sidebar-dataset select {
      width: 100%; padding: var(--space-2); background: var(--bg-elevated);
      border: 1px solid var(--border-standard); border-radius: var(--radius-sm);
      color: var(--text-primary); font-size: var(--text-sm);
    }

    .chat-main { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
    .chat-header {
      display: flex; align-items: center; gap: var(--space-3);
      padding: var(--space-3) var(--space-5);
      border-bottom: 1px solid var(--border-subtle);
    }
    .btn-back {
      background: none; border: none; color: var(--text-secondary);
      font-size: var(--text-lg); cursor: pointer; padding: var(--space-2);
    }
    .chat-title h2 { font-size: var(--text-md); }

    .chat-transcript {
      flex: 1; overflow-y: auto; padding: var(--space-5);
      display: flex; flex-direction: column; gap: var(--space-6);
    }
    .chat-empty { display: flex; flex-direction: column; align-items: center; padding: var(--space-8); }
    .sample-prompts { display: flex; flex-wrap: wrap; justify-content: center; gap: var(--space-2); margin-top: var(--space-4); }

    .turn { display: flex; gap: var(--space-3); }
    .turn-avatar {
      width: 32px; height: 32px; border-radius: 50%;
      display: flex; align-items: center; justify-content: center;
      font-size: var(--text-sm); font-weight: var(--weight-semibold);
      flex-shrink: 0; background: var(--bg-elevated);
    }
    .turn-avatar.ai { background: var(--brand-500); }
    .turn-content { flex: 1; min-width: 0; }
    .answer-text { color: var(--text-primary); line-height: var(--leading-relaxed); margin-bottom: var(--space-3); }

    .evidence-panel {
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-lg);
      padding: var(--space-4);
    }
    .confidence-meter {
      display: flex; align-items: center; gap: var(--space-3);
      margin-bottom: var(--space-3);
    }
    .confidence-label { font-size: var(--text-sm); color: var(--text-secondary); }
    .confidence-bar {
      flex: 1; height: 6px; background: var(--bg-elevated);
      border-radius: var(--radius-full); overflow: hidden;
    }
    .confidence-fill {
      height: 100%; border-radius: var(--radius-full);
      background: var(--accent-emerald);
      transition: width var(--duration-slow) var(--ease-out);
    }
    .confidence-value { font-size: var(--text-sm); font-weight: var(--weight-semibold); color: var(--accent-emerald); }

    .analysis-badge {
      display: inline-block; padding: var(--space-1) var(--space-2);
      background: var(--brand-500); color: #fff;
      border-radius: var(--radius-sm); font-size: var(--text-xs);
      margin-bottom: var(--space-3);
    }

    .evidence-section { margin-top: var(--space-3); padding-top: var(--space-3); border-top: 1px solid var(--border-subtle); }
    .evidence-section h4 { font-size: var(--text-sm); color: var(--text-secondary); margin-bottom: var(--space-2); }
    .evidence-section ul { list-style: none; padding: 0; }
    .evidence-section li {
      padding: var(--space-1) 0; color: var(--text-primary); font-size: var(--text-sm);
    }
    .evidence-section li code {
      background: var(--bg-elevated); padding: var(--space-1) var(--space-2);
      border-radius: var(--radius-xs); font-size: var(--text-xs);
    }
    .tools-chips { display: flex; flex-wrap: wrap; gap: var(--space-2); }
    .tool-chip {
      padding: var(--space-1) var(--space-2); background: var(--bg-elevated);
      border-radius: var(--radius-sm); font-size: var(--text-xs); color: var(--text-secondary);
    }
    .chart-filenames { display: flex; flex-wrap: wrap; gap: var(--space-2); }
    .chart-filename {
      padding: var(--space-1) var(--space-2); background: var(--bg-elevated);
      border-radius: var(--radius-sm); font-size: var(--text-xs); color: var(--accent-sky);
    }

    .typing-indicator { display: flex; align-items: center; gap: var(--space-3); }
    .typing-dots { display: flex; gap: 4px; }
    .typing-dots span {
      width: 8px; height: 8px; border-radius: 50%;
      background: var(--brand-400); animation: typing-dot 1.4s infinite;
    }
    .typing-dots span:nth-child(2) { animation-delay: 0.2s; }
    .typing-dots span:nth-child(3) { animation-delay: 0.4s; }
    @keyframes typing-dot {
      0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
      30% { transform: translateY(-4px); opacity: 1; }
    }
    .typing-label { color: var(--text-tertiary); font-size: var(--text-sm); }

    .chat-composer {
      padding: var(--space-4) var(--space-5);
      border-top: 1px solid var(--border-subtle);
      background: var(--bg-surface);
    }
    .composer-input-wrap { display: flex; gap: var(--space-3); margin-bottom: var(--space-3); }
    .composer-input {
      flex: 1; padding: var(--space-3) var(--space-4);
      background: var(--bg-elevated); border: 1px solid var(--border-standard);
      border-radius: var(--radius-md); color: var(--text-primary);
      font-size: var(--text-base); outline: none;
    }
    .composer-input:focus { border-color: var(--brand-400); }
    .btn-send {
      padding: var(--space-3) var(--space-5);
      background: var(--brand-500); color: #fff; border: none;
      border-radius: var(--radius-md); font-weight: var(--weight-medium); cursor: pointer;
    }
    .btn-send:disabled { opacity: 0.5; cursor: not-allowed; }
    .composer-chips { display: flex; flex-wrap: wrap; gap: var(--space-2); }
    .chip {
      padding: var(--space-1) var(--space-3); background: var(--bg-elevated);
      border: 1px solid var(--border-standard); border-radius: var(--radius-full);
      color: var(--text-secondary); font-size: var(--text-xs); cursor: pointer;
    }
    .chip:hover { background: var(--bg-active); color: var(--brand-400); }
    .chip.small { font-size: var(--text-xs); padding: var(--space-1) var(--space-2); }

    .dialog-backdrop {
      position: fixed; inset: 0; background: var(--bg-overlay);
      display: flex; align-items: center; justify-content: center; z-index: 100;
    }
    .dialog {
      background: var(--bg-elevated); border: 1px solid var(--border-standard);
      border-radius: var(--radius-xl); padding: var(--space-6);
      max-width: 400px; width: 90%;
    }
    .dialog h3 { margin-bottom: var(--space-4); }
    .dialog input {
      width: 100%; padding: var(--space-3); margin-bottom: var(--space-4);
      background: var(--bg-surface); border: 1px solid var(--border-standard);
      border-radius: var(--radius-md); color: var(--text-primary);
    }
    .dialog-actions { display: flex; justify-content: flex-end; gap: var(--space-3); }
    .dialog-actions button {
      padding: var(--space-2) var(--space-4); border-radius: var(--radius-md);
      border: 1px solid var(--border-standard); background: transparent;
      color: var(--text-secondary); cursor: pointer;
    }
    .dialog-actions .btn-primary {
      background: var(--brand-500); color: #fff; border-color: var(--brand-500);
    }

    @media (max-width: 768px) {
      .chat-sidebar { display: none; }
      .chat-sidebar:not(.mobile-hidden) { display: flex; position: fixed; z-index: 200; }
    }
  `],
})
export class ChatPage implements OnInit {
  protected readonly chatState = inject(ChatStateService);
  protected readonly appState = inject(AppStateService);
  private readonly datasetState = inject(DatasetStateService);
  private readonly route = inject(ActivatedRoute);

  question = '';
  selectedDataset = '';
  sidebarVisible = signal(false);
  showNewSession = signal(false);
  showRename = signal(false);
  confirmDelete = signal<string | null>(null);
  newSessionName = '';
  renameValue = '';
  renameTargetId = '';

  samplePrompts = [
    'What was total revenue?',
    'Which region earned the most?',
    'Show me revenue by product',
    'Monthly trend?',
    'Missing data?',
    'Distribution of revenue?',
  ];

  @ViewChild('transcriptRef') transcriptRef?: ElementRef;

  constructor() {
    // Auto-scroll when turns change
    effect(() => {
      this.chatState.turns();
      this.chatState.asking();
      requestAnimationFrame(() => {
        const el = this.transcriptRef?.nativeElement;
        if (el) el.scrollTop = el.scrollHeight;
      });
    });
  }

  async ngOnInit(): Promise<void> {
    await this.chatState.loadSessions();
    if (this.chatState.sessions().length > 0) {
      await this.chatState.loadSession(this.chatState.sessions()[0].session_id);
    }
    await this.datasetState.loadDatasets();

    // Handle prefill from navigation state
    const navigation = history.state;
    if (navigation?.prefill) {
      this.question = navigation.prefill;
    }
  }

  async send(): Promise<void> {
    const text = this.question.trim();
    if (!text || this.chatState.busy()) return;

    let sessionId = this.chatState.activeSession();
    if (!sessionId) {
      sessionId = await this.chatState.createSession('Conversation');
    }

    await this.chatState.ask(sessionId, text);
  }

  usePrompt(prompt: string): void {
    this.question = prompt;
  }

  async selectSession(sessionId: string): Promise<void> {
    await this.chatState.loadSession(sessionId);
  }

  async createSession(): Promise<void> {
    const name = this.newSessionName.trim() || undefined;
    await this.chatState.createSession(name);
    this.showNewSession.set(false);
    this.newSessionName = '';
  }

  renameSession(sessionId: string, currentName: string): void {
    this.renameTargetId = sessionId;
    this.renameValue = currentName;
    this.showRename.set(true);
  }

  async confirmRename(): Promise<void> {
    if (this.renameTargetId && this.renameValue.trim()) {
      await this.chatState.renameSession(this.renameTargetId, this.renameValue.trim());
    }
    this.showRename.set(false);
  }

  async deleteSession(): Promise<void> {
    const sessionId = this.confirmDelete();
    if (!sessionId) return;
    await this.chatState.deleteSession(sessionId);
    this.confirmDelete.set(null);
  }

  onDatasetChange(): void {
    this.appState.activeDataset.set(this.selectedDataset);
  }
}
