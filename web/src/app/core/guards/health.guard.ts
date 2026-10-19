import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { ApiService } from '../services/api.service';
import { AppStateService } from '../services/app-state.service';

export const healthGuard: CanActivateFn = async () => {
  const api = inject(ApiService);
  const state = inject(AppStateService);
  const router = inject(Router);

  try {
    const health = await api.health();
    state.health.set(health);
    return true;
  } catch (err) {
    state.healthError.set(err instanceof Error ? err.message : String(err));
    return true; // allow navigation — pages show error state
  }
};
