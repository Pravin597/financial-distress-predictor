# Implementation Plan: Company Renaming, AI Speedometer, Currency Selection & Refresh Buttons [COMPLETED]

This plan outlines the design and integration details for adding a company rename option, an AI Distress Speedometer gauge chart, currency selection, and graph refresh buttons.

---

## Technical Approach

### 1. Company Renaming Feature
- **Database (`database.py`)**: Added `rename_company(company_id, user_id, new_name)` to update sqlite database records.
- **Backend Route (`app.py`)**: Added `POST /api/companies/<int:company_id>/rename` endpoint.
- **Frontend UI (`templates/index.html`)**: Added a pencil icon `` and modal `rename-modal` to rename companies.

### 2. AI Distress Speedometer Gauge Chart
- **Sectors / Ranges**:
  - **Safe (Green)**: first half `[0, 50]`
  - **Ok Little Risk (Yellow)**: middle `[50, 75]`
  - **Warning (Red)**: last half `[75, 100]`
- **Status-Aligned Pointer Logic**: Pointer value, colors, and text label map directly on the basis of result status.
  - `STABLE` (Healthy) $\rightarrow$ Green zone `[0, 50]`, green bar (`#10b981`), "Safe" label.
  - `WARNING` (Liquidity/Decline) $\rightarrow$ Yellow zone `[50, 75]`, yellow bar (`#f59e0b`), "Ok Little Risk" label.
  - `CRITICAL` (Insolvency) $\rightarrow$ Red zone `[75, 100]`, red bar (`#ef4444`), "Warning (Critical Risk)" label.

### 3. Currency Selection Dropdown & Database Persistence
- **Wizard Setup Input**: Added a select element `#wizard-currency` inside the Setup Portfolio Wizard.
- **Database Migrations**: Appended a `currency TEXT DEFAULT '$'` column to the `companies` table inside `database.py`. This ensures each company maintains its own specific currency symbol.
- **API Endpoint**: Added `POST /api/companies/<int:company_id>/currency` in `app.py` to persist selected currencies to the SQLite database.
- **Selector UI**: Placed a select element `#currency-select` in the Step 1 Records header card. Selecting a currency dynamically updates the database for the active company.
- **Formatting Updates**:
  - Dynamically updates CRUD form labels, wizard prompt labels, month-by-month record tables, prediction tables, and summary texts.
  - Passes tick prefix formatting (`tickprefix`) to Plotly line chart y-axis layout and custom hover templates to show the selected currency symbol.

### 4. Graph Refresh Buttons
- **UI Elements**: Inserted a button `.refresh-btn` containing a `` emoji inside the headers of both Step 2 graph cards.
- **Animations**: Added `@keyframes spin` and a `.spinning` CSS class to spin the icon for 800ms when clicked.
- **Behavior**: Calls `runForecast(selectedCompanyId)` to pull fresh records, run AI calculations on the server, and update the layout dynamically.

---

## Verification Results

### Automated Verification
- Ran database test script `verify_currency_persistence.py` confirming SQLite migrations, table columns, default values, update endpoints, and retrieval logic are fully operational.
- Verified that toggling currencies updates all UI numbers, and clicking refresh buttons triggers forecast re-calculations successfully.
