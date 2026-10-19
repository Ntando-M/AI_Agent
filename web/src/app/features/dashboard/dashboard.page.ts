import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule, DatePipe, SlicePipe } from '@angular/common';
import { Router } from '@angular/router';
import { AppStateService } from '../../core/services/app-state.service';
import { DatasetStateService } from '../datasets/services/dataset-state.service';
import { DocumentStateService } from '../documents/services/document-state.service';
import { ReportStateService } from '../reports/services/report-state.service';
import { EmptyStateComponent } from '../../core/components/empty-state/empty-state.component';
import { LoadingSpinnerComponent } from '../../core/components/loading-spinner/loading-spinner.component';
import { AppIconComponent } from '../../core/components/app-icon/app-icon.component';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, DatePipe, SlicePipe, EmptyStateComponent, LoadingSpinnerComponent, AppIconComponent],
  template: `
    <div class="dashboard">
      @if (loading()) {
        <div class="dashboard-loading">
          <app-loading-spinner label="Loading dashboard..." />
        </div>
      } @else {
        <!-- Hero Section -->
        <section class="hero-section animate-fade-in">
          <h1 class="hero-title">Welcome to AI Data Analyst</h1>
          <p class="hero-subtitle">Ask questions. Get answers backed by real data.</p>
          <div class="hero-chips">
            @for (prompt of quickStartPrompts; track prompt) {
              <button class="chip" (click)="startChat(prompt)">{{ prompt }}</button>
            }
          </div>
          <div class="hero-actions">
            <button class="btn-primary" (click)="router.navigate(['/chat'])">
              <app-icon name="arrow-right" class="icon-inline"></app-icon> Start chatting
            </button>
            <button class="btn-secondary" (click)="router.navigate(['/reports'])">
              Generate report
            </button>
          </div>
        </section>

        <!-- Overview Cards -->
        <section class="dashboard-grid">
          <!-- System Status -->
          <div class="card status-card">
            <h3 class="card-title">System Status</h3>
            @if (appState.isLive()) {
              <div class="status-row">
                <span class="status-indicator live"></span>
                <span>Live</span>
              </div>
              <div class="status-detail">
                <span>Provider: {{ appState.health()?.provider }}</span>
                <span>Version: {{ appState.health()?.version }}</span>
              </div>
              <div class="status-sources">
                <span class="source-badge" [class.active]="appState.health()?.dataset_loaded">
                  Dataset @if (appState.health()?.dataset_loaded) { <app-icon name="check" class="status-icon"></app-icon> } @else { <app-icon name="x" class="status-icon"></app-icon> }
                </span>
                <span class="source-badge" [class.active]="appState.health()?.database_loaded">
                  Database @if (appState.health()?.database_loaded) { <app-icon name="check" class="status-icon"></app-icon> } @else { <app-icon name="x" class="status-icon"></app-icon> }
                </span>
                <span class="source-badge" [class.active]="appState.health()?.documents_indexed">
                  Docs @if (appState.health()?.documents_indexed) { <app-icon name="check" class="status-icon"></app-icon> } @else { <app-icon name="x" class="status-icon"></app-icon> }
                </span>
              </div>
            } @else {
              <div class="status-offline">Offline</div>
            }
          </div>

          <!-- Datasets Summary -->
          <div class="card datasets-card">
            <div class="card-header">
              <h3 class="card-title">Datasets</h3>
              <a routerLink="/datasets" class="card-link"><app-icon name="arrow-right" class="icon-inline"></app-icon> Manage</a>
            </div>
            <div class="dataset-list">
              @for (ds of datasetState.datasetList(); track ds.name) {
                <div class="dataset-item">
                  <span class="dataset-name">{{ ds.name }}</span>
                  <span class="dataset-meta">{{ ds.rows ?? '—' }} rows</span>
                </div>
              }
              @if (!datasetState.hasDatasets()) {
                <p class="empty-text">No datasets registered</p>
              }
            </div>
          </div>

          <!-- Documents Summary -->
          <div class="card documents-card">
            <div class="card-header">
              <h3 class="card-title">Documents</h3>
              <a routerLink="/documents" class="card-link"><app-icon name="arrow-right" class="icon-inline"></app-icon> Manage</a>
            </div>
            <div class="document-list">
              @for (doc of documentState.documents(); track doc) {
                <div class="document-item">
                  <span class="document-name">{{ doc }}</span>
                </div>
              }
              @if (documentState.documentCount() === 0) {
                <p class="empty-text">No documents indexed</p>
              }
            </div>
          </div>
        </section>

        <!-- Recent Reports -->
        <section class="recent-reports">
          <div class="section-header">
            <h2>Recent Reports</h2>
            <a routerLink="/reports" class="card-link"><app-icon name="arrow-right" class="icon-inline"></app-icon> View all</a>
          </div>
          @if (recentReports().length > 0) {
            <div class="report-cards">
              @for (report of recentReports(); track report.report_id) {
                <div class="report-card" (click)="openReport(report.report_id)">
                  <div class="report-dataset">{{ report.dataset_name ?? 'Unknown' }}</div>
                  <div class="report-preview">{{ report.preview | slice:0:80 }}...</div>
                  <div class="report-meta">{{ report.created_at | date:'short' }}</div>
                </div>
              }
            </div>
          } @else {
            <app-empty-state icon="report" title="No reports yet" message="Generate your first report to see it here." ctaLabel="Generate Report" (cta)="router.navigate(['/reports'])" />
          }
        </section>
      }
    </div>
  `,
  styles: [`
    .dashboard { display: flex; flex-direction: column; gap: var(--space-8); }
    .dashboard-loading { display: flex; justify-content: center; padding: var(--space-12); }

    .hero-section {
      text-align: center;
      padding: var(--space-12) var(--space-6);
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-2xl);
    }
    .hero-title { font-size: var(--text-3xl); margin-bottom: var(--space-3); }
    .hero-subtitle { color: var(--text-secondary); font-size: var(--text-lg); margin-bottom: var(--space-6); }
    .hero-chips {
      display: flex; flex-wrap: wrap; justify-content: center; gap: var(--space-2);
      margin-bottom: var(--space-6);
    }
    .chip {
      padding: var(--space-2) var(--space-4);
      background: var(--bg-elevated);
      border: 1px solid var(--border-standard);
      border-radius: var(--radius-full);
      color: var(--text-secondary);
      font-size: var(--text-sm);
      cursor: pointer;
      transition: all var(--duration-fast) var(--ease-out);
    }
    .chip:hover {
      background: var(--bg-active);
      color: var(--brand-400);
      border-color: var(--brand-400);
    }
    .hero-actions {
      display: flex; justify-content: center; gap: var(--space-3);
    }
    .btn-primary {
      padding: var(--space-3) var(--space-6);
      background: var(--brand-500);
      color: #fff;
      border: none;
      border-radius: var(--radius-md);
      font-weight: var(--weight-medium);
      font-size: var(--text-base);
      cursor: pointer;
    }
    .btn-secondary {
      padding: var(--space-3) var(--space-6);
      background: transparent;
      color: var(--brand-400);
      border: 1px solid var(--brand-400);
      border-radius: var(--radius-md);
      font-weight: var(--weight-medium);
      font-size: var(--text-base);
      cursor: pointer;
    }

    .dashboard-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: var(--space-6);
    }
    .card {
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-xl);
      padding: var(--space-5);
    }
    .card-header {
      display: flex; justify-content: space-between; align-items: center;
      margin-bottom: var(--space-4);
    }
    .card-title { font-size: var(--text-md); font-weight: var(--weight-semibold); }
    .card-link { font-size: var(--text-sm); text-decoration: none; }

    .status-row {
      display: flex; align-items: center; gap: var(--space-2);
      font-size: var(--text-lg); font-weight: var(--weight-semibold);
      margin-bottom: var(--space-3);
    }
    .status-indicator {
      width: 10px; height: 10px; border-radius: 50%;
    }
    .status-indicator.live { background: var(--status-success); animation: pulse-glow 2s infinite; }
    .status-offline { color: var(--status-error); }
    .status-detail {
      display: flex; flex-direction: column; gap: var(--space-1);
      color: var(--text-secondary); font-size: var(--text-sm);
      margin-bottom: var(--space-3);
    }
    .status-sources { display: flex; gap: var(--space-2); flex-wrap: wrap; }
    .source-badge {
      padding: var(--space-1) var(--space-2);
      background: var(--bg-elevated);
      border-radius: var(--radius-sm);
      font-size: var(--text-xs);
      color: var(--text-tertiary);
    }
    .source-badge.active { color: var(--status-success); background: var(--status-success-bg); }

    .dataset-list, .document-list {
      display: flex; flex-direction: column; gap: var(--space-2);
    }
    .dataset-item, .document-item {
      display: flex; justify-content: space-between; align-items: center;
      padding: var(--space-2) var(--space-3);
      background: var(--bg-elevated);
      border-radius: var(--radius-sm);
      font-size: var(--text-sm);
    }
    .dataset-name, .document-name {
      color: var(--text-primary);
      overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    }
    .dataset-meta { color: var(--text-tertiary); }
    .empty-text { color: var(--text-tertiary); font-size: var(--text-sm); text-align: center; padding: var(--space-4); }

    .recent-reports { margin-top: var(--space-4); }
    .section-header {
      display: flex; justify-content: space-between; align-items: center;
      margin-bottom: var(--space-4);
    }
    .report-cards {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: var(--space-4);
    }
    .report-card {
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-lg);
      padding: var(--space-4);
      cursor: pointer;
      transition: all var(--duration-fast) var(--ease-out);
    }
    .report-card:hover {
      border-color: var(--brand-400);
      box-shadow: var(--shadow-glow);
    }
    .report-dataset {
      font-weight: var(--weight-semibold); font-size: var(--text-sm);
      color: var(--brand-400); margin-bottom: var(--space-2);
    }
    .report-preview {
      color: var(--text-secondary); font-size: var(--text-sm);
      margin-bottom: var(--space-2); overflow: hidden; text-overflow: ellipsis;
    }
    .report-meta { color: var(--text-tertiary); font-size: var(--text-xs); }
  `],
})
export class DashboardPage implements OnInit {
  private readonly appState = inject(AppStateService);
  private readonly datasetState = inject(DatasetStateService);
  private readonly documentState = inject(DocumentStateService);
  private readonly reportState = inject(ReportStateService);

  loading = signal(true);
  quickStartPrompts = [
    'What was total revenue?',
    'Which region earned the most?',
    'Show me revenue by product',
    'What is the monthly revenue trend?',
    'Which product has the highest profit margin?',
  ];

  constructor(public router: Router) {}

  async ngOnInit(): Promise<void> {
    await Promise.all([
      this.appState.health() ? Promise.resolve() : this.loadHealth(),
      this.datasetState.loadDatasets(),
      this.documentState.loadDocuments(),
      this.reportState.loadReports(),
    ]);
    this.loading.set(false);
  }

  private async loadHealth(): Promise<void> {
    try {
      // health is loaded by the guard, but ensure it's available
      const { ApiService } = await import('../../core/services/api.service');
      const api = inject(ApiService);
      this.appState.health.set(await api.health());
    } catch {
      // guard already set the error
    }
  }

  startChat(prompt: string): void {
    this.appState.activeSessionId.set(null);
    this.router.navigate(['/chat'], { state: { prefill: prompt } });
  }

  openReport(reportId: string): void {
    this.router.navigate(['/reports'], { state: { openReport: reportId } });
  }

  recentReports() {
    return this.reportState.reports().slice(0, 5);
  }
}
