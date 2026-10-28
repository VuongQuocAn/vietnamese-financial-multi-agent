---
name: Financial Intelligence Workspace
colors:
  surface: '#f8f9ff'
  surface-dim: '#cbdbf5'
  surface-bright: '#f8f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#eff4ff'
  surface-container: '#e5eeff'
  surface-container-high: '#dce9ff'
  surface-container-highest: '#d3e4fe'
  on-surface: '#0b1c30'
  on-surface-variant: '#45464d'
  inverse-surface: '#213145'
  inverse-on-surface: '#eaf1ff'
  outline: '#76777d'
  outline-variant: '#c6c6cd'
  surface-tint: '#565e74'
  primary: '#000000'
  on-primary: '#ffffff'
  primary-container: '#131b2e'
  on-primary-container: '#7c839b'
  inverse-primary: '#bec6e0'
  secondary: '#006a61'
  on-secondary: '#ffffff'
  secondary-container: '#86f2e4'
  on-secondary-container: '#006f66'
  tertiary: '#000000'
  on-tertiary: '#ffffff'
  tertiary-container: '#001d31'
  on-tertiary-container: '#188ace'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dae2fd'
  primary-fixed-dim: '#bec6e0'
  on-primary-fixed: '#131b2e'
  on-primary-fixed-variant: '#3f465c'
  secondary-fixed: '#89f5e7'
  secondary-fixed-dim: '#6bd8cb'
  on-secondary-fixed: '#00201d'
  on-secondary-fixed-variant: '#005049'
  tertiary-fixed: '#cce5ff'
  tertiary-fixed-dim: '#93ccff'
  on-tertiary-fixed: '#001d31'
  on-tertiary-fixed-variant: '#004b73'
  background: '#f8f9ff'
  on-background: '#0b1c30'
  surface-variant: '#d3e4fe'
typography:
  headline-xl:
    fontFamily: Inter
    fontSize: 28px
    fontWeight: '700'
    lineHeight: 36px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Inter
    fontSize: 22px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.015em
  headline-md:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: -0.01em
  title-sm:
    fontFamily: Inter
    fontSize: 15px
    fontWeight: '600'
    lineHeight: 20px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  tabular-data:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 18px
    letterSpacing: -0.01em
  tabular-header:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.04em
  label-xs:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 14px
    letterSpacing: 0.02em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  gutter: 1rem
  margin: 1.5rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-lg: 1rem
  space-xl: 1.5rem
---

## Brand & Style
The design system embodies scientific rigor, absolute auditability, and academic precision. Designed specifically for Vietnamese financial statement analysis (BCTC) and multi-agent AI verification, the interface balances enterprise-grade density with high legibility. 

The aesthetic is Modern Corporate with Technical Realism: structured, distraction-free surfaces, sharp typographic clarity, and subtle contextual depth. Every pixel conveys fiduciary trust, evidentiary tracing, and structural discipline. Visual clutter is eliminated in favor of data-first utility, crisp borders, and unambiguous provenance states that allow researchers and analysts to trace every autonomous agent output directly back to source filing lines.

## Colors
The palette utilizes high-contrast structural darks against clean slate workspaces to provide prolonged readability for intensive numerical analysis.

- **Primary Canvas & Chrome:** `#0f172a` (Slate 900) anchors top navigation and high-level headings, while `#1e293b` (Slate 800) defines active states and structural sidebars.
- **Accents:** `#0d9488` (Teal 600) serves as the primary interactive and AI agent operational indicator. `#0284c7` (Sky 600) powers data hyperlinks, PDF bounding box highlights, and secondary active states.
- **Neutrals & Surfaces:** Background is anchored by `#f8fafc` (Slate 50), with `#ffffff` for elevated data panels and table canvases. Dividers, grid lines, and structural boundaries use a razor-sharp `#e2e8f0` (Slate 200).
- **Semantic Status Signals:**
  - Emerald (`#10b981` / background `#ecfdf5`): Hoàn tất / Đã đối chiếu (Verified / Reconciled).
  - Amber (`#f59e0b` / background `#fffbeb`): Đang xử lý / Cần xác nhận (Processing / Audit Needed).
  - Rose (`#ef4444` / background `#fef2f2`): Lỗi / Chưa khớp (Variance / Discrepancy).
  - Slate (`#64748b` / background `#f1f5f9`): Sắp ra mắt / Dự kiến (Roadmap / M3-M7).

## Typography
Typography is tuned for flawless diacritic rendering in Vietnamese and high-density tabular computation. 

- **Primary Sans (`Inter`):** Applied to UI navigation, form layouts, system messages, and analytical narratives. Features negative tracking on headings for an authoritative, compact footprint.
- **Data & Numeric Code (`JetBrains Mono`):** Applied to financial data cells, line-item reference codes (e.g., MS 110, B01-DN), calculation traces, and provenance confidence scores. All numerical values must enforce `font-feature-settings: 'tnum'` (`tabular-nums`) with strict right-alignment.
- Line heights prioritize compactness without sacrificing legibility during extended multi-column cross-checks.

