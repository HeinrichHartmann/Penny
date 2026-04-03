# ADR-001: Penny Application Design

## Status
Accepted

## Context

### Provenance

Penny builds upon two existing, proven components that have been developed and refined over time:

**1. Bank-csv-2-db** - CSV Export Processing
- Transforms Comdirect bank CSV exports into standardized Parquet format
- Handles multiple account types (Girokonto, Visa, Wertpapiere, Tagesgeld)
- Supports both private and shared accounts
- Includes PDF transaction extraction for manual entries
- Tech stack: Python, pandas, pyarrow

**2. FinanceAnalysis** - Transaction Classification & Reporting
- Classifies transactions using 100+ rule-based conditions
- Normalizes merchant names via 150+ alias rules
- Neutralizes internal transfers (Visa↔Giro settlements, inter-account movements)
- Exports to SQLite for queryable reporting
- Serves interactive dashboard via FastAPI + Vue.js + ECharts
- Features: category tree explorer, transaction search, Sankey cash-flow diagrams, time-series breakouts

Both components work well in their current form but require command-line operation and technical knowledge to run.

### Goal

Create a user-friendly desktop application targeting the **Accountant Persona**:
- Non-technical users (spouse, family accountant)
- No command-line or developer tool experience
- Expects standard desktop application behavior
- Needs clear visual feedback and intuitive workflows

### Naming

**Penny** - Named after the character from The Big Bang Theory.

Future components may follow the theme:
- **Sheldon** - Classification engine (rigid, rule-based)
- **Howard** - Import system (engineering)
- **Leonard** - Reports (sensible overview)

CLI command: `penny`

## Decision

### Technology Choices

**Frontend: Web Technologies (Retained)**
- Vue.js + ECharts dashboard has proven effective
- Rich visualization capabilities
- Responsive and interactive

**Backend: Python (Retained)**
- Data analysis ecosystem (pandas, pyarrow) is native to Python
- Existing classification logic is mature and well-tested
- No compelling reason to rewrite working code

### Installation Requirements

**Core Requirement: Self-Contained Application**

The application MUST be installable without external dependencies:

1. **Packaging Format**: macOS DMG with drag-and-drop installation
   - User drags app to Applications folder
   - No Homebrew, no pip, no Terminal commands
   - Standard macOS application experience

2. **Bundled Runtime**: Embedded Python interpreter
   - All Python dependencies packaged within the app bundle
   - No system Python dependency
   - Isolated from user's environment

3. **Single Executable**: One `.app` bundle contains everything
   - Backend server
   - Frontend assets
   - Python runtime + libraries
   - Data processing pipeline

4. **Zero Configuration**: Works immediately after install
   - No PATH setup
   - No environment variables
   - No config file editing

### Packaging Solution: Briefcase + Toga

**Chosen Stack:**
- **GUI Framework**: Toga (BeeWare's cross-platform native toolkit)
- **Packager**: Briefcase (creates proper macOS `.app` bundles and DMGs)
- **Web Server**: FastAPI + Uvicorn (embedded, serves dashboard)
- **Dashboard**: Opens in system default browser

**Architecture:**
```
Penny.app launches
    → Native Toga window appears ("Open Dashboard" button)
    → FastAPI server starts on localhost:8000
    → Browser auto-opens to dashboard
    → User interacts with Vue.js + ECharts UI
```

**Why Briefcase over PyInstaller:**
- Creates proper macOS `.app` bundles with correct structure (Info.plist, icons, code signing)
- Built-in DMG creation for distribution
- Part of BeeWare ecosystem - designed to work seamlessly with Toga
- PyInstaller requires more manual setup for macOS app bundle structure

**Why Toga over alternatives:**
- Native look and feel on macOS (and Linux)
- Pure Python - no additional toolchain (vs Tauri/Rust, Electron/Node)
- Briefcase-native - guaranteed compatibility with packaging
- Cross-platform potential (Linux support)

**Alternatives Evaluated:**

| Approach | Outcome |
|----------|---------|
| **rumps** (menu bar app) | Failed: PyObjC wheels not available in Briefcase's bundled Python environment |
| **tkinter** | Failed: UV's standalone Python lacks tcl/tk bindings |
| **Electron** | Rejected: 120MB+ bundle size, Node.js complexity |
| **Tauri** | Rejected: Rust toolchain, Python embedding challenges |

**Result:**
- Bundle size: ~33 MB (acceptable)
- Build command: `make app`
- Output: `dist/Penny-0.1.0.dmg`

## Consequences

- Users can install Penny like any standard macOS application
- Development must include packaging/distribution workflow
- Updates may require re-download of full DMG (no auto-update initially)
- Testing must cover fresh macOS installs without developer tools
