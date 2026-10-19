import { Injectable, signal } from '@angular/core';

export interface Toast {
  id: number;
  message: string;
  type: 'success' | 'error' | 'info' | 'warning';
}

let nextId = 0;

@Injectable({ providedIn: 'root' })
export class ToastService {
  readonly toasts = signal<Toast[]>([]);

  success(message: string): void {
    this.push(message, 'success', 5000);
  }

  error(message: string): void {
    this.push(message, 'error', 10000);
  }

  info(message: string): void {
    this.push(message, 'info', 5000);
  }

  warning(message: string): void {
    this.push(message, 'warning', 7000);
  }

  private push(message: string, type: Toast['type'], duration: number): void {
    const id = nextId++;
    this.toasts.update(t => [...t, { id, message, type }]);
    setTimeout(() => {
      this.toasts.update(t => t.filter(x => x.id !== id));
    }, duration);
  }

  dismiss(id: number): void {
    this.toasts.update(t => t.filter(x => x.id !== id));
  }
}