## Layout & Spacing
Optimized desktop-first for standard high-density financial environments (1440x900 base canvas).

- **Navigation Shell:** 64px collapsed / 240px expanded left sidebar. 48px fixed top context-bar holding stock ticker, enterprise title, filing year, and agent run status.
- **Split-Pane Workspace:** Primary analytical grid uses a persistent or toggleable split ratio (60% normalized BCTC spreadsheet view / 40% dual-panel original PDF evidentiary source and agent verification drawer).
- **Spacing Scale:** Built on a tight 4px structural baseline (`space-xs: 4px`, `space-sm: 8px`, `space-md: 12px`, `space-lg: 16px`, `space-xl: 24px`). High-density data grids reduce row padding to 6px vertical for maximum visible line-item density.

## Elevation & Depth
The design relies on structured surface layering and crisp borders rather than heavy ambient diffusion, maintaining an institutional, paper-like authority.

- **Level 0 (Base Canvas):** `#f8fafc` underlying background.
- **Level 1 (Card & Workspace Panels):** `#ffffff` solid fill with a 1px continuous border (`#e2e8f0`). No drop shadow.
- **Level 2 (Active Table Rows, Splitters & Menus):** `#ffffff` with `0 1px 3px 0 rgba(15, 23, 42, 0.08), 0 1px 2px -1px rgba(15, 23, 42, 0.04)`.
- **Level 3 (Evidence Drawer & Provenance Popovers):** Dynamic overlays with a 1px border (`#cbd5e1`) and shadow `0 10px 15px -3px rgba(15, 23, 42, 0.1), 0 4px 6px -4px rgba(15, 23, 42, 0.05)`.
- **Focus Rings:** Non-offset 2px focus line in Teal (`#0d9488`) at 40% alpha for accessible data entry and navigation.

## Shapes
Soft, precise rounding (`roundedness: 1`):
- Data cells, tabs, split containers, and toolbar buttons employ a clean 4px (`0.25rem`) border radius.
- Cards, structural split panes, and modal containers use 6px–8px (`0.5rem`) radius maximum.
- Status chips, indicator pills, and standard metric tags utilize micro-pill shaping (fully rounded bounds) to contrast visually against the angular, rectangular geometry of financial data tables.

## Components

### 1. Navigation Sidebar & Top App Bar
- **Sidebar:** Slate 900 background (`#0f172a`) with subtle 1px right border (`#1e293b`). Menu items display Vietnamese titles (*Bảng cân đối kế toán, Báo cáo kết quả HĐKD, Lưu chuyển tiền tệ, Thuyết minh BCTC*). Active items take `#1e293b` fill with a 3px teal (`#0d9488`) left border indicator.
- **Top Bar:** 48px fixed bar containing enterprise metadata, ticker search (e.g., `VNM`, `FPT`), fiscal period selector (`Q3/2024`, `Niên độ 2023`), and agent execution controls.

### 2. Financial Statement Tables (B01, B02, B03, B09)
- **Header:** Sticky top, uppercase tracking (`tabular-header`), Slate 100 fill, 1px bottom border.
- **Statement Identifiers:** Badges denoting standard formats: `B01-DN` (Cân đối kế toán), `B02-DN` (Kết quả HĐKD), `B03-DN` (Lưu chuyển tiền tệ), `B09-DN` (Thuyết minh).
- **Data Rows:** Alternating row hovering (`#f1f5f9`). Financial figures strictly right-aligned (`tabular-nums`), negative balances enclosed in standard accounting parentheses `(12.450.000.000)`.

### 3. Split-Pane Document Viewer & Evidence Drawer
- Left canvas renders normalized statement hierarchy; right canvas contains the native PDF viewer with interactive bounding boxes correlating extracted numbers with physical scanned pages.
- Clicking any extracted cell instantly centers the PDF pane onto the exact coordinates and draws an animated teal highlight box around the original source line.

### 4. Semantic Badges & Provenance Tags
- **Đã đối chiếu (Reconciled):** Green pill (`#ecfdf5` text `#047857`) accompanied by a checkmark icon.
- **Cần xác nhận (Flagged Variance):** Amber pill (`#fffbeb` text `#b45309`) indicating math discrepancy or unmapped note.
- **Chưa khớp (Error):** Rose pill (`#fef2f2` text `#b91c1c`) for failing debit/credit parity.
- **Sắp ra mắt (Coming Soon):** Slate pill (`#f1f5f9` text `#475569`) with mono font tag for upcoming research modules (e.g., `M3 - Agentic Valuation`, `M4 - Forensic Auditing`).

### 5. Buttons & Form Elements
- **Primary Buttons:** Solid `#0f172a` fill, white text, 4px border radius. Hover: `#1e293b`.
- **Secondary / Action Buttons:** White fill, 1px border (`#cbd5e1`), text `#1e293b`. Hover: `#f8fafc`.
- **Inputs & Filters:** 32px height, 1px border (`#cbd5e1`), placeholder `#94a3b8`, focus ring in `#0d9488`.