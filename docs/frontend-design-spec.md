# AI Data Analyst — Frontend Design Specification

**Version:** 2.0 (Rebuild)  
**Target:** Angular 22.2+ (standalone components, signals)  
**Design System:** Custom, dark-mode-native with full light-mode support  
**Author:** Design Agent  
**Date:** 2026-10-14

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Component Hierarchy & Routing](#2-component-hierarchy--routing)
3. [State Management](#3-state-management)
4. [API Service Design](#4-api-service-design)
5. [Design Tokens — Color, Typography, Spacing](#5-design-tokens)
6. [Page Specifications](#6-page-specifications)
   - 6.1 [Dashboard / Home](#61-dashboard--home)
   - 6.2 [Chat](#62-chat)
   - 6.3 [Analysis](#63-analysis)
   - 6.4 [Reports](#64-reports)
   - 6.5 [Datasets](#65-datasets)
   - 6.6 [Documents](#66-documents)
7. [Interaction Patterns](#7-interaction-patterns)
8. [File Upload UX](#8-file-upload-ux)
9. [Chat Interface Design](#9-chat-interface-design)
10. [Analysis Result Display](#10-analysis-result-display)
11. [Report Viewer Design](#11-report-viewer-design)
12. [Accessibility](#12-accessibility)
13. [Responsive Layout](#13-responsive-layout)
14. [Migration from v1](#14-migration-from-v1)
15. [Implementation Checklist](#15-implementation-checklist)

---

## 1. Architecture Overview

### 1.1 Current State (v1)

The existing frontend is a single-component Angular app (`app.ts` + `app.html` + `app.css`, ~900 + ~660 + ~1720 lines). It uses Angular signals for state, has three views (Chat, Data/Manage, Reports) managed by a `view<'chat' | 'manage' | 'reports'>` signal, and communicates with a .NET gateway at `http://localhost:5000` via a relative `/api` base path.

**Problems identified:**
- "Boring" — dark Linear aesthetic is functional but lacks visual richness and personality
- Does not showcase all app capabilities (no dashboard, no dedicated analysis view, no rich dataset/document management)
- Reports page dataset switching is malfunctioning (`reportSource` signal not properly synced with `generateReport` calls)
- Single monolithic component — hard to maintain, test, or extend
- No Angular Material or component library — everything hand-rolled
- No routing — all navigation through signal-based view switching
- Charts not displayed inline (only filenames listed)
- No dark/light mode toggle
- No drag-and-drop upload
- No streaming/typing feel for chat responses
- Confidence, evidence, tools are shown as collapsed `<details>` — hidden by default

### 1.2 Target State (v2)

A multi-route, component-based Angular application with:

- **6 distinct pages** with proper Angular Router navigation
- **Angular Signals** for reactive state management ( NgRx not needed — signals are the Angular-native solution in v22)
- **Angular Material** component library for accessible, consistent UI primitives
- **Dark/light mode** toggle with CSS custom properties
- **Inline chart display** — charts render as `<img>` tags from base64 data URLs
- **Drag-and-drop** file upload with preview
- **Simulated streaming** — character-by-character reveal for chat answers to create a real-time feel
- **Proper report dataset switching** — the root cause of the v1 bug is fixed by routing report generation through a service method that always sends the selected dataset name

### 1.3 Technology Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Framework | Angular 22.2 (standalone) | Already in use; signals are first-class |
| UI Library | Angular Material 22 | Accessible, consistent, themeable |
| State | Angular Signals + Services | Native Angular reactivity; no external store needed |
| Routing | Angular Router | Multi-page navigation, lazy loading |
| HTTP | `@angular/common/http` | Already in use |
| Charts | `<img>` from base64 data URLs | API already returns base64 chart images in `chart_images` |
| Icons | `@angular/material/icon` (Material Symbols) | Consistent icon set |
| Build | `@angular/build` (esbuild) | Already configured |

### 1.4 API Gateway Architecture

```
Browser (Angular)  ──HTTP /api/*──▶  .NET Gateway (:5000)  ──▶  FastAPI (:8000)
                                          │
                                          └── holds X-API-Key header
                                              (never exposed to browser)
```

The browser **never** holds the API key. All requests go to the gateway via relative paths. This is non-negotiable — the existing spec tests enforce this.

---

## 2. Component Hierarchy & Routing

### 2.1 Route Map

| Path | Page | Purpose |
|------|------|---------|
| `/` | Dashboard | Overview, quick-start, system status |
| `/chat` | Chat | Conversational analysis interface |
| `/analysis/:sessionId?` | Analysis | Standalone analysis result display |
| `/reports` | Reports | Report list, generation, viewer |
| `/datasets` | Datasets | Dataset management (view, upload, select) |
| `/documents` | Documents | Document management (view, upload, re-index) |

All routes except `/` are guarded by a health check — if the gateway is not reachable, show a connection error page with retry instructions.

### 2.2 App Shell Layout

```
┌──────────────────────────────────────────────────────────────────┐
│  ╔════════════════════════════════════════════════════════════╗  │
│  ║  Header (64px)                                             ║  │
│  ║  [≡]  Brand  ·  Nav tabs  ·  Status pills  ·  [☀/🌙]     ║  │
│  ╚════════════════════════════════════════════════════════════╝  │
├──────────┬───────────────────────────────────────────────────────┤
│          │                                                       │
│  Side    │              Router Outlet                            │
│  nav     │              (page content)                           │
│  (240px) │                                                       │
│          │                                                       │
│  Chat    │                                                       │
│  Reports │                                                       │
│  Datasets│                                                       │
│  Docs    │                                                       │
│          │                                                       │
├──────────┴───────────────────────────────────────────────────────┤
│  ╔════════════════════════════════════════════════════════════╗  │
│  ║  Footer (optional, 32px) — powered by, version            ║  │
│  ╚════════════════════════════════════════════════════════════╝  │
└──────────────────────────────────────────────────────────────────┘
```

The sidebar is collapsible to 72px (icon-only) for more content space. On mobile (<768px), it becomes a drawer overlay.

### 2.3 Component Tree

```
AppComponent (shell)
├── HeaderComponent
│   ├── BrandMark
│   ├── NavigationTabs
│   ├── StatusPills
│   └── ThemeToggle
├── SidebarComponent
│   └── NavLink[] (routerLink)
├── RouterOutlet
│   ├── DashboardPage
│   │   ├── HealthOverviewCard
│   │   ├── QuickStartPrompts
│   │   ├── DatasetSummaryGrid
│   │   ├── DocumentListCard
│   │   └── RecentReportsCard
│   ├── ChatPage
│   │   ├── SessionSidebar (within chat page layout)
│   │   │   ├── SessionList
│   │   │   ├── NewSessionDialog
│   │   │   └── RenameDialog
│   │   ├── ChatTranscript
│   │   │   ├── TurnCard[]
│   │   │   │   ├── QuestionBlock
│   │   │   │   ├── AnswerBlock
│   │   │   │   ├── EvidencePanel
│   │   │   │   │   ├── ConfidenceMeter
│   │   │   │   │   ├── FindingsList
│   │   │   │   │   ├── CalculationsList
│   │   │   │   │   ├── SourcesList
│   │   │   │   │   └── ToolsList
│   │   │   │   └── ChartGallery
│   │   │   └── TypingIndicator
│   │   └── ChatComposer
│   │       └── SamplePromptChips
│   ├── AnalysisPage
│   │   ├── AnalysisHeader
│   │   ├── AnalysisResultCard
│   │   │   ├── AnswerText
│   │   │   ├── AnalysisTypeBadge
│   │   │   ├── ConfidenceRing
│   │   │   ├── EvidenceAccordion
│   │   │   │   ├── FindingsSection
│   │   │   │   ├── CalculationsSection
│   │   │   │   └── SourcesSection
│   │   │   └── EvidenceTable
│   │   └── AnalysisPlanViewer
│   ├── ReportsPage
│   │   ├── ReportGenerator
│   │   │   ├── DatasetSelector (FIXED — see §11)
│   │   │   ├── SessionSelector
│   │   │   └── GenerateButton
│   │   ├── ReportList
│   │   │   └── ReportCard[]
│   │   └── ReportViewer
│   │       ├── ReportHeader
│   │       ├── EvidenceLayerSection[]
│   │       │   ├── FactsSection
│   │       │   ├── CalculatedFindingsSection
│   │       │   ├── InterpretationsSection
│   │       │   └── RecommendationsSection
│   │       ├── ChartGallery (inline images)
│   │       └── FullTextReport (collapsible)
│   ├── DatasetsPage
│   │   ├── DatasetGrid
│   │   │   └── DatasetCard[]
│   │   ├── UploadDropZone
│   │   └── ColumnPreviewTable
│   └── DocumentsPage
│       ├── DocumentList
│       │   └── DocumentCard[]
│       ├── UploadDropZone
│       └── IndexingStatusBadge
└── SharedComponents
    ├── Base64ImageComponent
    ├── EmptyStateComponent
    ├── LoadingSpinnerComponent
    ├── ErrorBannerComponent
    ├── ConfirmDialogComponent
    └── ToastNotificationComponent
```

### 2.4 Component Responsibilities

| Component | Responsibility |
|-----------|---------------|
| `AppComponent` | Shell layout, theme management, health polling |
| `HeaderComponent` | Brand, navigation, status indicators, theme toggle |
| `SidebarComponent` | Navigation links, collapsible |
| `DashboardPage` | Aggregate overview of system state |
| `ChatPage` | Conversational interface, session management |
| `ChatTranscript` | Display turns, auto-scroll |
| `TurnCard` | Single Q&A pair with evidence |
| `ChatComposer` | Input area, sample prompts |
| `AnalysisPage` | Rich analysis result display |
| `ReportsPage` | Report CRUD, generation, viewing |
| `DatasetsPage` | Dataset CRUD, upload, column preview |
| `DocumentsPage` | Document CRUD, upload, indexing status |
| `ApiService` | All HTTP calls, error normalization |
| `StateService` | Cross-component state (active session, theme, etc.) |

---

## 3. State Management

### 3.1 Philosophy

Angular 22 signals are the native reactive primitive. We use **service-based state** with signals — no NgRx, no external store. Each domain area has a dedicated state service with signal-based state and computed derived values.

### 3.2 State Services

```typescript
// core/services/app-state.service.ts — global app state
@Injectable({ providedIn: 'root' })
export class AppStateService {
  // Theme
  readonly theme = signal<'dark' | 'light'>('dark');
  readonly isDark = computed(() => this.theme() === 'dark');
  
  // Health
  readonly health = signal<HealthResponse | null>(null);
  readonly healthError = signal<string | null>(null);
  readonly isLive = computed(() => this.health()?.status === 'ok');
  
  // Active dataset (global selector)
  readonly activeDataset = signal<string>('');
  
  // Active session (shared between Chat and Analysis)
  readonly activeSessionId = signal<string | null>(null);
  
  // Sidebar
  readonly sidebarCollapsed = signal(false);
  
  // Toast notifications
  readonly toasts = signal<Toast[]>([]);
}
```

```typescript
// features/chat/services/chat-state.service.ts
@Injectable({ providedIn: 'root' })
export class ChatStateService {
  readonly sessions = signal<SessionPayload[]>([]);
  readonly activeSession = signal<string | null>(null);
  readonly turns = signal<Turn[]>([]);
  readonly asking = signal(false);
  readonly question = signal('');
  
  // Computed
  readonly activeSessionName = computed(() => 
    this.sessions().find(s => s.session_id === this.activeSession())?.name ?? null
  );
  readonly turnCount = computed(() => this.turns().length);
  readonly busy = computed(() => this.asking());
}
```

```typescript
// features/reports/services/report-state.service.ts
@Injectable({ providedIn: 'root' })
export class ReportStateService {
  readonly reports = signal<ReportSummary[]>([]);
  readonly activeReport = signal<ReportDetail | null>(null);
  readonly generatingReport = signal(false);
  readonly reportError = signal<string | null>(null);
  
  // FIXED: report source is always a string, never null/undefined
  // The v1 bug was that reportSource could be '' which was then
  // passed to the API inconsistently. Now we use a discriminated approach.
  readonly reportDataset = signal<string>(''); // '' = "use currently loaded"
  readonly reportSessionId = signal<string | null>(null);
  
  readonly isDetailOpen = computed(() => this.activeReport() !== null);
}
```

```typescript
// features/datasets/services/dataset-state.service.ts
@Injectable({ providedIn: 'root' })
export class DatasetStateService {
  readonly datasets = signal<DatasetListResponse | null>(null);
  readonly uploading = signal(false);
  readonly uploadMessage = signal<string | null>(null);
  readonly deleting = signal<string | null>(null);
  
  readonly datasetList = computed(() => this.datasets()?.datasets ?? []);
  readonly hasDatasets = computed(() => this.datasetList().length > 0);
}
```

```typescript
// features/documents/services/document-state.service.ts
@Injectable({ providedIn: 'root' })
export class DocumentStateService {
  readonly documents = signal<string[]>([]);
  readonly uploading = signal(false);
  readonly uploadMessage = signal<string | null>(null);
  readonly deleting = signal<string | null>(null);
  
  readonly documentCount = computed(() => this.documents().length);
}
```

### 3.3 State Flow Patterns

**Reading state:** Components inject state services and read signals directly in templates.

```typescript
// In template
@if (chatState.turns(); as turns) {
  @for (turn of turns; track $index) {
    <app-turn-card [turn]="turn" />
  }
}
```

**Writing state:** Components call service methods that update signals.

```typescript
// In component
async ask(): Promise<void> {
  const text = this.chatState.question().trim();
  if (!text || this.chatState.busy()) return;
  
  this.chatState.ask(text); // method on service that updates all relevant signals
}
```

**Cross-component communication:** Shared services. For example, when the user starts a chat from the Dashboard's quick-start, the Dashboard sets `AppStateService.activeSessionId()` and navigates to `/chat`, where `ChatStateService` picks it up.

### 3.4 Why Not NgRx

- Angular signals are the framework's native reactivity model in v22
- The app's state is domain-partitioned, not a single global tree
- Services + signals give fine-grained reactivity without boilerplate
- Computed signals replace selectors
- `effect()` handles side effects

---

## 4. API Service Design

### 4.1 ApiService (Refactored)

The existing `ApiService` is well-structured. The v2 version refactors it with:

1. **Stronger typing** — response interfaces match the Pydantic models exactly
2. **Chart URL helper** — converts base64 data URLs for `<img src>`
3. **Streaming simulation** — SSE-style chunked reading where supported, fallback to full response
4. **Error normalization** — preserves the existing `GatewayError` pattern

```typescript
@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);
  private readonly base = '/api';
  
  // ── Health ──
  health(): Promise<HealthResponse>
  
  // ── Sessions ──
  listSessions(): Promise<SessionPayload[]>
  createSession(sessionId: string, name?: string): Promise<SessionPayload>
  renameSession(sessionId: string, name: string): Promise<SessionPayload>
  getSession(sessionId: string): Promise<SessionDetail>
  deleteSession(sessionId: string): Promise<void>
  
  // ── Chat ──
  chat(sessionId: string, message: string): Promise<ChatResponse>
  
  // ── Analyse (stateless or session-bound) ──
  analyse(question: string, sessionId?: string | null): Promise<AnalyseResponse>
  
  // ── Datasets ──
  listDatasets(): Promise<DatasetListResponse>
  uploadDataset(file: File): Promise<UploadResult>
  deleteDataset(name: string): Promise<void>
  
  // ── Documents ──
  listDocuments(): Promise<string[]>
  uploadDocument(file: File): Promise<UploadResult>
  deleteDocument(name: string): Promise<void>
  
  // ── Reports ──
  listReports(): Promise<ReportSummary[]>
  getReport(reportId: string): Promise<ReportDetail>
  generateReport(sessionId: string | null, dataset: string | null): Promise<ReportDetail>
  deleteReport(reportId: string): Promise<void>
  
  // ── Helpers ──
  getChartUrl(base64Data: string): string  // returns "data:image/png;base64,..." 
}
```

### 4.2 Response Interfaces (Complete)

```typescript
/** Mirrors api/schemas.py AnalysisPayload. */
export interface AnalysisPayload {
  answer: string;
  analysis_type: AnalysisType;
  datasets_used: string[];
  calculations_performed: string[];
  key_findings: string[];
  sources: string[];
  confidence: number;
}

export type AnalysisType = 'general' | 'document' | 'dataset' | 'database' | 'visualisation';

export interface ChatResponse {
  session_id: string;
  response: AnalysisPayload;
  visualisations: string[];
  tools_used: string[];
  source_labels: string[];
  warnings: string[];
}

export interface AnalyseResponse {
  response: AnalysisPayload;
  visualisations: string[];
  tools_used: string[];
  plan: Record<string, any>;
  warnings: string[];
}

export interface SessionPayload {
  session_id: string;
  message_count: number;
  created_at: string | null;
  last_activity_at: string | null;
  preview: string | null;
  name: string;
}

export interface TurnPayload {
  role: 'user' | 'assistant';
  content: string;
  created_at: string | null;
  evidence?: TurnEvidence | null;
}

export interface TurnEvidence {
  analysis_type?: string;
  confidence?: number;
  sources?: string[];
  datasets_used?: string[];
  calculations_performed?: string[];
  key_findings?: string[];
  visualisations?: string[];
  tools_used?: string[];
  source_labels?: string[];
}

export interface SessionDetail {
  session_id: string;
  turns: TurnPayload[];
}

export interface DatasetListResponse {
  datasets: DatasetPayload[];
}

export interface DatasetPayload {
  name: string;
  path: string;
  rows: number | null;
  columns: string[];
  registered: boolean;
}

export interface UploadResult {
  name?: string;
  path?: string;
  rows?: number | null;
  columns?: string[];
  filename?: string;
  stored_path?: string;
  size_bytes?: number;
  indexed?: boolean;
  chunks?: number;
  message?: string;
}

export interface HealthResponse {
  status: string;
  provider: string;
  dataset_loaded: boolean;
  database_loaded: boolean;
  documents_indexed: boolean;
  version: string;
}

export interface ReportSummary {
  report_id: string;
  session_id: string | null;
  dataset_name: string | null;
  created_at: string | null;
  preview: string;
}

export interface ReportLayers {
  facts?: string[];
  calculated_findings?: string[];
  interpretations?: string[];
  recommendations?: string[];
}

export interface ReportDetail {
  report_id: string;
  session_id: string | null;
  content: string;
  created_at: string | null;
  dataset_name: string | null;
  summary: Record<string, unknown>;
  layers: ReportLayers;
  charts: Record<string, string>;       // name -> filesystem path
  chart_images: Record<string, string>; // name -> "data:image/png;base64,..."
}
```

### 4.3 Endpoint Coverage Matrix

| Endpoint | Method | Service Method | Page(s) Using It |
|----------|--------|----------------|-------------------|
| `/api/health` | GET | `health()` | Dashboard, Header |
| `/api/sessions` | GET | `listSessions()` | Chat |
| `/api/sessions` | POST | `createSession()`, `renameSession()` | Chat |
| `/api/sessions/:id` | GET | `getSession()` | Chat, Analysis |
| `/api/sessions/:id` | DELETE | `deleteSession()` | Chat |
| `/api/chat` | POST | `chat()` | Chat |
| `/api/analyse` | POST | `analyse()` | Analysis |
| `/api/datasets` | GET | `listDatasets()` | Datasets, Dashboard |
| `/api/datasets` | POST | `uploadDataset()` | Datasets |
| `/api/datasets/:name` | DELETE | `deleteDataset()` | Datasets |
| `/api/documents` | GET | `listDocuments()` | Documents, Dashboard |
| `/api/documents` | POST | `uploadDocument()` | Documents |
| `/api/documents/:name` | DELETE | `deleteDocument()` | Documents |
| `/api/reports` | GET | `listReports()` | Reports, Dashboard |
| `/api/reports/:id` | GET | `getReport()` | Reports |
| `/api/reports` | POST | `generateReport()` | Reports |
| `/api/reports/:id` | DELETE | `deleteReport()` | Reports |

---

## 5. Design Tokens

### 5.1 Color System

The v1 palette is good but sparse. v2 expands it with semantic color roles, status colors, and chart-friendly accent colors.

#### Dark Mode (Default)

```css
:root {
  /* ── Backgrounds (luminance stack) ── */
  --bg-canvas:        #0a0b0d;   /* deepest background */
  --bg-surface:        #111318;   /* cards, panels */
  --bg-elevated:      #1a1d24;   /* dropdowns, modals */
  --bg-overlay:       rgba(0, 0, 0, 0.6); /* modal backdrop */
  --bg-hover:         rgba(255, 255, 255, 0.04);
  --bg-active:         rgba(255, 255, 255, 0.08);

  /* ── Text ── */
  --text-primary:     #f0f2f5;
  --text-secondary:   #b8bfcc;
  --text-tertiary:    #7d8590;
  --text-quaternary:  #4d5560;
  --text-inverse:     #0a0b0d;   /* text on colored bg */

  /* ── Brand (indigo/violet family) ── */
  --brand-50:  #eef0ff;
  --brand-100: #d9deff;
  --brand-200: #b3bcff;
  --brand-300: #8d9aff;
  --brand-400: #6778ff;
  --brand-500: #5e6ad2;   /* primary brand */
  --brand-600: #4b58b8;
  --brand-700: #3a4594;

  /* ── Accent colors for charts & categories ── */
  --accent-emerald: #10b981;
  --accent-amber:   #f59e0b;
  --accent-rose:    #f43f5e;
  --accent-sky:     #0ea5e9;
  --accent-violet:  #8b5cf6;
  --accent-teal:    #14b8a6;

  /* ── Status ── */
  --status-success:     #10b981;
  --status-success-bg:  rgba(16, 185, 129, 0.12);
  --status-warning:     #f59e0b;
  --status-warning-bg:  rgba(245, 158, 11, 0.12);
  --status-error:       #ef4444;
  --status-error-bg:    rgba(239, 68, 68, 0.12);
  --status-info:        #0ea5e9;
  --status-info-bg:     rgba(14, 165, 233, 0.12);

  /* ── Borders ── */
  --border-subtle:    rgba(255, 255, 255, 0.05);
  --border-standard:  rgba(255, 255, 255, 0.09);
  --border-strong:    rgba(255, 255, 255, 0.14);
  --border-focus:     var(--brand-400);

  /* ── Shadows ── */
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.3);
  --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.4);
  --shadow-lg: 0 8px 24px rgba(0, 0, 0, 0.5);
  --shadow-glow: 0 0 20px rgba(94, 106, 210, 0.15);

  /* ── Chart palette ── */
  --chart-1: #5e6ad2;
  --chart-2: #10b981;
  --chart-3: #f59e0b;
  --chart-4: #f43f5e;
  --chart-5: #0ea5e9;
  --chart-6: #8b5cf6;
}
```

#### Light Mode

```css
[data-theme="light"] {
  --bg-canvas:        #f8f9fb;
  --bg-surface:        #ffffff;
  --bg-elevated:      #ffffff;
  --bg-overlay:       rgba(0, 0, 0, 0.3);
  --bg-hover:         rgba(0, 0, 0, 0.04);
  --bg-active:         rgba(0, 0, 0, 0.06);

  --text-primary:     #1a1d24;
  --text-secondary:   #4d5560;
  --text-tertiary:    #7d8590;
  --text-quaternary:  #a0a8b3;
  --text-inverse:     #ffffff;

  --border-subtle:    rgba(0, 0, 0, 0.06);
  --border-standard:  rgba(0, 0, 0, 0.10);
  --border-strong:    rgba(0, 0, 0, 0.16);

  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.06);
  --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.10);
  --shadow-lg: 0 8px 24px rgba(0, 0, 0, 0.14);
  --shadow-glow: 0 0 20px rgba(94, 106, 210, 0.08);
}
```

### 5.2 Typography

```css
:root {
  /* Font families */
  --font-sans: 'Inter', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
  --font-mono: 'JetBrains Mono', 'Fira Code', ui-monospace, monospace;

  /* Font sizes (1.25 modular scale) */
  --text-xs:   0.6875rem;  /* 11px */
  --text-sm:   0.75rem;    /* 12px */
  --text-base: 0.875rem;   /* 14px */
  --text-md:   1rem;       /* 16px */
  --text-lg:   1.125rem;   /* 18px */
  --text-xl:   1.25rem;    /* 20px */
  --text-2xl:  1.5rem;     /* 24px */
  --text-3xl:  2rem;       /* 32px */
  --text-4xl:  2.5rem;     /* 40px */

  /* Font weights */
  --weight-normal: 400;
  --weight-medium: 500;
  --weight-semibold: 600;
  --weight-bold: 700;

  /* Line heights */
  --leading-tight: 1.25;
  --leading-normal: 1.5;
  --leading-relaxed: 1.75;

  /* Letter spacing */
  --tracking-tight: -0.02em;
  --tracking-normal: 0;
  --tracking-wide: 0.02em;
}
```

### 5.3 Spacing System

```css
:root {
  /* 4px base grid */
  --space-1:  4px;
  --space-2:  8px;
  --space-3:  12px;
  --space-4:  16px;
  --space-5:  20px;
  --space-6:  24px;
  --space-8:  32px;
  --space-10: 40px;
  --space-12: 48px;
  --space-16: 64px;
  --space-20: 80px;

  /* Semantic spacing */
  --page-padding: var(--space-6);
  --card-padding: var(--space-5);
  --section-gap: var(--space-8);
  --component-gap: var(--space-4);
}
```

### 5.4 Border Radius

```css
:root {
  --radius-xs:  4px;
  --radius-sm:  6px;
  --radius-md:  8px;
  --radius-lg:  12px;
  --radius-xl:  16px;
  --radius-2xl: 24px;
  --radius-full: 9999px;
}
```

### 5.5 Elevation & Shadows

```css
:root {
  --shadow-card: var(--shadow-sm);
  --shadow-elevated: var(--shadow-md);
  --shadow-modal: var(--shadow-lg);
  --shadow-glow-brand: var(--shadow-glow);
  --shadow-inset: inset 0 1px 0 0 rgba(255, 255, 255, 0.06);
}
```

### 5.6 Animation

```css
:root {
  --duration-instant: 100ms;
  --duration-fast: 150ms;
  --duration-normal: 250ms;
  --duration-slow: 400ms;
  
  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
  --ease-in-out: cubic-bezier(0.65, 0, 0.35, 1);
  --ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1);
}

/* Micro-animations */
@keyframes fade-in {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes slide-in-right {
  from { opacity: 0; transform: translateX(16px); }
  to { opacity: 1; transform: translateX(0); }
}

@keyframes pulse-glow {
  0%, 100% { box-shadow: 0 0 0 0 rgba(94, 106, 210, 0.4); }
  50% { box-shadow: 0 0 0 8px rgba(94, 106, 210, 0); }
}

@keyframes typing-dot {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
  30% { transform: translateY(-4px); opacity: 1; }
}

@keyframes shimmer {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}

@keyframes confidence-fill {
  from { stroke-dashoffset: var(--confidence-circumference); }
}
```

---

## 6. Page Specifications

### 6.1 Dashboard / Home

**Route:** `/`  
**Purpose:** First impression. Show system status, available data sources, and quick-start actions.

**Layout:**

```
┌─────────────────────────────────────────────────────────────┐
│  ┌───────────────────────────────────────────────────────┐  │
│  │  HERO SECTION                                        │  │
│  │                                                       │  │
│  │  Welcome to AI Data Analyst                          │  │
│  │  Ask questions. Get answers backed by real data.     │  │
│  │                                                       │  │
│  │  ┌─────────────────────────────────────────────────┐ │  │
│  │  │ Quick-start prompt chips:                       │ │  │
│  │  │ [Total revenue?] [Top region?] [By product?]   │ │  │
│  │  │ [Monthly trend?] [Strategy doc?]                │ │  │
│  │  └─────────────────────────────────────────────────┘ │  │
│  │  [→ Start chatting]  [Generate report]               │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐        │
│  │ SYSTEM STATUS│ │  DATASETS    │ │  DOCUMENTS   │        │
│  │              │ │              │ │              │        │
│  │ ● LIVE       │ │ 2 loaded     │ │ 5 indexed    │        │
│  │ Provider:    │ │ ┌──────────┐ │ │ ┌──────────┐ │        │
│  │ groq         │ │ │sample.csv│ │ │ │roadmap  │ │        │
│  │ v22.2        │ │ │120 rows  │ │ │ │.pdf      │ │        │
│  │              │ │ ├──────────┤ │ │ ├──────────┤ │        │
│  │ ● Dataset ✓  │ │ │sales.    │ │ │ │strategy  │ │        │
│  │ ● Database ✓ │ │ │xlsx      │ │ │ │.docx     │ │        │
│  │ ● Docs ✓     │ │ │240 rows  │ │ │ ├──────────┤ │        │
│  │              │ │ └──────────┘ │ │ │notes.txt  │ │        │
│  │              │ │ [→ Manage]  │ │ │ └──────────┘ │        │
│  │              │ │              │ │ [→ Manage]   │        │
│  └──────────────┘ └──────────────┘ └──────────────┘        │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  RECENT REPORTS                                       │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐              │  │
│  │  │ Report 1 │ │ Report 2 │ │ Report 3 │  [→ View all]│  │
│  │  │ sample   │ │ sample   │ │ sales.db │              │  │
│  │  │ sales    │ │ sales    │ │ regions  │              │  │
│  │  │ 2h ago   │ │ 1d ago   │ │ 3d ago   │              │  │
│  │  └──────────┘ └──────────┘ └──────────┘              │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

**Components:**

| Component | Description |
|-----------|-------------|
| `HeroSection` | Welcome message, primary CTAs, quick-start prompt chips |
| `HealthOverviewCard` | Live status, provider, version, loaded sources (dataset/database/docs) |
| `DatasetSummaryGrid` | Card per dataset: name, rows, columns count, column preview |
| `DocumentListCard` | Document filenames, count badge, indexed status |
| `RecentReportsCard` | Last 5 reports with preview text, dataset name, timestamp |
| `QuickStartChips` | Clickable prompt suggestions that navigate to chat with pre-filled question |

**Interactions:**
- Quick-start chips: clicking one navigates to `/chat` with the question pre-filled in the composer
- "Start chatting" button: navigates to `/chat`
- "Generate report" button: navigates to `/reports`
- Dataset/Document cards: clicking navigates to respective management pages
- Reports: clicking opens the report in the Reports page
- Health card: polls every 30s for live status

**State:**
- Uses `AppStateService.health`, `DatasetStateService`, `DocumentStateService`, `ReportStateService`
- All data loaded on `ngOnInit` via a parallel `Promise.all`

---

### 6.2 Chat

**Route:** `/chat`  
**Purpose:** The primary conversational interface. Users ask questions, see answers with full evidence, manage sessions.

**Layout:**

```
┌─────────────────────────────────────────────────────────────────┐
│  Chat Header                                                    │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ [Session Name]  [Rename]  [⋮ Delete]  [← New]            │  │
│  └──────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                                                         │   │
│  │  ┌──────────────────────────────────────────────────┐  │   │
│  │  │  You                                              │  │   │
│  │  │  What was the total revenue last quarter?        │  │   │
│  │  └──────────────────────────────────────────────────┘  │   │
│  │                                                         │   │
│  │  ┌──────────────────────────────────────────────────┐  │   │
│  │  │  🤖 AI Analyst                                   │  │   │
│  │  │                                                  │  │   │
│  │  │  The total revenue for Q3 2026 was R2,847,300.  │  │   │
│  │  │  This was calculated by summing all Revenue     │  │   │
│  │  │  values where the Date fell between 2026-07-01  │  │   │
│  │  │  and 2026-09-30.                               │  │   │
│  │  │                                                  │  │   │
│  │  │  ┌────────────────────────────────────────────┐ │  │   │
│  │  │  │ 📊 ANALYSIS METADATA                      │ │  │   │
│  │  │  │                                            │ │  │   │
│  │  │  │  Confidence: ████████░░ 82%              │ │  │   │
│  │  │  │  Type: dataset analysis                   │ │  │   │
│  │  │  │                                            │ │  │   │
│  │  │  │  ┌─ Key Findings ──────────────────────┐  │ │  │   │
│  │  │  │  │ • Q3 revenue: R2,847,300            │  │ │  │   │
│  │  │  │  │ • Top product: Laptop (R1.2M, 42%) │  │ │  │   │
│  │  │  │  │ • Growth vs Q2: +12.3%              │  │ │  │   │
│  │  │  │  └──────────────────────────────────────┘  │ │  │   │
│  │  │  │                                            │ │  │   │
│  │  │  │  ┌─ Calculations ──────────────────────┐  │ │  │   │
│  │  │  │  │ aggregate_dataset(Revenue, sum)      │  │ │  │   │
│  │  │  │  │ filter_dataset(Date, Q3 range)        │  │ │  │   │
│  │  │  │  │ group_by(Product, Revenue, sum)       │  │ │  │   │
│  │  │  │  └──────────────────────────────────────┘  │ │  │   │
│  │  │  │                                            │ │  │   │
│  │  │  │  ┌─ Sources ────────────────────────────┐  │ │  │   │
│  │  │  │  │ sample_sales.xlsx                     │  │ │  │   │
│  │  │  │  └──────────────────────────────────────┘  │ │  │   │
│  │  │  │                                            │ │  │   │
│  │  │  │  ┌─ Tools Used ─────────────────────────┐  │ │  │   │
│  │  │  │  │ 🔧 aggregate_dataset                  │  │ │  │   │
│  │  │  │  │ 🔧 filter_dataset                     │  │ │  │   │
│  │  │  │  │ 🔧 group_by_column                    │  │ │  │   │
│  │  │  │  │ 🔧 calculate_statistics               │  │ │  │   │
│  │  │  │  └──────────────────────────────────────┘  │ │  │   │
│  │  │  └────────────────────────────────────────────┘ │  │   │
│  │  │                                                  │  │   │
│  │  │  ┌──────────────────────────────────────────┐   │  │   │
│  │  │  │ 📈 Charts Generated                      │   │  │   │
│  │  │  │                                          │   │  │   │
│  │  │  │  ┌──────────┐  ┌──────────┐             │   │  │   │
│  │  │  │  │ [Chart   │  │ [Chart   │             │   │  │   │
│  │  │  │  │  image]  │  │  image]  │             │   │  │   │
│  │  │  │  │ Revenue  │  │ Revenue  │             │   │  │   │
│  │  │  │  │ by Prod  │  │ by Reg   │             │   │  │   │
│  │  │  │  └──────────┘  └──────────┘             │   │  │   │
│  │  │  └──────────────────────────────────────────┘   │  │   │
│  │  └──────────────────────────────────────────────────┘  │   │
│  │                                                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ COMPOSER                                                │   │
│  │ ┌─────────────────────────────────────┐ ┌─────────────┐ │   │
│  │ │ Ask a question about your data...    │ │ [Send →]    │ │   │
│  │ └─────────────────────────────────────┘ └─────────────┘ │   │
│  │                                                         │   │
│  │  Quick prompts:                                         │   │
│  │  [Total revenue?] [Top region?] [By product?]         │   │
│  │  [Monthly trend] [Missing data] [Distribution]         │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

**Session Sidebar (integrated into chat page, collapsible):**

```
┌─────────────────────────────┐
│  Conversations      [+ New] │
│  ┌───────────────────────┐  │
│  │ ● Sales Analysis      │  │
│  │   12 messages         │  │
│  │   2 min ago     ✎ ×   │  │
│  ├───────────────────────┤  │
│  │ ○ Revenue Deep-Dive   │  │
│  │   8 messages          │  │
│  │   1 hour ago    ✎ ×   │  │
│  ├───────────────────────┤  │
│  │ ○ Product Review      │  │
│  │   24 messages         │  │
│  │   3 hours ago   ✎ ×   │  │
│  └───────────────────────┘  │
│                             │
│  ┌───────────────────────┐  │
│  │  Active Dataset:      │  │
│  │  [sample_sales.xlsx ▾]│  │
│  │  240 rows · 8 cols    │  │
│  └───────────────────────┘  │
└─────────────────────────────┘
```

**Components:**

| Component | Description |
|-----------|-------------|
| `ChatHeader` | Session name, rename/delete/new buttons |
| `SessionSidebar` | Session list, new session dialog, active dataset selector |
| `ChatTranscript` | Scrollable transcript, auto-scrolls to bottom |
| `TurnCard` | Single Q&A pair — question, answer, metadata, evidence |
| `ConfidenceMeter` | Visual bar or ring showing confidence percentage |
| `EvidencePanel` | Findings, calculations, sources, tools — each as a sub-section |
| `ChartGallery` | Inline chart images from `chart_images` (base64) |
| `TypingIndicator` | Animated dots while waiting for response |
| `ChatComposer` | Text input, send button, sample prompt chips |
| `QuickPromptChips` | Clickable suggested questions |

**Key Interactions:**

1. **Ask a question:** Type in composer → press Enter or click Send → question appears immediately in transcript → typing indicator shows → response streams in character-by-character → evidence panels expand below answer.

2. **Create session:** Click "New" → dialog opens with name input → confirm → new session appears in sidebar, becomes active, transcript clears.

3. **Switch session:** Click a session in sidebar → loads that session's turn history from API → transcript updates → composer focuses.

4. **Rename session:** Click ✎ → dialog with pre-filled name → confirm → name updates in sidebar and header.

5. **Delete session:** Click × → browser confirm → session removed → if active, switches to first remaining session.

6. **Sample prompt:** Click a chip → fills composer with that question → user can edit before sending.

7. **View chart:** Charts render as `<img [src]="chartUrl">` from base64 data URLs. Clicking a chart opens it in a lightbox modal at full size.

8. **Export answer:** (Future enhancement — right-click or button to copy answer as markdown)

**State Management:**

```typescript
// ChatStateService methods
class ChatStateService {
  // Loading
  async loadSessions(): Promise<void>
  async loadSession(sessionId: string): Promise<void>
  async createSession(name: string): Promise<string>
  async renameSession(sessionId: string, name: string): Promise<void>
  async deleteSession(sessionId: string): Promise<void>
  
  // Chatting
  async ask(sessionId: string, question: string): Promise<void>
  // Internally: adds pending turn, calls api.chat(), updates turn with response,
  // streams the answer character-by-character for typing feel
  
  // Helpers
  setQuestion(text: string): void
  clearQuestion(): void
}
```

**Streaming Simulation:**

The API returns the full response at once. To create a "real-time typing feel," the frontend reveals the answer text progressively:

```typescript
// In ChatStateService
private async streamAnswer(turn: Turn, fullAnswer: string): Promise<void> {
  const chars = fullAnswer.split('');
  const chunkSize = 3; // characters per tick
  const tickMs = 20;   // ms between ticks
  
  for (let i = 0; i < chars.length; i += chunkSize) {
    const partial = chars.slice(0, i + chunkSize).join('');
    this.updateTurnAnswer(turn, partial);
    await delay(tickMs);
  }
}
```

This is purely presentational — the answer is already computed by the backend. The streaming just makes it feel responsive and alive.

---

### 6.3 Analysis

**Route:** `/analysis` or `/analysis/:sessionId`  
**Purpose:** Standalone page for rich analysis result display. Can be navigated to from a chat turn (to view it in full screen) or used for stateless analysis.

**Layout:**

```
┌─────────────────────────────────────────────────────────────────┐
│  Analysis Header                                                │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  [← Back to chat]  Standalone Analysis                  │  │
│  │                                                          │  │
│  │  Ask a question for stateless analysis:                  │  │
│  │  ┌────────────────────────────────┐ ┌──────────────────┐ │  │
│  │  │ Type your question...          │ │ [Analyse →]      │ │  │
│  │  └────────────────────────────────┘ └──────────────────┘ │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  OR — if navigated from a chat turn:                           │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Question: What was the total revenue last quarter?     │   │
│  │                                                         │   │
│  │  Answer                                                 │   │
│  │  ═══════════════════════════════════════════════════    │   │
│  │                                                         │   │
│  │  The total revenue for Q3 2026 was R2,847,300...      │   │
│  │                                                         │   │
│  │  ┌──────────────────────────────────────────────────┐  │   │
│  │  │  ANALYSIS METADATA                               │  │   │
│  │  │                                                  │  │   │
│  │  │  ┌──────────────┐  ┌──────────────────────────┐  │  │   │
│  │  │  │ Confidence   │  │ Analysis Type            │  │  │   │
│  │  │  │              │  │                          │  │  │   │
│  │  │  │    ╭─────╮   │  │  ┌────────────────────┐  │  │  │   │
│  │  │  │   ╱ 82%  ╲  │  │  │ 📊 dataset          │  │  │  │   │
│  │  │  │  │       │  │  │  │    analysis         │  │  │  │   │
│  │  │  │   ╲      ╱  │  │  └────────────────────┘  │  │  │   │
│  │  │  │    ╰─────╯   │  │                          │  │  │   │
│  │  │  └──────────────┘  └──────────────────────────┘  │  │   │
│  │  └──────────────────────────────────────────────────┘  │   │
│  │                                                         │   │
│  │  ┌─ Key Findings ──────────────────────────────────┐   │   │
│  │  │ ● Q3 total revenue: R2,847,300                   │   │   │
│  │  │ ● Top product: Laptop (R1.2M, 42.1% of total)   │   │   │
│  │  │ ● Growth vs Q2: +12.3%                           │   │   │
│  │  │ ● Average order value: R4,560                    │   │   │
│  │  └───────────────────────────────────────────────────┘   │   │
│  │                                                         │   │
│  │  ┌─ Calculations Performed ────────────────────────┐   │   │
│  │  │ aggregate_dataset(Revenue, sum) → R2,847,300    │   │   │
│  │  │ filter_dataset(Date, 2026-07-01..2026-09-30)     │   │   │
│  │  │ group_by_column(Product, Revenue, sum)           │   │   │
│  │  │ calculate_statistics(Revenue) → mean, median...  │   │   │
│  │  └───────────────────────────────────────────────────┘   │   │
│  │                                                         │   │
│  │  ┌─ Data Sources ──────────────────────────────────┐   │   │
│  │  │ 📄 sample_sales.xlsx                             │   │   │
│  │  │    240 rows × 8 columns                          │   │   │
│  │  │    Columns: Date, Product, Region, Revenue...    │   │   │
│  │  └───────────────────────────────────────────────────┘   │   │
│  │                                                         │   │
│  │  ┌─ Tools Executed ─────────────────────────────────┐   │   │
│  │  │ 🔧 aggregate_dataset      ✓ completed in 0.02s   │   │   │
│  │  │ 🔧 filter_dataset         ✓ completed in 0.01s   │   │   │
│  │  │ 🔧 group_by_column        ✓ completed in 0.03s   │   │   │
│  │  │ 🔧 calculate_statistics   ✓ completed in 0.02s   │   │   │
│  │  └───────────────────────────────────────────────────┘   │   │
│  │                                                         │   │
│  │  ┌─ Visualisations ────────────────────────────────┐   │   │
│  │  │                                                 │   │   │
│  │  │  ┌──────────────┐  ┌──────────────┐            │   │   │
│  │  │  │              │  │              │            │   │   │
│  │  │  │ [Chart IMG]  │  │ [Chart IMG]  │            │   │   │
│  │  │  │ Revenue by   │  │ Revenue by   │            │   │   │
│  │  │  │ Product      │  │ Region       │            │   │   │
│  │  │  │              │  │              │            │   │   │
│  │  │  │ [🔍 Zoom]    │  │ [🔍 Zoom]    │            │   │   │
│  │  │  └──────────────┘  └──────────────┘            │   │   │
│  │  │                                                 │   │   │
│  │  │  ┌──────────────┐  ┌──────────────┐            │   │   │
│  │  │  │              │  │              │            │   │   │
│  │  │  │ [Chart IMG]  │  │ [Chart IMG]  │            │   │   │
│  │  │  │ Monthly      │  │ Revenue      │            │   │   │
│  │  │  │ Revenue      │  │ Distribution │            │   │   │
│  │  │  │              │  │              │            │   │   │
│  │  │  │ [🔍 Zoom]    │  │ [🔍 Zoom]    │            │   │   │
│  │  │  └──────────────┘  └──────────────┘            │   │   │
│  │  └─────────────────────────────────────────────────┘   │   │
│  │                                                         │   │
│  │  ┌─ Analysis Plan (LLM reasoning trace) ──────────┐   │   │
│  │  │ 1. User asks about Q3 revenue                     │   │   │
│  │  │ 2. Identify date range for Q3                    │   │   │
│  │  │ 3. Filter dataset to Q3 dates                    │   │   │
│  │  │ 4. Aggregate Revenue column                      │   │   │
│  │  │ 5. Group by Product for breakdown                │   │   │
│  │  │ 6. Generate charts for visualisation             │   │   │
│  │  └───────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

**Key Differences from Chat View:**

1. **Charts are displayed inline** as images (not just filenames) — the API returns base64 data URLs in `chart_images`
2. **Analysis plan is visible** — the `plan` field from `AnalyseResponse` shows the LLM's reasoning steps
3. **Evidence is fully expanded** — all sections (findings, calculations, sources, tools) are shown expanded by default, not collapsed
4. **Confidence is a visual ring/gauge** — not just a percentage text
5. **Tools show execution status** — each tool shows completion status and timing (when available from plan)
6. **Chart lightbox** — clicking any chart opens a full-size modal overlay

**Components:**

| Component | Description |
|-----------|-------------|
| `AnalysisHeader` | Back navigation, stateless question input |
| `AnalysisResultCard` | Full analysis result with all evidence |
| `ConfidenceRing` | SVG circular progress showing confidence |
| `EvidenceAccordion` | Expandable sections for findings/calculations/sources/tools |
| `ChartGallery` | Grid of inline chart images with zoom capability |
| `ChartLightbox` | Modal overlay for full-size chart viewing |
| `AnalysisPlanViewer` | Step-by-step display of the LLM's analysis plan |

---

### 6.4 Reports

**Route:** `/reports`  
**Purpose:** Generate, view, and manage deterministic analytical reports.

**Layout:**

```
┌─────────────────────────────────────────────────────────────────┐
│  Reports Header                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Reports                                                 │  │
│  │  Deterministic summaries. Every figure is calculated,    │  │
│  │  never written by the model.                             │  │
│  └──────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  REPORT GENERATOR                                       │   │
│  │                                                         │   │
│  │  Data source:  [sample_sales.xlsx          ▾]          │   │
│  │                ┌─────────────────────────────┐          │   │
│  │                │ Currently loaded dataset   │          │   │
│  │                │ sample_sales.xlsx (240 rows)│ ◄── active│  │
│  │                │ sample.csv (120 rows)       │          │   │
│  │                │ sales.db (via SQL)          │          │   │
│  │                └─────────────────────────────┘          │   │
│  │                                                         │   │
│  │  Session:      [Optional: select a session  ▾]         │   │
│  │                ┌─────────────────────────────┐          │   │
│  │                │ No session (standalone)     │          │   │
│  │                │ Sales Analysis              │          │   │
│  │                │ Revenue Deep-Dive           │          │   │
│  │                └─────────────────────────────┘          │   │
│  │                                                         │   │
│  │  [⚡ Generate Report]                                  │   │
│  │                                                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  REPORT LIST                                            │   │
│  │                                                         │   │
│  │  ┌──────────────────────────────────────────────────┐  │   │
│  │  │ 📊 sample_sales.xlsx                            │  │   │
│  │  │ "Revenue analysis across 8 products and         │  │   │
│  │  │  5 regions..."                                   │  │   │
│  │  │ 2 hours ago  ·  4 findings  ·  3 charts    ×   │  │   │
│  │  └──────────────────────────────────────────────────┘  │   │
│  │                                                         │   │
│  │  ┌──────────────────────────────────────────────────┐  │   │
│  │  │ 📊 sample.csv                                    │  │   │
│  │  │ "Monthly revenue trend across 12 months..."      │  │   │
│  │  │ 1 day ago  ·  2 findings  ·  2 charts       ×   │  │   │
│  │  └──────────────────────────────────────────────────┘  │   │
│  │                                                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ── OR — Report Detail View ─────────────────────────────────  │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  [← All Reports]  sample_sales.xlsx           [× Delete]│  │
│  │  Generated: 2026-10-14 14:32  ·  sample_sales.xlsx    │  │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  FACTS                                                  │   │
│  │  What the data contains.                                │   │
│  │                                                         │   │
│  │  ● The dataset contains 240 rows across 8 columns.     │   │
│  │  ● Total revenue across all products is R2,847,300.    │   │
│  │  ● The highest-revenue product is Laptop at R1,197,600│   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  CALCULATED FINDINGS                                    │   │
│  │  Derived by deterministic arithmetic.                   │   │
│  │                                                         │   │
│  │  ● Laptop accounts for 42.1% of total revenue.         │   │
│  │  ● North generates the most revenue at R892,400.       │   │
│  │  ● Revenue moved from R312,000 in Jan to R587,300     │   │
│  │    in Sep, a change of +88.2%.                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  INTERPRETATIONS                                        │   │
│  │  What the pattern appears to mean.                      │   │
│  │                                                         │   │
│  │  ● Revenue appears to be growing across the period     │   │
│  │    covered by the dataset.                             │   │
│  │  ● Revenue appears concentrated in Laptop, which       │   │
│  │    alone exceeds half of the total.                    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  RECOMMENDATIONS                                        │   │
│  │  Suggested actions.                                     │   │
│  │                                                         │   │
│  │  ● Review the pipeline feeding Laptop - concentration  │   │
│  │    of this size makes overall revenue sensitive to     │   │
│  │    that one category.                                  │   │
│  │  ● Correlate the growth with documented strategy       │   │
│  │    changes before acting on it.                        │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  CHARTS                                                 │   │
│  │                                                         │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │   │
│  │  │[Chart 1] │ │[Chart 2] │ │[Chart 3] │ │[Chart 4] │  │   │
│  │  │Revenue   │ │Revenue   │ │Monthly   │ │Revenue   │  │   │
│  │  │by Product│ │by Region │ │Revenue   │ │Trend     │  │   │
│  │  │[🔍 Zoom] │ │[🔍 Zoom] │ │[🔍 Zoom] │ │[🔍 Zoom] │  │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  [▶ Full Text Report]  (expandable <details>)           │  │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

**CRITICAL: Dataset Switching Bug Fix**

The v1 bug: `reportSource` was a `signal<string>('')` bound to a `<select>`. When the user selected a dataset, the signal updated, but `generateReport()` passed `this.reportSource() || null` — which meant an empty string was converted to null (use currently loaded). The issue was that the signal and the actual API call could get out of sync during change detection, and the select's `(change)` handler didn't always fire before the button click.

**Fix in v2:**

```typescript
// report-state.service.ts
@Injectable({ providedIn: 'root' })
export class ReportStateService {
  // ... other signals ...
  
  // The selected dataset for report generation.
  // '' means "use currently loaded dataset" (sent as null to API).
  readonly selectedDataset = signal<string>('');
  
  // The session selected for report generation.
  readonly selectedSession = signal<string | null>(null);
  
  // The ACTUAL parameters used for the last generation.
  // These are set atomically when generateReport is called.
  private readonly lastGenerationParams = signal<{
    dataset: string | null;
    sessionId: string | null;
  } | null>(null);
  
  /**
   * Generate a report with the currently selected parameters.
   * 
   * FIX: Instead of reading the signal at call time and passing
   * it to the API, we capture the values atomically and store them.
   * This ensures the UI always shows what was actually generated.
   */
  async generate(): Promise<void> {
    this.generatingReport.set(true);
    this.reportError.set(null);
    
    // Capture the current selection atomically
    const datasetName = this.selectedDataset();
    const sessionId = this.selectedSession();
    
    this.lastGenerationParams.set({
      dataset: datasetName || null,
      session: sessionId,
    });
    
    try {
      const report = await this.api.generateReport(
        sessionId,
        datasetName || null,
      );
      this.activeReport.set(report);
      await this.loadReports();
    } catch (error) {
      this.reportError.set(this.describe(error));
    } finally {
      this.generatingReport.set(false);
    }
  }
  
  /**
   * Get the display name of the dataset that was used for
   * the currently open report.
   */
  getActiveReportDatasetName(): string {
    const report = this.activeReport();
    return report?.dataset_name ?? 'Unknown';
  }
}
```

**Additional safeguards:**
1. The `<select>` uses `[(ngModel)]` instead of `(change)` for two-way binding — no timing issues
2. The Generate button shows the selected dataset name in its label: `Generate report for [sample_sales.xlsx]`
3. After generation, the report detail view shows which dataset was used (from `report.dataset_name`)
4. If the selected dataset is deleted while viewing a report, the report still displays correctly (it has its own copy of the data)

**Report Detail View** is a separate component that receives the `ReportDetail` object. It does not re-fetch data when switching datasets — it renders whatever report is in `activeReport` signal. The dataset selector only affects the *next* generation.

---

### 6.5 Datasets

**Route:** `/datasets`  
**Purpose:** Manage datasets — view, upload, delete, select active dataset, preview columns.

**Layout:**

```
┌─────────────────────────────────────────────────────────────────┐
│  Datasets Header                                                │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Datasets                                                │  │
│  │  Upload, inspect, and manage your data files.            │  │
│  └──────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  UPLOAD ZONE (drag-and-drop)                            │   │
│  │                                                         │   │
│  │              ┌─────────────────────────┐                │   │
│  │              │                         │                │   │
│  │              │    📁 Drag files here    │                │   │
│  │              │    or click to browse   │                │   │
│  │              │                         │                │   │
│  │              │  .csv  .xlsx  .xls     │                │   │
│  │              │  Max 10 MB              │                │   │
│  │              │                         │                │   │
│  │              └─────────────────────────┘                │   │
│  │                                                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  REGISTERED DATASETS                                    │   │
│  │                                                         │   │
│  │  ┌───────────────────────────────────────────────────┐ │   │
│  │  │ 📊 sample_sales.xlsx                    ● ACTIVE │ │   │
│  │  │                                                   │ │   │
│  │  │  240 rows × 8 columns                             │ │   │
│  │  │  Columns: Date, Product, Region, Revenue,        │ │   │
│  │  │  Quantity, Cost, Profit, Customer                │ │   │
│  │  │                                                   │ │   │
│  │  │  ┌─ Column Preview ─────────────────────────┐    │ │   │
│  │  │  │ Column        Type        Missing       │    │ │   │
│  │  │  │ ─────────────────────────────────────── │    │ │   │
│  │  │  │ Date          datetime64   0            │    │ │   │
│  │  │  │ Product       object        0            │    │ │   │
│  │  │  │ Region        object        0            │    │ │   │
│  │  │  │ Revenue       float64       0            │    │ │   │
│  │  │  │ Quantity      int64         0            │    │ │   │
│  │  │  │ Cost          float64       3            │    │ │   │
│  │  │  │ Profit        float64       0            │    │ │   │
│  │  │  │ Customer      object        12           │    │ │   │
│  │  │  └───────────────────────────────────────────┘    │ │   │
│  │  │                                                   │ │   │
│  │  │  [Set Active]  [Preview Data]  [Delete ×]         │ │   │
│  │  └───────────────────────────────────────────────────┘ │   │
│  │                                                         │   │
│  │  ┌───────────────────────────────────────────────────┐ │   │
│  │  │ 📊 sample.csv                                    │ │   │
│  │  │                                                   │ │   │
│  │  │  120 rows × 5 columns                             │ │   │
│  │  │  Columns: Month, Revenue, Expenses, Profit, ROI  │ │   │
│  │  │                                                   │ │   │
│  │  │  [Set Active]  [Preview Data]  [Delete ×]         │ │   │
│  │  └───────────────────────────────────────────────────┘ │   │
│  │                                                         │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

**Components:**

| Component | Description |
|-----------|-------------|
| `DatasetUploadZone` | Drag-and-drop area with click-to-browse fallback |
| `DatasetCard` | Dataset info, column preview, action buttons |
| `ColumnPreviewTable` | Expandable table showing column names, types, missing values |
| `DataPreviewModal` | Modal showing first 10 rows of the dataset |
| `DatasetDeleteConfirm` | Browser confirm dialog (destructive action) |

**Interactions:**

1. **Upload:** Drag file onto drop zone OR click to browse → file is held in `pendingUpload` signal → confirmation modal shows file name, size, type → confirm → upload to `/api/datasets` → on success, dataset list refreshes → toast notification shows "Uploaded X — N rows, M columns"

2. **Set Active:** Click "Set Active" on a dataset card → `AppStateService.activeDataset` updates → all components that depend on it react (header pill, chat sidebar, report generator default) → toast notification

3. **Preview:** Click "Preview Data" → modal opens showing first 10 rows in a table (fetched via API or computed from upload response)

4. **Delete:** Click × → browser `confirm()` → if confirmed, delete → list refreshes → if the deleted dataset was active, active resets to first remaining or empty

5. **Column preview:** Click to expand column details showing name, dtype, and missing value count

---

### 6.6 Documents

**Route:** `/documents`  
**Purpose:** Manage documents — view, upload, delete, check indexing status.

**Layout:**

```
┌─────────────────────────────────────────────────────────────────┐
│  Documents Header                                               │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Documents                                               │  │
│  │  Upload source material for the RAG retrieval engine.    │  │
│  └──────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  UPLOAD ZONE (drag-and-drop)                            │   │
│  │                                                         │   │
│  │              ┌─────────────────────────┐                │   │
│  │              │    📄 Drag files here    │                │   │
│  │              │    or click to browse   │                │   │
│  │              │                         │                │   │
│  │              │  .txt  .pdf  .docx      │                │   │
│  │              │  Max 10 MB              │                │   │
│  │              │                         │                │   │
│  │              └─────────────────────────┘                │   │
│  │                                                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  INDEXED DOCUMENTS (5)                                  │   │
│  │                                                         │   │
│  │  ┌───────────────────────────────────────────────────┐ │   │
│  │  │ 📄 AI_Data_Analyst_Chatbot_Roadmap.pdf           │ │   │
│  │  │                                                   │ │   │
│  │  │  Indexed ✓  ·  34 chunks  ·  298 KB             │ │   │
│  │  │  Type: PDF  ·  Uploaded: 2026-10-08             │ │   │
│  │  │                                                   │ │   │
│  │  │  [View chunks]  [Re-index]  [Delete ×]           │ │   │
│  │  └───────────────────────────────────────────────────┘ │   │
│  │                                                         │   │
│  │  ┌───────────────────────────────────────────────────┐ │   │
│  │  │ 📄 FY2026_Sales_Strategy.docx                    │ │   │
│  │  │                                                   │ │   │
│  │  │  Indexed ✓  ·  12 chunks  ·  39 KB              │ │   │
│  │  │  Type: DOCX  ·  Uploaded: 2026-10-12            │ │   │
│  │  │                                                   │ │   │
│  │  │  [View chunks]  [Re-index]  [Delete ×]           │ │   │
│  │  └───────────────────────────────────────────────────┘ │   │
│  │                                                         │   │
│  │  ┌───────────────────────────────────────────────────┐ │   │
│  │  │ 📄 sample_notes.txt                              │ │   │
│  │  │                                                   │ │   │
│  │  │  Indexed ✓  ·  3 chunks  ·  2.1 KB              │ │   │
│  │  │  Type: TXT  ·  Uploaded: 2026-10-13             │ │   │
│  │  │                                                   │ │   │
│  │  │  [View chunks]  [Re-index]  [Delete ×]           │ │   │
│  │  └───────────────────────────────────────────────────┘ │   │
│  │                                                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  INFO PANEL                                             │   │
│  │                                                         │   │
│  │  Documents are processed by the RAG pipeline:           │   │
│  │  1. Loaded and split into chunks                        │   │
│  │  2. Embedded using sentence-transformers                │   │
│  │  3. Stored in ChromaDB vector store                     │   │
│  │                                                         │   │
│  │  When you delete a document, both the file and its      │   │
│  │  indexed chunks are removed.                            │   │
│  │                                                         │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

**Components:**

| Component | Description |
|-----------|-------------|
| `DocumentUploadZone` | Drag-and-drop area for documents |
| `DocumentCard` | Document info, chunk count, indexing status |
| `IndexingStatusBadge` | Visual badge showing indexed/pending/error state |
| `ChunkViewerModal` | Modal showing the document's indexed chunks |
| `DocumentDeleteConfirm` | Browser confirm (destructive) |

---

## 7. Interaction Patterns

### 7.1 Loading States

Every data-fetching operation shows a loading indicator:

| Pattern | Usage |
|---------|-------|
| **Skeleton cards** | Dashboard overview cards while data loads |
| **Spinner overlay** | Chat transcript while asking a question |
| **Button loading state** | Generate report, upload buttons show spinner + disable |
| **Progress bar** | File upload progress (if supported by gateway) |
| **Pulsing dot** | Health status while checking |

### 7.2 Empty States

Every list has a meaningful empty state:

| Location | Message | CTA |
|----------|---------|-----|
| Chat (no sessions) | "No conversations yet. Start one!" | [New Conversation] |
| Chat (empty transcript) | "Ask a question to begin analysis" | Shows sample prompts |
| Reports (no reports) | "No reports generated yet" | [Generate First Report] |
| Datasets (no datasets) | "No datasets registered" | [Upload Dataset] |
| Documents (no documents) | "No documents indexed" | [Upload Document] |
| Analysis (no result) | "Ask a question to see analysis" | [Input field] |

### 7.3 Error States

| Type | Display | Action |
|------|---------|--------|
| Gateway unreachable | Full-page error with retry | [Retry Connection] |
| API error (4xx/5xx) | Toast notification + inline banner | Dismissible |
| Validation error | Inline field message | Fix and retry |
| Upload size/extension rejection | Modal error message | Pick different file |
| Timeout | Toast with "try again later" | Auto-dismiss after 10s |

### 7.4 Toast Notifications

```
┌──────────────────────────────────────────┐
│ ✅ Uploaded sample_sales.xlsx —           │
│    240 rows, 8 columns              [×]  │
└──────────────────────────────────────────┘
```

- Position: bottom-right corner
- Auto-dismiss: 5 seconds for success, 10 seconds for error
- Types: success (green), error (red), info (blue), warning (amber)
- Stacked: max 3 visible, older ones fade

### 7.5 Modal Dialogs

Standard modal structure:
- Backdrop: semi-transparent overlay, click to close
- Container: centered, max-width 480px, elevation shadow
- Header: title + close button
- Body: content (form, file preview, etc.)
- Footer: action buttons (Cancel, Confirm)

Keyboard: `Escape` closes, `Enter` confirms (when input is focused).

---

## 8. File Upload UX

### 8.1 Drag-and-Drop

Both Datasets and Documents pages use a shared `DropZoneComponent`:

```
┌─────────────────────────────────────────────┐
│                                             │
│   ┌─────────────────────────────────────┐   │
│   │                                     │   │
│   │          📁                         │   │
│   │                                     │   │
│   │     Drag files here                 │   │
│   │     or click to browse              │   │
│   │                                     │   │
│   │     .csv  .xlsx  .xls  (datasets)  │   │
│   │     .txt  .pdf  .docx  (documents) │   │
│   │     Max 10 MB                       │   │
│   │                                     │   │
│   └─────────────────────────────────────┘   │
│                                             │
└─────────────────────────────────────────────┘
```

**States:**
- **Idle:** Dashed border, subtle background
- **Drag over:** Solid brand-colored border, tinted background, scale up slightly
- **File selected:** Shows file preview card inside the zone
- **Uploading:** Progress bar, disabled state
- **Success:** Green checkmark, auto-dismiss
- **Error:** Red border, error message

**Interactions:**
1. User drags file over zone → zone highlights
2. User drops file → file is validated (type + size)
3. If valid: file preview card appears with name, size, and "Upload" button
4. If invalid: error message appears ("File type not supported" or "File exceeds 10 MB")
5. User clicks "Upload" → confirmation modal → upload begins
6. Upload completes → success toast → list refreshes

### 8.2 File Validation

| Rule | Datasets | Documents |
|------|----------|-----------|
| Accepted types | .csv, .xlsx, .xls | .txt, .pdf, .docx |
| Max size | 10 MB | 10 MB |
| Validation | Client-side (type + size) before upload | Client-side (type + size) before upload |
| Error display | Inline in drop zone + toast | Inline in drop zone + toast |

### 8.3 Upload Flow

```
User selects file
       │
       ▼
┌──────────────┐
│ Client-side  │── type/size validation ──▶ Error → show message
│ validation   │
└──────┬───────┘
       │ valid
       ▼
┌──────────────┐
│ Show file    │── user can cancel or change
│ preview card │
└──────┬───────┘
       │ user clicks Upload
       ▼
┌──────────────┐
│ Confirmation │── modal with file name, size
│ modal        │
└──────┬───────┘
       │ user confirms
       ▼
┌──────────────┐
│ POST /api/   │── FormData with file
│ datasets     │   or /api/documents
│   or         │
│ documents    │
└──────┬───────┘
       │
       ├─ success → toast + refresh list
       │
       └─ error → toast with API error detail
```

---

## 9. Chat Interface Design

### 9.1 Message Flow

```
User types question
       │
       ▼
┌─────────────────┐
│ Turn added to   │── pending: true, question visible
│ transcript      │── typing indicator shown
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ POST /api/chat  │── { session_id, message }
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Response received│── ChatResponse with answer, evidence, charts
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Answer streams  │── characters revealed progressively (20ms/3 chars)
│ character-by-   │── creates "real-time" feel
│ character       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Evidence panels │── findings, calculations, sources, tools
│ render below    │── charts display as inline images
│ answer          │── confidence meter animates to value
└─────────────────┘
```

### 9.2 Turn Card Anatomy

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  [User avatar]  You                                         │
│                 ──────────────────────────────────────────  │
│                 What was the total revenue last quarter?    │
│                                                             │
│  [AI avatar]    🤖 AI Analyst                               │
│                 ──────────────────────────────────────────  │
│                                                             │
│                 The total revenue for Q3 2026 was           │
│                 R2,847,300. This was calculated by         │
│                 summing all Revenue values where the        │
│                 Date fell between 2026-07-01 and            │
│                 2026-09-30.                                 │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  📊 ANALYSIS METADATA                                 │  │
│  │                                                       │  │
│  │  Confidence: ████████░░ 82%                         │  │
│  │  Type: ● dataset analysis                            │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌─ Key Findings ──────────────────────────────────────┐    │
│  │ ● Q3 total revenue: R2,847,300                      │    │
│  │ ● Top product: Laptop (R1.2M, 42.1%)               │    │
│  │ ● Growth vs Q2: +12.3%                              │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                             │
│  ┌─ Calculations ──────────────────────────────────────┐    │
│  │ aggregate_dataset(Revenue, sum) → R2,847,300        │    │
│  │ filter_dataset(Date, 2026-07-01..2026-09-30)        │    │
│  │ group_by_column(Product, Revenue, sum)               │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                             │
│  ┌─ Data Sources ──────────────────────────────────────┐    │
│  │ 📄 sample_sales.xlsx (240 rows × 8 columns)         │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                             │
│  ┌─ Tools Executed ────────────────────────────────────┐    │
│  │ 🔧 aggregate_dataset ✓  🔧 filter_dataset ✓        │    │
│  │ 🔧 group_by_column ✓   🔧 calculate_statistics ✓  │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                             │
│  ┌─ Charts ────────────────────────────────────────────┐    │
│  │ ┌──────────┐  ┌──────────┐                          │    │
│  │ │ [Chart]  │  │ [Chart]  │                          │    │
│  │ │ Revenue  │  │ Revenue  │                          │    │
│  │ │ by Prod  │  │ by Reg   │                          │    │
│  │ └──────────┘  └──────────┘                          │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 9.3 Auto-Scroll Behavior

```typescript
// In ChatPage component
private setupAutoScroll(): void {
  effect(() => {
    this.chatState.turns();
    this.chatState.asking();
    
    requestAnimationFrame(() => {
      const container = this.transcriptRef()?.nativeElement;
      if (container) {
        // Smooth scroll to bottom
        container.scrollTo({
          top: container.scrollHeight,
          behavior: 'smooth',
        });
      }
    });
  });
}
```

### 9.4 Composer Design

```
┌─────────────────────────────────────────────────────────────┐
│  ┌─────────────────────────────────────────┐ ┌───────────┐ │
│  │ Ask a question about your data...        │ │ [Send →]  │ │
│  └─────────────────────────────────────────┘ └───────────┘ │
│                                                             │
│  Quick prompts:                                             │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐       │
│  │ Total revenue│ │ Top region   │ │ By product   │       │
│  └──────────────┘ └──────────────┘ └──────────────┘       │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐       │
│  │ Monthly trend│ │ Missing data │ │ Distribution │       │
│  └──────────────┘ └──────────────┘ └──────────────┘       │
│                                                             │
│  Active dataset: [sample_sales.xlsx ▾]                      │
└─────────────────────────────────────────────────────────────┘
```

- Input: single-line text field, grows to max 3 lines, Enter to send
- Send button: disabled when input is empty or request in flight
- Quick prompts: clickable chips that fill the input (don't auto-send)
- Active dataset indicator: shows which dataset the analysis will use

---

## 10. Analysis Result Display

### 10.1 Confidence Visualization

Instead of plain text "confidence: 82%", render an animated SVG ring:

```html
<svg class="confidence-ring" viewBox="0 0 100 100">
  <!-- Background ring -->
  <circle cx="50" cy="50" r="45" 
    fill="none" stroke="var(--border-standard)" 
    stroke-width="8" />
  <!-- Progress ring -->
  <circle cx="50" cy="50" r="45" 
    fill="none" stroke="var(--accent-emerald)" 
    stroke-width="8"
    stroke-dasharray="283"
    [attr.stroke-dashoffset]="confidenceOffset()"
    stroke-linecap="round"
    transform="rotate(-90 50 50)"
    class="confidence-progress" />
  <!-- Center text -->
  <text x="50" y="50" text-anchor="middle" 
    class="confidence-text">82%</text>
</svg>
```

Color coding:
- ≥ 80%: green (`--accent-emerald`)
- 60–79%: amber (`--accent-amber`)
- < 60%: red (`--accent-rose`)

### 10.2 Evidence Section Rendering

Each evidence section (findings, calculations, sources, tools) renders as a distinct visual block with its own icon and styling:

```
┌─ 🔍 Key Findings ──────────────────────────────────────┐
│                                                        │
│  ● Q3 total revenue: R2,847,300                        │
│  ● Top product: Laptop (R1.2M, 42.1% of total)       │
│  ● Growth vs Q2: +12.3%                                │
│                                                        │
└────────────────────────────────────────────────────────┘

┐
│  ┌─ 🧮 Calculations Performed ─────────────────────────┐
│                                                        │
│  │ aggregate_dataset(Revenue, sum) → R2,847,300        │
│  │ filter_dataset(Date, 2026-07-01..2026-09-30)        │
│  │ group_by_column(Product, Revenue, sum)               │
│  │ calculate_statistics(Revenue) → mean: R11,864       │
│                                                        │
│  └────────────────────────────────────────────────────────┘
```

### 10.3 Chart Display

Charts from the API come as base64 data URLs in `chart_images` (for reports) or file paths in `visualisations` (for chat). The chat view shows chart filenames (since the gateway proxy doesn't serve PNG bytes), while the Analysis and Reports views show actual images.

```html
<!-- Report/Analysis view — inline image -->
<figure class="chart-card">
  <img [src]="chart.dataUrl" 
       [alt]="chart.name"
       loading="lazy"
       (click)="openLightbox(chart)" />
  <figcaption>{{ chart.name }}</figcaption>
</figure>

<!-- Chat view — filename reference -->
<code class="chart-filename">{{ chart.filename }}</code>
```

### 10.4 Chart Lightbox

Clicking any chart image opens a full-screen modal:

```
┌─────────────────────────────────────────────┐
│                                     [×]     │
│                                             │
│                                             │
│            ┌─────────────────────┐          │
│            │                     │          │
│            │   [Full-size chart  │          │
│            │    image]           │          │
│            │                     │          │
│            └─────────────────────┘          │
│                                             │
│            Revenue by Product                │
│                                             │
└─────────────────────────────────────────────┘
```

- Click backdrop or press Escape to close
- Image is centered, max 90vw/90vh
- Caption shows chart name

---

## 11. Report Viewer Design

### 11.1 Report Generation Flow (Fixed)

**The v1 bug:** `reportSource` signal was `''` by default. When the user selected a dataset from the `<select>`, the signal updated via `(change)` handler. But `generateReport()` read `this.reportSource()` which could race with the change event, or the select could show a selected value while the signal hadn't propagated yet. Additionally, `''` was passed as `null` to the API (meaning "use currently loaded dataset"), so the UI would show a dataset selected but the report was actually generated from a different one.

**The v2 fix:**

1. **Use `[(ngModel)]` two-way binding** on the select — no `(change)` handler needed
2. **Capture parameters atomically** at the moment "Generate" is clicked
3. **Store the actual generation parameters** separately from the selector state
4. **Display the actual dataset used** from the response (`report.dataset_name`), not from the selector
5. **Validate before sending:** if a dataset is selected, verify it still exists in the dataset list

```html
<!-- Reports page template -->
<div class="report-generator">
  <label>
    Data source
    <select [(ngModel)]="reportState.selectedDataset()">
      <option value="">Currently loaded dataset</option>
      <option *ngFor="let ds of datasetState.datasetList()" 
              [value]="ds.name">
        {{ ds.name }} ({{ ds.rows }} rows)
      </option>
    </select>
  </label>
  
  <label>
    Attach to session (optional)
    <select [(ngModel)]="reportState.selectedSession()">
      <option [value]="null">No session (standalone)</option>
      <option *ngFor="let s of chatState.sessions()" 
              [value]="s.session_id">
        {{ s.name }}
      </option>
    </select>
  </label>
  
  <button (click)="generateReport()" 
          [disabled]="reportState.generatingReport()">
    {{ reportState.generatingReport() ? 'Generating…' : 'Generate Report' }}
  </button>
  
  <!-- Shows the ACTUAL dataset used for the open report -->
  <p class="report-dataset-indicator">
    Showing report for: <strong>{{ activeReportDatasetName() }}</strong>
  </p>
</div>
```

### 11.2 Report List View

```
┌──────────────────────────────────────────────────────────┐
│  REPORT LIST                                             │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │ 📊 sample_sales.xlsx                    [Open] [×] │  │
│  │ "Revenue analysis across 8 products and 5 regions" │  │
│  │ 2h ago · 4 findings · 3 charts · 240 rows         │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │ 📊 sample.csv                          [Open] [×] │  │
│  │ "Monthly revenue trend across 12 months"          │  │
│  │ 1d ago · 2 findings · 2 charts · 120 rows         │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

Each report card shows:
- Dataset name (icon + text)
- Preview text (first ~80 chars)
- Metadata: time ago, finding count, chart count, row count
- Actions: Open, Delete

### 11.3 Report Detail View

The detail view renders the `ReportDetail` object with these sections in order:

1. **Header:** Report ID, dataset name, creation date, session link, delete button
2. **Facts:** Bullet list from `report.layers.facts`
3. **Calculated Findings:** Bullet list from `report.layers.calculated_findings`
4. **Interpretations:** Bullet list from `report.layers.interpretations`
5. **Recommendations:** Bullet list from `report.layers.recommendations`
6. **Charts:** Grid of inline images from `report.chart_images` (base64 data URLs)
7. **Full Text Report:** Expandable `<details>` with `report.content` in a `<pre>` block

Each evidence layer section has:
- A distinct visual treatment (different icon, different accent color)
- The section title and hint text
- Bullet list items
- If the layer is empty, the section is hidden (not shown as empty)

---

## 12. Accessibility

### 12.1 WCAG 2.1 AA Compliance

| Requirement | Implementation |
|-------------|---------------|
| **Color contrast** | All text meets 4.5:1 contrast ratio against its background |
| **Focus indicators** | Visible 2px outline on all interactive elements (`:focus-visible`) |
| **Keyboard navigation** | All features accessible via keyboard; tab order follows visual order |
| **Screen readers** | ARIA labels on icon-only buttons; `aria-live` on toast notifications; `role="status"` on loading indicators |
| **Form labels** | All inputs have associated `<label>` elements |
| **Error identification** | Errors announced via `aria-describedby` or `role="alert"` |

### 12.2 ARIA Patterns

```html
<!-- Navigation -->
<nav aria-label="Main navigation">
  <a routerLink="/chat" aria-current="page">Chat</a>
</nav>

<!-- Chat transcript -->
<div class="transcript" 
     role="log" 
     aria-live="polite" 
     aria-label="Conversation transcript">
  <!-- turns -->
</div>

<!-- Toast notifications -->
<div role="alert" aria-live="assertive">
  Uploaded sample_sales.xlsx
</div>

<!-- Modal dialog -->
<div role="dialog" aria-modal="true" aria-labelledby="dialog-title">
  <h2 id="dialog-title">Upload Dataset</h2>
</div>

<!-- Loading state -->
<div role="status" aria-label="Analyzing your question...">
  <span class="spinner" aria-hidden="true"></span>
  Analyzing...
</div>
```

### 12.3 Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Ctrl/Cmd + K` | Focus search / new question input |
| `Ctrl/Cmd + N` | New conversation (in Chat) |
| `Enter` | Send message (in composer) |
| `Escape` | Close modal / dialog |
| `Tab` | Navigate between interactive elements |
| `↑ / ↓` | Navigate session list (when sidebar focused) |

### 12.4 Reduced Motion

```css
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

---

## 13. Responsive Layout

### 13.1 Breakpoints

| Breakpoint | Width | Layout |
|-----------|-------|--------|
| `xs` | < 480px | Single column, sidebar as drawer |
| `sm` | 480–767px | Single column, sidebar as drawer |
| `md` | 768–1023px | Sidebar visible, 2-column grids |
| `lg` | 1024–1439px | Full layout, 3-column grids |
| `xl` | ≥ 1440px | Full layout, max-width 1440px container |

### 13.2 Layout Behavior

**Desktop (≥ 1024px):**
- Sidebar: 240px fixed, collapsible to 72px
- Content: fills remaining width
- Chat: transcript + composer stacked vertically
- Dashboard: 3-column grid
- Datasets/Documents: 2-column grid
- Reports: list + detail side-by-side

**Tablet (768–1023px):**
- Sidebar: 72px icon-only (collapsed)
- Dashboard: 2-column grid
- Reports: list + detail stacked

**Mobile (< 768px):**
- Sidebar: hidden, accessible via hamburger menu (drawer overlay)
- All grids: single column
- Chat: full-screen with floating session switcher
- Report generator: stacked controls
- Touch targets: minimum 44×44px

### 13.3 Mobile Chat View

```
┌─────────────────────────────┐
│ [←]  Chat          [≡] [⋮] │
├─────────────────────────────┤
│                             │
│  Transcript                 │
│  (full width, scrollable)   │
│                             │
│                             │
├─────────────────────────────┤
│  ┌───────────────────────┐  │
│  │ Ask a question...     │  │
│  └───────────────────┬───┘  │
│                     [→]    │
│  [Total?] [Region?] [Prod?] │
└─────────────────────────────┘
```

Hamburger menu opens session sidebar as a drawer overlay from the left.

---

## 14. Migration from v1

### 14.1 What to Keep

| Aspect | v1 Location | v2 Target |
|--------|------------|-----------|
| API service base | `api.service.ts` | Refactored `core/services/api.service.ts` |
| Error handling | `GatewayError` class | Same, enhanced |
| Signal-based state | `app.ts` signals | Distributed across domain services |
| Security tests | `api.service.spec.ts` | Preserved, never break |
| Dark mode CSS | `app.css` | Refactored into design tokens |
| Chat logic | `app.ts` ask/loadSession | `ChatStateService` |
| Report sections | `app.ts` reportSections | `ReportsPage` template |
| Upload flow | `app.ts` chooseUpload/confirmUpload | `DropZoneComponent` + `UploadModal` |

### 14.2 What to Replace

| v1 Problem | v2 Solution |
|-----------|-------------|
| Single monolithic `AppComponent` | 6 page components + shared components |
| No routing (signal-based view switch) | Angular Router with 6 routes |
| No Angular Material | Material components for accessibility |
| Charts not displayed inline | `<img>` from base64 data URLs in Analysis/Reports |
| Evidence hidden in `<details>` | Always-expanded evidence blocks with visual hierarchy |
| No dashboard | Dashboard page with overview |
| Report dataset switching bug | Atomic parameter capture + response-based display |
| No dark/light toggle | Theme toggle with CSS custom properties |
| No drag-and-drop upload | `DropZoneComponent` with drag events |
| No toast notification system | `ToastService` with signal-based queue |
| No empty states | `EmptyStateComponent` with contextual CTAs |
| No loading skeletons | `SkeletonCardComponent` |
| Text-only "Thinking…" | Animated typing indicator with dots |
| No streaming feel | Character-by-character answer reveal |

### 14.3 File Structure (v2)

```
web/src/
├── main.ts
├── index.html
├── styles/
│   ├── _tokens.css          # Design tokens (CSS custom properties)
│   ├── _reset.css           # CSS reset / normalize
│   ├── _typography.css      # Typography base styles
│   ├── _animations.css      # Keyframe animations
│   ├── _utilities.css       # Utility classes
│   └── main.css             # Entry point, imports all above
├── app/
│   ├── app.config.ts        # Application config (router, providers)
│   ├── app.component.ts     # Root shell component
│   ├── app.routes.ts        # Route definitions
│   ├── core/
│   │   ├── components/
│   │   │   ├── header/
│   │   │   ├── sidebar/
│   │   │   ├── base64-image/
│   │   │   ├── empty-state/
│   │   │   ├── loading-spinner/
│   │   │   ├── error-banner/
│   │   │   ├── confirm-dialog/
│   │   │   ├── toast-notification/
│   │   │   ├── skeleton-card/
│   │   │   └── chart-lightbox/
│   │   ├── services/
│   │   │   ├── api.service.ts
│   │   │   ├── app-state.service.ts
│   │   │   ├── theme.service.ts
│   │   │   └── toast.service.ts
│   │   ├── guards/
│   │   │   └── health.guard.ts
│   │   └── interceptors/
│   │       └── error.interceptor.ts
│   ├── features/
│   │   ├── dashboard/
│   │   │   ├── dashboard.page.ts
│   │   │   ├── dashboard.page.html
│   │   │   ├── dashboard.page.css
│   │   │   └── components/
│   │   │       ├── hero-section/
│   │   │       ├── health-overview-card/
│   │   │       ├── dataset-summary-grid/
│   │   │       ├── document-list-card/
│   │   │       ├── recent-reports-card/
│   │   │       └── quick-start-chips/
│   │   ├── chat/
│   │   │   ├── chat.page.ts
│   │   │   ├── chat.page.html
│   │   │   ├── chat.page.css
│   │   │   ├── services/
│   │   │   │   └── chat-state.service.ts
│   │   │   └── components/
│   │   │       ├── session-sidebar/
│   │   │       ├── chat-transcript/
│   │   │       ├── turn-card/
│   │   │       ├── confidence-meter/
│   │   │       ├── evidence-panel/
│   │   │       ├── chart-gallery/
│   │   │       ├── typing-indicator/
│   │   │       └── chat-composer/
│   │   ├── analysis/
│   │   │   ├── analysis.page.ts
│   │   │   ├── analysis.page.html
│   │   │   ├── analysis.page.css
│   │   │   └── components/
│   │   │       ├── analysis-result-card/
│   │   │       ├── confidence-ring/
│   │   │       ├── evidence-accordion/
│   │   │       └── analysis-plan-viewer/
│   │   ├── reports/
│   │   │   ├── reports.page.ts
│   │   │   ├── reports.page.html
│   │   │   ├── reports.page.css
│   │   │   ├── services/
│   │   │   │   └── report-state.service.ts
│   │   │   └── components/
│   │   │       ├── report-generator/
│   │   │       ├── report-list/
│   │   │       └── report-viewer/
│   │   ├── datasets/
│   │   │   ├── datasets.page.ts
│   │   │   ├── datasets.page.html
│   │   │   ├── datasets.page.css
│   │   │   ├── services/
│   │   │   │   └── dataset-state.service.ts
│   │   │   └── components/
│   │   │       ├── dataset-card/
│   │   │       ├── column-preview-table/
│   │   │       └── upload-drop-zone/
│   │   └── documents/
│   │       ├── documents.page.ts
│   │       ├── documents.page.html
│   │       ├── documents.page.css
│   │       ├── services/
│   │       │   └── document-state.service.ts
│   │       └── components/
│   │           ├── document-card/
│   │           ├── indexing-status-badge/
│   │           └── upload-drop-zone/  # shared with datasets
│   └── shared/
│       ├── components/
│       │   ├── upload-drop-zone/
│       │   ├── chart-lightbox/
│       │   └── data-table/
│       └── models/
│           └── api.models.ts    # All API response interfaces
```

---

## 15. Implementation Checklist

### Phase 1: Foundation
- [ ] Set up Angular Material (`ng add @angular/material`)
- [ ] Create design token CSS file (`_tokens.css`)
- [ ] Set up Angular Router with 6 routes
- [ ] Create `AppComponent` shell with header, sidebar, router outlet
- [ ] Implement `ThemeService` (dark/light toggle)
- [ ] Implement `ToastService` (notification queue)
- [ ] Refactor `ApiService` with stronger types
- [ ] Create all state services (`AppStateService`, `ChatStateService`, `ReportStateService`, `DatasetStateService`, `DocumentStateService`)
- [ ] Create shared components (`EmptyState`, `LoadingSpinner`, `ErrorBanner`, `ConfirmDialog`, `SkeletonCard`)
- [ ] Create `Base64ImageComponent`

### Phase 2: Dashboard
- [ ] Create `DashboardPage` with health overview
- [ ] Create `HeroSection` with quick-start prompts
- [ ] Create `HealthOverviewCard`
- [ ] Create `DatasetSummaryGrid` (mini cards)
- [ ] Create `DocumentListCard` (mini list)
- [ ] Create `RecentReportsCard` (last 5 reports)
- [ ] Wire up quick-start chips to navigate to chat

### Phase 3: Chat
- [ ] Create `ChatPage` layout with session sidebar
- [ ] Create `SessionSidebar` component
- [ ] Create `ChatTranscript` with auto-scroll
- [ ] Create `TurnCard` with question + answer + evidence
- [ ] Create `ConfidenceMeter` (animated bar)
- [ ] Create `EvidencePanel` (findings, calculations, sources, tools)
- [ ] Create `ChartGallery` (filenames for chat, images for analysis/reports)
- [ ] Create `TypingIndicator` (animated dots)
- [ ] Create `ChatComposer` with input and send
- [ ] Create `QuickPromptChips`
- [ ] Implement streaming simulation (character-by-character reveal)
- [ ] Implement session CRUD (create, rename, delete, switch)
- [ ] Implement `ChatStateService` with all chat logic

### Phase 4: Analysis
- [ ] Create `AnalysisPage` with stateless question input
- [ ] Create `AnalysisResultCard` with full evidence display
- [ ] Create `ConfidenceRing` (SVG circular gauge)
- [ ] Create `EvidenceAccordion` (expandable sections)
- [ ] Create `AnalysisPlanViewer` (plan steps display)
- [ ] Create `ChartLightbox` (modal for full-size chart viewing)
- [ ] Wire up navigation from chat turn to analysis page

### Phase 5: Reports (Critical — Fix Dataset Switching)
- [ ] Create `ReportsPage` layout
- [ ] Create `ReportGenerator` component with dataset/session selectors
- [ ] **Fix: Use `[(ngModel)]` for two-way binding on selectors**
- [ ] **Fix: Capture generation parameters atomically in `generate()` method**
- [ ] **Fix: Store actual generation params in `lastGenerationParams` signal**
- [ ] **Fix: Display dataset from response, not from selector**
- [ ] Create `ReportList` with report cards
- [ ] Create `ReportDetail` with all evidence layers
- [ ] Create `ReportViewer` with inline chart images
- [ ] Implement report CRUD (generate, list, view, delete)

### Phase 6: Datasets
- [ ] Create `DatasetsPage` layout
- [ ] Create `DropZoneComponent` with drag-and-drop
- [ ] Create `DatasetCard` with column preview
- [ ] Create `ColumnPreviewTable` (expandable)
- [ ] Create `DataPreviewModal` (first 10 rows)
- [ ] Implement dataset CRUD (upload, list, delete, set active)
- [ ] Implement upload confirmation modal

### Phase 7: Documents
- [ ] Create `DocumentsPage` layout
- [ ] Create `DocumentCard` with indexing status
- [ ] Create `IndexingStatusBadge`
- [ ] Create `ChunkViewerModal`
- [ ] Implement document CRUD (upload, list, delete)
- [ ] Reuse `DropZoneComponent`

### Phase 8: Polish
- [ ] Add all animations (fade-in, slide-in, pulse, shimmer)
- [ ] Implement responsive breakpoints
- [ ] Add keyboard shortcuts
- [ ] Add `prefers-reduced-motion` support
- [ ] Run accessibility audit
- [ ] Write unit tests for all state services
- [ ] Write integration tests for ApiService (preserve security tests)
- [ ] Build and verify production bundle

---

## Appendix A: API Response to UI Mapping

| API Field | UI Display Location | Rendering |
|-----------|-------------------|-----------|
| `answer` | Turn card / Analysis page / Report full text | Markdown-ish prose, streamed |
| `analysis_type` | Turn card badge / Analysis type badge | Colored pill badge |
| `confidence` | ConfidenceMeter / ConfidenceRing | Animated bar or SVG ring |
| `datasets_used` | Sources section | List with file icons |
| `calculations_performed` | Calculations section | Monospace list |
| `key_findings` | Findings section | Bullet list with icons |
| `sources` | Sources section | List with source type icons |
| `visualisations` | Chat chart gallery | Filenames (chat) or images (analysis) |
| `tools_used` | Tools section | Chip list with tool icons |
| `warnings` | Toast notification | Amber toast |
| `source_labels` | Turn card metadata | Small text labels |
| `plan` (analyse) | Analysis plan viewer | Numbered step list |
| `chart_images` (report) | Report chart gallery | Inline `<img>` from base64 |
| `layers.facts` | Report detail — Facts section | Bullet list |
| `layers.calculated_findings` | Report detail — Findings section | Bullet list |
| `layers.interpretations` | Report detail — Interpretations section | Bullet list |
| `layers.recommendations` | Report detail — Recommendations section | Bullet list |
| `content` (report) | Report detail — Full text (collapsible) | Pre-formatted text |
| `summary` (report) | Report header stats | Row/column count, key metrics |

## Appendix B: Sample Prompt Library

Quick-start prompts for the Dashboard and Chat composer:

```
Dataset Analysis:
  - "What was total revenue?"
  - "Which region earned the most?"
  - "Show me revenue by product"
  - "What is the monthly revenue trend?"
  - "Which product has the highest profit margin?"
  - "How many missing values are there?"
  - "What is the average order value?"
  - "Group revenue by region and product"

Database Queries:
  - "List all tables in the database"
  - "Show me the schema of the sales table"
  - "What are the top 10 customers by total spend?"
  - "Count the number of orders per month"

Document Retrieval:
  - "What does the strategy document say?"
  - "Summarize the roadmap document"
  - "What are the key recommendations in the docs?"
  - "Find information about Q3 targets"

Visualisation:
  - "Show revenue as a bar chart by product"
  - "Plot monthly revenue over time"
  - "Create a scatter plot of revenue vs quantity"
  - "Show the distribution of revenue"

General:
  - "What datasets are available?"
  - "What documents are indexed?"
  - "How does the analysis engine work?"
  - "What tools are available?"
```

---

*End of specification. The developer agent shall implement everything described herein.*
