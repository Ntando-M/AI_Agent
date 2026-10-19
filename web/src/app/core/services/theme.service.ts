import { Injectable, signal, effect } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class ThemeService {
  readonly theme = signal<'dark' | 'light'>(
    (localStorage.getItem('theme') as 'dark' | 'light') || 'dark',
  );

  constructor() {
    effect(() => {
      document.documentElement.setAttribute('data-theme', this.theme());
      localStorage.setItem('theme', this.theme());
    });
  }

  toggle(): void {
    this.theme.update(t => (t === 'dark' ? 'light' : 'dark'));
  }

  setTheme(t: 'dark' | 'light'): void {
    this.theme.set(t);
  }
}
