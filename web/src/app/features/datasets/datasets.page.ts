import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { DatasetStateService } from './services/dataset-state.service';
import { AppStateService } from '../../core/services/app-state.service';
import { ToastService } from '../../core/services/toast.service';
import type { DatasetPayload } from '../../shared/models/api.models';
import { EmptyStateComponent } from '../../core/components/empty-state/empty-state.component';
import { ConfirmDialogComponent } from '../../core/components/confirm-dialog/confirm-dialog.component';
import { UploadDropZoneComponent } from '../../shared/components/upload-drop-zone/upload-drop-zone.component';
import { AppIconComponent } from '../../core/components/app-icon/app-icon.component';

@Component({
  selector: 'app-datasets',
  standalone: true,
  imports: [CommonModule, EmptyStateComponent, ConfirmDialogComponent, UploadDropZoneComponent, AppIconComponent],
  template: `
    <div class="datasets-page">
      <header class="page-header">
        <h1>Datasets</h1>
        <p>Upload, inspect, and manage your data files.</p>
      </header>

      <!-- Upload Zone -->
      <section class="upload-section">
        <app-upload-drop-zone
          accept=".csv,.xlsx,.xls"
          [maxSizeMb]="10"
          label="Drag files here or click to browse"
          hint=".csv .xlsx .xls — Max 10 MB"
          [uploading]="datasetState.uploading()"
          (fileSelected)="onFileSelected($event)" />
      </section>

      @if (datasetState.uploadMessage()) {
        <div class="upload-message success">{{ datasetState.uploadMessage() }}</div>
      }

      <!-- Registered Datasets -->
      <section class="datasets-section">
        <h2>Registered Datasets</h2>
        @if (!datasetState.hasDatasets()) {
          <app-empty-state icon="chart-bar" title="No datasets registered" message="Upload a dataset to get started." ctaLabel="Upload Dataset" />
        } @else {
          <div class="dataset-grid">
            @for (ds of datasetState.datasetList(); track ds.name) {
              <div class="dataset-card">
                <div class="dataset-header">
                  <app-icon name="chart-bar" class="dataset-icon"></app-icon>
                  <h3 class="dataset-name">{{ ds.name }}</h3>
                  @if (appState.activeDataset() === ds.name) {
                    <span class="active-badge"><span class="active-dot"></span> ACTIVE</span>
                  }
                </div>

                <div class="dataset-meta">
                  <span>{{ ds.rows ?? '—' }} rows × {{ ds.columns.length }} columns</span>
                </div>

                <!-- Column Preview (expandable) -->
                <div class="column-preview">
                  <button class="expand-btn" (click)="toggleColumns(ds.name)">
                    <app-icon [name]="expandedDataset() === ds.name ? 'chevron-down' : 'chevron-right'" class="chevron"></app-icon> Columns: {{ ds.columns.slice(0, 3).join(', ') }}{{ ds.columns.length > 3 ? '...' : '' }}
                  </button>
                  @if (expandedDataset() === ds.name) {
                    <div class="column-list">
                      @for (col of ds.columns; track col) {
                        <span class="column-tag">{{ col }}</span>
                      }
                    </div>
                  }
                </div>

                <div class="dataset-actions">
                  <button class="btn-sm" (click)="setActive(ds.name)" [disabled]="appState.activeDataset() === ds.name">
                    {{ appState.activeDataset() === ds.name ? 'Active' : 'Set Active' }}
                  </button>
                  <button class="btn-sm btn-danger" (click)="confirmDelete.set(ds.name)">Delete</button>
                </div>
              </div>
            }
          </div>
        }
      </section>

      <!-- Delete Confirmation -->
      @if (confirmDelete()) {
        <app-confirm-dialog
          title="Delete Dataset"
          message="This will permanently delete the dataset and its data. This cannot be undone."
          confirmLabel="Delete"
          [danger]="true"
          (confirm)="deleteDataset()"
          (cancel)="confirmDelete.set(null)" />
      }
    </div>
  `,
  styles: [`
    .datasets-page { max-width: 900px; margin: 0 auto; display: flex; flex-direction: column; gap: var(--space-8); }
    .page-header h1 { margin-bottom: var(--space-2); }
    .page-header p { color: var(--text-secondary); }

    .upload-section { margin-bottom: var(--space-2); }
    .upload-message {
      padding: var(--space-3) var(--space-4);
      background: var(--status-success-bg); color: var(--status-success);
      border-radius: var(--radius-md); font-size: var(--text-sm);
    }
    .upload-message.success { background: var(--status-success-bg); color: var(--status-success); }

    .datasets-section h2 { margin-bottom: var(--space-4); }
    .dataset-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
      gap: var(--space-4);
    }
    .dataset-card {
      background: var(--bg-surface); border: 1px solid var(--border-subtle);
      border-radius: var(--radius-xl); padding: var(--space-5);
      display: flex; flex-direction: column; gap: var(--space-3);
    }
    .dataset-header { display: flex; align-items: center; gap: var(--space-2); }
    .dataset-icon { font-size: var(--text-lg); }
    .dataset-name { flex: 1; font-size: var(--text-md); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .active-badge { font-size: var(--text-xs); color: var(--status-success); font-weight: var(--weight-semibold); }

    .dataset-meta { color: var(--text-secondary); font-size: var(--text-sm); }

    .column-preview { background: var(--bg-elevated); border-radius: var(--radius-md); padding: var(--space-2); }
    .expand-btn {
      background: none; border: none; color: var(--text-secondary);
      cursor: pointer; font-size: var(--text-sm); padding: var(--space-1);
    }
    .expand-btn:hover { color: var(--text-primary); }
    .column-list { display: flex; flex-wrap: wrap; gap: var(--space-1); padding: var(--space-2); }
    .column-tag {
      padding: 2px var(--space-2); background: var(--bg-surface);
      border-radius: var(--radius-xs); font-size: var(--text-xs); font-family: var(--font-mono);
    }

    .dataset-actions { display: flex; gap: var(--space-2); }
    .btn-sm {
      padding: var(--space-2) var(--space-3); background: var(--bg-elevated);
      border: 1px solid var(--border-standard); border-radius: var(--radius-sm);
      color: var(--text-secondary); font-size: var(--text-xs); cursor: pointer;
    }
    .btn-sm:hover:not(:disabled) { background: var(--bg-active); color: var(--brand-400); }
    .btn-sm:disabled { opacity: 0.5; cursor: not-allowed; }
    .btn-sm.btn-danger:hover { background: var(--status-error-bg); color: var(--status-error); border-color: var(--status-error); }
  `],
})
export class DatasetsPage implements OnInit {
  protected readonly datasetState = inject(DatasetStateService);
  protected readonly appState = inject(AppStateService);
  private readonly toastSvc = inject(ToastService);

  confirmDelete = signal<string | null>(null);
  expandedDataset = signal<string | null>(null);
  pendingFile = signal<File | null>(null);

  async ngOnInit(): Promise<void> {
    await this.datasetState.loadDatasets();
  }

  onFileSelected(file: File): void {
    this.pendingFile.set(file);
  }

  toggleColumns(name: string): void {
    this.expandedDataset.update(current => current === name ? null : name);
  }

  setActive(name: string): void {
    this.appState.activeDataset.set(name);
    this.toastSvc.success(`Active dataset set to ${name}`);
  }

  async deleteDataset(): Promise<void> {
    const name = this.confirmDelete();
    if (!name) return;
    await this.datasetState.delete(name);
    if (this.appState.activeDataset() === name) {
      const remaining = this.datasetState.datasetList();
      this.appState.activeDataset.set(remaining[0]?.name ?? '');
    }
    this.confirmDelete.set(null);
    this.toastSvc.success(`Dataset ${name} deleted`);
  }
}
