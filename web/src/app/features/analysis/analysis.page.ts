import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';
import { ApiService } from '../../core/services/api.service';
import { ChatStateService } from '../chat/services/chat-state.service';
import type { AnalyseResponse, AnalysisPayload } from '../../shared/models/api.models';
import { EmptyStateComponent } from '../../core/components/empty-state/empty-state.component';
import { LoadingSpinnerComponent } from '../../core/components/loading-spinner/loading-spinner.component';
import { AppIconComponent } from '../../core/components/app-icon/app-icon.component';

@Component({
  selector: 'app-analysis',
  standalone: true,
  imports: [CommonModule, FormsModule, EmptyStateComponent, LoadingSpinnerComponent, AppIconComponent],
  template: `
    <div class="analysis-page">
      <!-- Header with stateless input -->
      <header class="analysis-header">
        <h1>Standalone Analysis</h1>
        <p>Ask a question for immediate analysis without a session.</p>
        <div class="stateless-input">
          <input type="text"
                 [(ngModel)]="question"
                 placeholder="Type your question..."
                 (keydown.enter)="analyse()"
                 [disabled]="loading()" />
          <button class="btn-primary" (click)="analyse()" [disabled]="loading() || !question.trim()">
            {{ loading() ? 'Analysing...' : 'Analyse' }} <app-icon name="arrow-right" class="icon-inline"></app-icon>
          </button>
        </div>
      </header>

      @if (loading()) {
        <app-loading-spinner label="Analyzing your question..." size="lg" />
      }

      @if (result(); as res) {
        <div class="analysis-result animate-fade-in">
          <!-- Question -->
          <div class="question-block">
            <h3>Question</h3>
            <p>{{ res.question }}</p>
          </div>

          <!-- Answer -->
          <div class="answer-block">
            <h3>Answer</h3>
            <p class="answer-text">{{ res.response.answer }}</p>
          </div>

          <!-- Metadata Row -->
          <div class="metadata-row">
            <!-- Confidence Ring -->
            <div class="confidence-ring">
              <svg viewBox="0 0 100 100" class="ring-svg">
                <circle cx="50" cy="50" r="45" fill="none" stroke="var(--border-standard)" stroke-width="8" />
                <circle cx="50" cy="50" r="45" fill="none"
                        [attr.stroke]="confidenceColor(res.response.confidence)"
                        stroke-width="8"
                        stroke-dasharray="283"
                        [attr.stroke-dashoffset]="283 - (283 * res.response.confidence / 100)"
                        stroke-linecap="round"
                        transform="rotate(-90 50 50)"
                        class="ring-progress" />
                <text x="50" y="50" text-anchor="middle" class="ring-text">{{ res.response.confidence }}%</text>
              </svg>
              <span class="ring-label">Confidence</span>
            </div>

            <!-- Analysis Type Badge -->
            <div class="type-badge">
              <span class="badge-label">Analysis Type</span>
              <span class="badge-value">{{ res.response.analysis_type }}</span>
            </div>
          </div>

          <!-- Evidence Sections -->
          <div class="evidence-sections">
            <!-- Key Findings -->
            @if (res.response.key_findings.length) {
              <div class="evidence-block">
                <h3><app-icon name="search" class="section-icon"></app-icon> Key Findings</h3>
                <ul>
                  @for (finding of res.response.key_findings; track finding) {
                    <li>{{ finding }}</li>
                  }
                </ul>
              </div>
            }

            <!-- Calculations -->
            @if (res.response.calculations_performed.length) {
              <div class="evidence-block">
                <h3><app-icon name="calculator" class="section-icon"></app-icon> Calculations Performed</h3>
                <ul>
                  @for (calc of res.response.calculations_performed; track calc) {
                    <li><code>{{ calc }}</code></li>
                  }
                </ul>
              </div>
            }

            <!-- Sources -->
            @if (res.response.sources.length) {
              <div class="evidence-block">
                <h3><app-icon name="document" class="section-icon"></app-icon> Data Sources</h3>
                <ul>
                  @for (source of res.response.sources; track source) {
                    <li>{{ source }}</li>
                  }
                </ul>
              </div>
            }

            <!-- Tools -->
            @if (res.tools_used.length) {
              <div class="evidence-block">
                <h3><app-icon name="wrench" class="section-icon"></app-icon> Tools Executed</h3>
                <div class="tools-list">
                  @for (tool of res.tools_used; track tool) {
                    <span class="tool-item"><app-icon name="check" class="tool-check-icon"></app-icon> {{ tool }}</span>
                  }
                </div>
              </div>
            }
          </div>

          <!-- Charts (inline images) -->
          @if (res.visualisations.length) {
            <div class="charts-section">
              <h3><app-icon name="chart-line" class="section-icon"></app-icon> Visualisations</h3>
              <div class="chart-grid">
                @for (chart of res.visualisations; track chart) {
                  <figure class="chart-card">
                    <figcaption>{{ chart }}</figcaption>
                  </figure>
                }
              </div>
            </div>
          }

          <!-- Analysis Plan -->
          @if (res.plan && res.plan['steps']) {
            <div class="plan-section">
              <h3><app-icon name="list" class="section-icon"></app-icon> Analysis Plan</h3>
              <ol>
                @for (step of res.plan['steps']; track step) {
                  <li>{{ step }}</li>
                }
              </ol>
            </div>
          }
        </div>
      }

      @if (!loading() && !result()) {
        <app-empty-state icon="search" title="Ask a question to see analysis" message="Use the input above to run a stateless analysis." />
      }
    </div>
  `,
  styles: [`
    .analysis-page { max-width: 900px; margin: 0 auto; display: flex; flex-direction: column; gap: var(--space-8); }
    .analysis-header {
      background: var(--bg-surface); border: 1px solid var(--border-subtle);
      border-radius: var(--radius-2xl); padding: var(--space-6);
    }
    .analysis-header h1 { margin-bottom: var(--space-2); }
    .analysis-header p { color: var(--text-secondary); margin-bottom: var(--space-4); }
    .stateless-input { display: flex; gap: var(--space-3); }
    .stateless-input input {
      flex: 1; padding: var(--space-3) var(--space-4);
      background: var(--bg-elevated); border: 1px solid var(--border-standard);
      border-radius: var(--radius-md); color: var(--text-primary); font-size: var(--text-base);
    }
    .stateless-input input:focus { border-color: var(--brand-400); outline: none; }
    .btn-primary {
      padding: var(--space-3) var(--space-6); background: var(--brand-500); color: #fff;
      border: none; border-radius: var(--radius-md); font-weight: var(--weight-medium); cursor: pointer;
    }
    .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

    .analysis-result { display: flex; flex-direction: column; gap: var(--space-6); }
    .question-block, .answer-block {
      background: var(--bg-surface); border: 1px solid var(--border-subtle);
      border-radius: var(--radius-xl); padding: var(--space-5);
    }
    .question-block h3, .answer-block h3 { color: var(--text-secondary); font-size: var(--text-sm); margin-bottom: var(--space-2); }
    .answer-text { line-height: var(--leading-relaxed); font-size: var(--text-md); }

    .metadata-row { display: flex; gap: var(--space-6); align-items: center; }
    .confidence-ring { display: flex; flex-direction: column; align-items: center; gap: var(--space-2); }
    .ring-svg { width: 100px; height: 100px; }
    .ring-progress { transition: stroke-dashoffset 1s var(--ease-out); }
    .ring-text { font-size: var(--text-md); font-weight: var(--weight-semibold); fill: var(--text-primary); }
    .ring-label { font-size: var(--text-sm); color: var(--text-secondary); }

    .type-badge {
      display: flex; flex-direction: column; gap: var(--space-1);
    }
    .badge-label { font-size: var(--text-xs); color: var(--text-tertiary); text-transform: uppercase; }
    .badge-value {
      padding: var(--space-2) var(--space-4); background: var(--bg-elevated);
      border-radius: var(--radius-full); font-size: var(--text-sm); font-weight: var(--weight-medium);
    }

    .evidence-sections { display: flex; flex-direction: column; gap: var(--space-4); }
    .evidence-block {
      background: var(--bg-surface); border: 1px solid var(--border-subtle);
      border-radius: var(--radius-xl); padding: var(--space-5);
    }
    .evidence-block h3 { font-size: var(--text-md); margin-bottom: var(--space-3); }
    .evidence-block ul { list-style: none; padding: 0; }
    .evidence-block li { padding: var(--space-1) 0; font-size: var(--text-sm); }
    .evidence-block li code {
      background: var(--bg-elevated); padding: var(--space-1) var(--space-2);
      border-radius: var(--radius-xs); font-size: var(--text-xs);
    }
    .tools-list { display: flex; flex-wrap: wrap; gap: var(--space-2); }
    .tool-item {
      padding: var(--space-1) var(--space-3); background: var(--bg-elevated);
      border-radius: var(--radius-sm); font-size: var(--text-sm);
    }

    .charts-section { background: var(--bg-surface); border: 1px solid var(--border-subtle); border-radius: var(--radius-xl); padding: var(--space-5); }
    .charts-section h3 { margin-bottom: var(--space-4); }
    .chart-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: var(--space-4); }
    .chart-card {
      background: var(--bg-elevated); border-radius: var(--radius-md);
      padding: var(--space-4); text-align: center;
    }
    .chart-card figcaption { font-size: var(--text-sm); color: var(--text-secondary); }

    .plan-section { background: var(--bg-surface); border: 1px solid var(--border-subtle); border-radius: var(--radius-xl); padding: var(--space-5); }
    .plan-section h3 { margin-bottom: var(--space-3); }
    .plan-section ol { padding-left: var(--space-5); }
    .plan-section li { padding: var(--space-1) 0; font-size: var(--text-sm); color: var(--text-secondary); }
  `],
})
export class AnalysisPage implements OnInit {
  private readonly api = inject(ApiService);
  private readonly chatState = inject(ChatStateService);
  private readonly route = inject(ActivatedRoute);

  question = '';
  loading = signal(false);
  result = signal<{
    question: string;
    response: AnalysisPayload;
    visualisations: string[];
    tools_used: string[];
    plan: Record<string, any>;
  } | null>(null);

  async ngOnInit(): Promise<void> {
    // If navigated from chat with a session, load the session's analysis
    const sessionId = this.route.snapshot.paramMap.get('sessionId');
    if (sessionId) {
      await this.chatState.loadSession(sessionId);
    }
  }

  async analyse(): Promise<void> {
    const text = this.question.trim();
    if (!text || this.loading()) return;

    this.loading.set(true);
    try {
      const res: AnalyseResponse = await this.api.analyse(text);
      this.result.set({
        question: text,
        response: res.response,
        visualisations: res.visualisations,
        tools_used: res.tools_used,
        plan: res.plan,
      });
    } finally {
      this.loading.set(false);
    }
  }

  confidenceColor(value: number): string {
    if (value >= 80) return 'var(--accent-emerald)';
    if (value >= 60) return 'var(--accent-amber)';
    return 'var(--accent-rose)';
  }
}
