import { Routes } from '@angular/router';
import { healthGuard } from './core/guards/health.guard';

export const routes: Routes = [
  {
    path: '',
    loadComponent: () => import('./features/dashboard/dashboard.page').then(m => m.DashboardPage),
    canActivate: [healthGuard],
  },
  {
    path: 'chat',
    loadComponent: () => import('./features/chat/chat.page').then(m => m.ChatPage),
    canActivate: [healthGuard],
  },
  {
    path: 'analysis',
    loadComponent: () => import('./features/analysis/analysis.page').then(m => m.AnalysisPage),
    canActivate: [healthGuard],
  },
  {
    path: 'analysis/:sessionId',
    loadComponent: () => import('./features/analysis/analysis.page').then(m => m.AnalysisPage),
    canActivate: [healthGuard],
  },
  {
    path: 'reports',
    loadComponent: () => import('./features/reports/reports.page').then(m => m.ReportsPage),
    canActivate: [healthGuard],
  },
  {
    path: 'datasets',
    loadComponent: () => import('./features/datasets/datasets.page').then(m => m.DatasetsPage),
    canActivate: [healthGuard],
  },
  {
    path: 'documents',
    loadComponent: () => import('./features/documents/documents.page').then(m => m.DocumentsPage),
    canActivate: [healthGuard],
  },
  { path: '**', redirectTo: '' },
];
