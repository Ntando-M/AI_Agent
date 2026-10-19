import { Injectable, signal, computed, inject } from '@angular/core';
import { ApiService } from '../../../core/services/api.service';
import type { DatasetListResponse } from '../../../shared/models/api.models';

@Injectable({ providedIn: 'root' })
export class DatasetStateService {
  private readonly api = inject(ApiService);

  readonly datasets = signal<DatasetListResponse | null>(null);
  readonly uploading = signal(false);
  readonly uploadMessage = signal<string | null>(null);
  readonly deleting = signal<string | null>(null);

  readonly datasetList = computed(() => this.datasets()?.datasets ?? []);
  readonly hasDatasets = computed(() => this.datasetList().length > 0);

  async loadDatasets(): Promise<void> {
    this.datasets.set(await this.api.listDatasets());
  }

  async upload(file: File): Promise<void> {
    this.uploading.set(true);
    this.uploadMessage.set(null);
    try {
      const result = await this.api.uploadDataset(file);
      this.uploadMessage.set(
        `Uploaded ${file.name}${result.rows ? ` — ${result.rows} rows, ${result.columns?.length ?? 0} columns` : ''}`,
      );
      await this.loadDatasets();
    } finally {
      this.uploading.set(false);
    }
  }

  async delete(name: string): Promise<void> {
    this.deleting.set(name);
    try {
      await this.api.deleteDataset(name);
      await this.loadDatasets();
    } finally {
      this.deleting.set(null);
    }
  }
}
