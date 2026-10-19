import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { DocumentStateService } from './services/document-state.service';
import { ToastService } from '../../core/services/toast.service';
import { EmptyStateComponent } from '../../core/components/empty-state/empty-state.component';
import { ConfirmDialogComponent } from '../../core/components/confirm-dialog/confirm-dialog.component';
import { UploadDropZoneComponent } from '../../shared/components/upload-drop-zone/upload-drop-zone.component';
import { AppIconComponent } from '../../core/components/app-icon/app-icon.component';

@Component({
  selector: 'app-documents',
  standalone: true,
  imports: [CommonModule, EmptyStateComponent, ConfirmDialogComponent, UploadDropZoneComponent, AppIconComponent],
  template: `
    <div class="documents-page">
      <header class="page-header">
        <h1>Documents</h1>
        <p>Upload source material for the RAG retrieval engine.</p>
      </header>

      <!-- Upload Zone -->
      <section class="upload-section">
        <app-upload-drop-zone
          accept=".txt,.pdf,.docx"
          [maxSizeMb]="10"
          label="Drag files here or click to browse"
          hint=".txt .pdf .docx — Max 10 MB"
          [uploading]="documentState.uploading()"
          (fileSelected)="onFileSelected($event)" />
      </section>

      @if (documentState.uploadMessage()) {
        <div class="upload-message success">{{ documentState.uploadMessage() }}</div>
      }

      <!-- Indexed Documents -->
      <section class="documents-section">
        <h2>Indexed Documents ({{ documentState.documentCount() }})</h2>
        @if (documentState.documentCount() === 0) {
          <app-empty-state icon="document" title="No documents indexed" message="Upload a document to make it searchable." ctaLabel="Upload Document" />
        } @else {
          <div class="document-list">
            @for (doc of documentState.documents(); track doc) {
              <div class="document-card">
                <div class="document-header">
                  <app-icon name="document" class="document-icon"></app-icon>
                  <h3 class="document-name">{{ doc }}</h3>
                  <span class="index-badge indexed">Indexed <app-icon name="check" class="check-icon"></app-icon></span>
                </div>
                <div class="document-actions">
                  <button class="btn-sm" (click)="viewChunks(doc)">View Chunks</button>
                  <button class="btn-sm" (click)="reindex(doc)">Re-index</button>
                  <button class="btn-sm btn-danger" (click)="confirmDelete.set(doc)">Delete</button>
                </div>
              </div>
            }
          </div>
        }
      </section>

      <!-- Info Panel -->
      <section class="info-panel">
        <h3>How Documents are Processed</h3>
        <ol>
          <li>Loaded and split into chunks</li>
          <li>Embedded using sentence-transformers</li>
          <li>Stored in ChromaDB vector store</li>
        </ol>
        <p>When you delete a document, both the file and its indexed chunks are removed.</p>
      </section>

      <!-- Delete Confirmation -->
      @if (confirmDelete()) {
        <app-confirm-dialog
          title="Delete Document"
          message="This will permanently delete the document and its indexed chunks. This cannot be undone."
          confirmLabel="Delete"
          [danger]="true"
          (confirm)="deleteDocument()"
          (cancel)="confirmDelete.set(null)" />
      }
    </div>
  `,
  styles: [`
    .documents-page { max-width: 800px; margin: 0 auto; display: flex; flex-direction: column; gap: var(--space-8); }
    .page-header h1 { margin-bottom: var(--space-2); }
    .page-header p { color: var(--text-secondary); }

    .upload-section { margin-bottom: var(--space-2); }
    .upload-message {
      padding: var(--space-3) var(--space-4);
      background: var(--status-success-bg); color: var(--status-success);
      border-radius: var(--radius-md); font-size: var(--text-sm);
    }

    .documents-section h2 { margin-bottom: var(--space-4); }
    .document-list { display: flex; flex-direction: column; gap: var(--space-3); }
    .document-card {
      background: var(--bg-surface); border: 1px solid var(--border-subtle);
      border-radius: var(--radius-xl); padding: var(--space-4) var(--space-5);
    }
    .document-header { display: flex; align-items: center; gap: var(--space-3); margin-bottom: var(--space-3); }
    .document-icon { font-size: var(--text-lg); }
    .document-name { flex: 1; font-size: var(--text-md); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .index-badge {
      padding: var(--space-1) var(--space-2); border-radius: var(--radius-sm);
      font-size: var(--text-xs); font-weight: var(--weight-medium);
    }
    .index-badge.indexed { background: var(--status-success-bg); color: var(--status-success); }

    .document-actions { display: flex; gap: var(--space-2); }
    .btn-sm {
      padding: var(--space-2) var(--space-3); background: var(--bg-elevated);
      border: 1px solid var(--border-standard); border-radius: var(--radius-sm);
      color: var(--text-secondary); font-size: var(--text-xs); cursor: pointer;
    }
    .btn-sm:hover { background: var(--bg-active); color: var(--brand-400); }
    .btn-sm.btn-danger:hover { background: var(--status-error-bg); color: var(--status-error); border-color: var(--status-error); }

    .info-panel {
      background: var(--bg-surface); border: 1px solid var(--border-subtle);
      border-radius: var(--radius-xl); padding: var(--space-5);
    }
    .info-panel h3 { margin-bottom: var(--space-3); }
    .info-panel ol { padding-left: var(--space-5); margin-bottom: var(--space-3); }
    .info-panel li { color: var(--text-secondary); font-size: var(--text-sm); padding: var(--space-1) 0; }
    .info-panel p { color: var(--text-tertiary); font-size: var(--text-sm); }
  `],
})
export class DocumentsPage implements OnInit {
  protected readonly documentState = inject(DocumentStateService);
  private readonly toastSvc = inject(ToastService);

  confirmDelete = signal<string | null>(null);

  async ngOnInit(): Promise<void> {
    await this.documentState.loadDocuments();
  }

  onFileSelected(file: File): void {
    this.documentState.upload(file).then(() => {
      this.toastSvc.success(`Uploaded ${file.name}`);
    }).catch((err: any) => {
      this.toastSvc.error(err?.message ?? 'Upload failed');
    });
  }

  viewChunks(doc: string): void {
    this.toastSvc.info(`Viewing chunks for ${doc} — feature coming soon`);
  }

  reindex(doc: string): void {
    this.toastSvc.info(`Re-indexing ${doc} — feature coming soon`);
  }

  async deleteDocument(): Promise<void> {
    const name = this.confirmDelete();
    if (!name) return;
    await this.documentState.delete(name);
    this.confirmDelete.set(null);
    this.toastSvc.success(`Document ${name} deleted`);
  }
}
