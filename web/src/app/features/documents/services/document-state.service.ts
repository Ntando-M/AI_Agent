import { Injectable, signal, computed, inject } from '@angular/core';
import { ApiService } from '../../../core/services/api.service';

@Injectable({ providedIn: 'root' })
export class DocumentStateService {
  private readonly api = inject(ApiService);

  readonly documents = signal<string[]>([]);
  readonly uploading = signal(false);
  readonly uploadMessage = signal<string | null>(null);
  readonly deleting = signal<string | null>(null);

  readonly documentCount = computed(() => this.documents().length);

  async loadDocuments(): Promise<void> {
    this.documents.set(await this.api.listDocuments());
  }

  async upload(file: File): Promise<void> {
    this.uploading.set(true);
    this.uploadMessage.set(null);
    try {
      const result = await this.api.uploadDocument(file);
      this.uploadMessage.set(
        `Uploaded ${file.name}${result.chunks ? ` — ${result.chunks} chunks indexed` : ''}`,
      );
      await this.loadDocuments();
    } finally {
      this.uploading.set(false);
    }
  }

  async delete(name: string): Promise<void> {
    this.deleting.set(name);
    try {
      await this.api.deleteDocument(name);
      await this.loadDocuments();
    } finally {
      this.deleting.set(null);
    }
  }
}
