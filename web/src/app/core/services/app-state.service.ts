import { Injectable, signal, computed } from '@angular/core';
import type { HealthResponse } from '../../shared/models/api.models';

@Injectable({ providedIn: 'root' })
export class AppStateService {
  readonly health = signal<HealthResponse | null>(null);
  readonly healthError = signal<string | null>(null);
  readonly isLive = computed(() => this.health()?.status === 'ok');

  readonly activeDataset = signal<string>('');
  readonly activeSessionId = signal<string | null>(null);
  readonly sidebarCollapsed = signal(false);
}
