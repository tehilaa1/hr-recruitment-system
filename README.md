# HireTrack — HR Recruitment & Management System

An internal HR web application, Hebrew-first (RTL), for managing recruitment pipelines and HR workflows. It covers job postings, AI-assisted CV intake, candidate status tracking, a global candidate search, Excel exports, Outlook email/calendar drafts, and a maternity leave tracking module with Outlook and Microsoft Teams announcement templates.

The system is built as independent **modules** behind a single home dashboard, so new HR areas (e.g. an annual budget module, planned for a later phase) can be added without touching existing ones.

Access is restricted to **authorized users only**: users sign in with Firebase Authentication (email/password), and every API request is verified by the backend against a Firestore allow-list with **role-based permissions** (`admin` / `editor`).

---

## Table of contents

1. [Tech stack](#tech-stack)
2. [Architecture overview](#architecture-overview)
3. [Core modules & features](#core-modules--features)
4. [Data model (Firestore)](#data-model-firestore)
5. [API reference](#api-reference)
6. [Project structure](#project-structure)
7. [Getting started (local development)](#getting-started-local-development)
8. [Configuration reference](#configuration-reference)
9. [Testing](#testing)
10. [Deployment & environment](#deployment--environment)
11. [Security & known limitations](#security--known-limitations)
12. [Extending the system](#extending-the-system)

---

## Tech stack

| Layer | Technology |
|---|---|
| **Frontend** | React 18, Vite 5, React Router 6, Tailwind CSS 3, Axios, Lucide icons, Firebase JS SDK (Auth only) |
| **Backend** | Python 3.11+ (developed on 3.14), FastAPI, Uvicorn, Pydantic v2 / pydantic-settings |
| **Database** | Google Cloud **Firestore** (via `firebase-admin`, server-side only) |
| **Authentication** | **Firebase Authentication** (email/password) + ID-token verification in FastAPI |
| **AI** | Google **Gemini** (`google-genai`) for parsing CVs (PDF, images, Word) into structured candidate data |
| **File processing** | `openpyxl` (Excel export), `python-docx` (Word CV text extraction) |
| **Integrations** | Outlook on the web (mail & calendar deep links), Microsoft Teams (copy-and-paste announcements + channel link) |

**Firebase scope:** **Firestore** (data) and **Firebase Authentication** (sign-in). Firebase Storage is *not* used. The browser uses Firebase **only to sign in** and obtain an ID token; it never reads or writes Firestore directly. All data access goes through the FastAPI backend using a service-account key. Uploaded CV files are sent to Gemini for parsing and **are not stored**. Only the extracted fields are saved.

---

## Architecture overview

```
                  sign in (email/password)
   ┌──────────────────────────────────────▶ Firebase Authentication
   │            ◀── ID token ──────────────
   │
┌──┴─────────────────────────┐  HTTP/JSON + Bearer ID token   ┌───────────────────────────────┐
│  React SPA (Vite, :5173)   │ ─────────────────────────────▶ │  FastAPI (Uvicorn, :8000)     │
│                            │                                │                               │
│  /login       Login        │                                │  security.py  token verify +  │
│  /            Home         │                                │               role checks     │
│  /jobs        Jobs module  │                                │  routers/  jobs, candidates,  │
│  /jobs/:id    Job details  │                                │            search, maternity, │
│  /maternity   Maternity    │                                │            users (+ /auth/me) │
│  /admin/users Users (admin)│                                │  services/ firestore, gemini, │
│                            │                                │            auth, export, ...  │
└─────────────┬──────────────┘                                └───────┬───────────────┬───────┘
              │ opens deep links in a new tab                         │               │
              ▼                                                       ▼               ▼
   Outlook on the web (mail / calendar)                    Firestore (firebase-admin)  Gemini API
   Microsoft Teams (channel link)
```

Key architectural points:

- **Thin client, server-owned data.** The React app is a pure API consumer. Firestore credentials and the Gemini key live only on the backend.
- **Authentication in the browser, authorization on the server.** Firebase Auth proves *who* the user is; the backend decides *whether they may enter* (Firestore `users` allow-list) and *what they may do* (role). See [Authentication & permissions](#5-authentication--permissions).
- **Layered backend.** `routers/` hold HTTP concerns (validation, status codes), `services/` hold logic and I/O, `models/` hold Pydantic schemas. Blocking Firestore/Gemini calls run in `asyncio.to_thread` so the event loop stays responsive.
- **No server-side email/Teams sending.** Outlook and Teams integrations generate **drafts and deep links** that open in the user's own Outlook/Teams session. Nothing is sent without the user clicking *Send*, and no Microsoft credentials or Graph permissions are required.
- **Config-driven UI.** Module cards/navigation (`constants/modules.js`), recruitment statuses (`constants/statuses.js`) and maternity table columns (`constants/maternityColumns.js`) are declared once and rendered generically.
- **Backend ↔ frontend contract checks.** Statuses and maternity fields are defined on both sides; tests in `backend/tests/` fail if they drift apart.

---

## Core modules & features

### 1. Home dashboard & modular navigation
- Landing page (`/`) with a card per module: **Jobs & Candidates** and **Maternity Leave Tracking**.
- A persistent top navbar with module tabs; the logo returns home.
- Modules are declared in `frontend/src/constants/modules.js`. That one list drives both the home cards and the navbar tabs.

### 2. Jobs & candidates management (`/jobs`)
- **Jobs:** create, list and delete job postings with interviewers, interviewer emails, interview location and interview type (`יחידני` individual / `מרוכז` group).
- **AI CV intake:** drag-and-drop upload of PDF, PNG/JPG/WEBP and DOCX files. Gemini extracts name, phone, email, address, profession and years of experience. A configurable model fallback chain with retries handles overload/unavailable errors.
- **Duplicate prevention:** on upload, candidates are matched against the job's existing candidates (and the rest of the batch) by **normalized email or phone** (e.g. `+972-50-123-4567` = `0501234567`). Duplicates are skipped and reported in amber.
- **Recruitment statuses:** `לא טופל` · `לא עונה` · `נשלח זימון` · `לשלוח זימון` · `גויס/ה` (Hired) · `שלילי` (Rejected) · `לא רלוונטי`. Status changes are optimistic and **roll back** if the server rejects them.
- **Outlook integrations** (per candidate, based on status):
  - `שלילי` → **"מייל דחייה"** opens a pre-filled rejection email (editable before sending).
  - `לשלוח זימון` → **"זימון ב-Outlook"** opens a new calendar event with all interviewers + the candidate as attendees and the interview address in the location and notes. **Date/time are intentionally left empty** for the user to choose.
- **Excel export:** real `.xlsx` (RTL sheet, styled header, frozen top row), Hebrew filename via RFC 5987 `filename*`, phone numbers stored as text, tolerant of missing/malformed fields.
- **Global candidate search** (navbar, inside the jobs module): search across **all jobs** by name (either order), email or phone (any format). Records sharing an email/phone are merged into one person. Selecting a result opens a **candidate profile** with contact details and every position applied to, with status and date.
- **Referred by (הובא על ידי – חבר מביא חבר):** recorded **per application** (and per talent-pool entry), so the same person can be referred to different jobs by different employees. Set it in the manual-add form, once for a whole CV upload batch, or inline in the job / talent-pool tables (autocomplete from names used before). Assigning a pool candidate to a job keeps the pool's referrer. Included in the candidates Excel export.
- **All candidates (`/candidates`):** every person once — job applications and talent-pool entries merged by normalized email or phone — with filters (source, referrer). The profile shows the full **application history**: job, application date, current status in that job and the referrer of each application. The list is computed on each request from the job candidates and the talent pool (the sources of truth), so there is no second copy that can drift; no top-level `candidates` collection is used, since job candidates are read with a `candidates` collection-group query.

### 3. Maternity leave tracking (`/maternity`)
- **Dynamic table** generated from a column config. Initial columns: name, phone, company email, birth date, estimated return date, gift delivery address, delivery contact (name + phone), attendance-updated (yes/no), notes.
- Add/edit via a generated form (with date validation), delete with confirmation, quick text filter.
- **Attendance toggle:** click the yes/no badge in the table to flip it (optimistic, with rollback).
- **Summary cards:** total on leave, not yet updated in attendance, returning in the next 30 days.
- **"שליחת עדכונים" (Send updates) per employee:**
  - **Outlook summary email:** a structured summary (birth date, return date, contact info, gift address, delivery contact, notes) addressed to the **preset recipient list**, editable in-app and opened as an Outlook draft.
  - **Teams announcement:** an editable congratulations message with *Copy* and *Copy & open channel* (if a channel link is configured).
- **Excel export (privacy-filtered):** name, phone, company email, birth date, expected return date, attendance-updated and notes only. The gift address and delivery contact (name + phone) are **never exported**; the columns are an explicit allow-list in `export_service.py`, checked by `tests/test_exports.py`.

### Annual budget: holiday expenses (`/budgets`)
- Click a holiday / event to open its **itemized expenses**: item or supplier, quantity, unit price, total (auto-calculated from quantity × unit price, or entered directly), payment status (**שולם** / **ישולם בהעברה**), notes, an optional invoice number / link, and an **uploaded invoice file**.
- **Invoice files (PDF, PNG, JPG, up to 5 MB):** picked from the computer in the expense form, or attached straight from the table row; opened in a new browser tab. Files are stored in Firestore itself (no Storage bucket needed): raw bytes split into ~900 KB chunk documents under `.../expenses/{id}/invoice_chunks`, so the expenses list never downloads them. The real type is checked from the file's content, not its name, and files are deleted along with their expense, holiday or year.
- Once a holiday has expense items, its *actual spent* is their sum (kept in sync by the backend on every change).
- **Excel export** per holiday: RTL sheet with a title, the items, and totals (total, paid, pending, allocated budget, remaining).

### 4. Preset settings & persistence
- Maternity notification settings (**fixed recipient emails** and **Teams channel URL**) are edited from the module's *הגדרות התראות* dialog and persisted in Firestore at `settings/maternity`.
- Emails are validated and de-duplicated server-side; the Teams URL must be `https://`.

### 5. Authentication & permissions
- **Login screen** (`/login`): email/password via Firebase Auth, Hebrew error messages, and *שכחתי סיסמה* (Firebase password-reset email).
- **Protected routes:** every page except `/login` requires an authorized user. Unauthenticated visitors are redirected to `/login` and returned to the page they wanted after signing in. `/admin/users` additionally requires the `admin` role.
- **Roles:**

  | Role | Label | Access |
  |---|---|---|
  | `admin` | מנהל/ת מערכת | Everything + user management |
  | `editor` | עורך/ת | Full read/write access to jobs, candidates and maternity data |

- **User management** (`/admin/users`, from the user menu in the navbar). Admins can:
  - **Add** an authorized user (email, display name, role). The backend creates the Firebase Auth account with a random password, and the app sends the user a Firebase "set your password" email.
  - **Change roles** and **send password-reset emails**.
  - **Remove access**, which deletes the user record *and* their login account.
- **Safeguards:** admins can't change their own role or delete themselves, and the last remaining admin can't be demoted or removed.
- **How a request is authorized** (`backend/app/security.py`):
  1. The frontend attaches `Authorization: Bearer <Firebase ID token>` to every API call (Axios interceptor; tokens refresh automatically).
  2. FastAPI verifies the token with the Firebase Admin SDK (signature, expiry, project) → **401** if missing or invalid.
  3. It loads `users/{email}`. The record must exist, have a valid role, and its **`uid` must match the token's uid** → otherwise **403**. The uid binding means that registering the same email address elsewhere doesn't grant access.
  4. Role requirements are checked per router (`require_member` for data, `require_admin` for `/api/users`) → **403** if insufficient.
- After sign-in, the frontend calls `/api/auth/me`. If the user isn't on the allow-list, the app shows *"אין הרשאת גישה"* and signs them out. Any later 401 signs the user out automatically.
- **First admin:** created from the server with `backend/scripts/create_admin.py` (see [Getting started](#getting-started-local-development)). There is no self-registration.

---

## Data model (Firestore)

```
jobs/{jobId}
  job_title, description, interviewers[], interviewer_emails[],
  interview_location, interview_type ("יחידני" | "מרוכז"), created_at
  └── candidates/{candidateId}          (subcollection)
        full_name, family_name, phone, email, address, profession,
        years_of_experience, recruitment_status, file_name, job_id, created_at

maternity_leaves/{recordId}
  name, phone, company_email, birth_date ("YYYY-MM-DD"), expected_return_date ("YYYY-MM-DD"),
  gift_address, delivery_contact_name, delivery_contact_phone,
  attendance_updated (bool), notes, created_at, updated_at

settings/maternity
  notify_recipients[], teams_channel_url

users/{email}                          (document id = lower-cased email)
  display_name, role ("admin" | "editor"), uid (Firebase Auth uid),
  created_at, created_by
```

- Dates without time are stored as ISO `YYYY-MM-DD` strings (Firestore has no date-only type).
- Deleting a job deletes its candidates subcollection.
- Global search uses a **collection-group query** on `candidates`, which needs no composite index.

---

## API reference

Interactive docs are served at **`/docs`** (Swagger) and **`/redoc`** when the backend is running.

**All endpoints except `/health` require `Authorization: Bearer <Firebase ID token>`.** Data endpoints accept any authorized user (`admin` or `editor`); `/api/users` is admin-only.

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Health check (public) |
| GET | `/api/auth/me` | Current user's profile and role |
| GET / POST | `/api/users` | List users / add an authorized user (creates the login account) **(admin)** |
| PATCH / DELETE | `/api/users/{email}` | Change role or name / remove user and login account **(admin)** |
| GET / POST | `/api/jobs` | List jobs (with candidate counts) / create job |
| GET / PUT / DELETE | `/api/jobs/{job_id}` | Get / update / delete job (delete cascades to candidates) |
| GET | `/api/jobs/{job_id}/export-excel` | Download candidates as `.xlsx` |
| GET | `/api/jobs/{job_id}/candidates` | List candidates of a job |
| POST | `/api/jobs/{job_id}/candidates/upload` | Upload CV files (multipart `files`); AI parse + dedup |
| GET / PATCH / DELETE | `/api/jobs/{job_id}/candidates/{candidate_id}` | Get / update / delete candidate |
| PATCH | `/api/jobs/{job_id}/candidates/{candidate_id}/status` | Update recruitment status |
| GET | `/api/candidates/search?q=…&limit=20` | Global search across all jobs (merged profiles) |
| GET | `/api/candidates` | Every person (applications + talent pool merged), with application history and referrers |
| GET | `/api/candidates/referrers` | Referrer names used so far, most used first |
| PATCH | `/api/talent-pool/{candidate_id}` | Update a talent-pool entry (`referred_by`) |
| GET / POST | `/api/maternity` | List / create maternity records |
| PATCH / DELETE | `/api/maternity/{record_id}` | Partial update / delete a record |
| GET / PUT | `/api/maternity/settings` | Read / save notification settings |
| GET | `/api/maternity/export-excel` | Download records as `.xlsx` (no gift address / delivery contact) |
| GET / POST | `/api/budgets/{year}/events/{event_id}/expenses` | List / add expense items of a holiday |
| PATCH / DELETE | `/api/budgets/{year}/events/{event_id}/expenses/{expense_id}` | Update / delete an expense item |
| PUT / GET / DELETE | `/api/budgets/{year}/events/{event_id}/expenses/{expense_id}/invoice` | Upload (multipart `file`) / view / remove the invoice file |
| GET | `/api/budgets/{year}/events/{event_id}/export-excel` | Download the holiday's expenses as `.xlsx` |

---

## Project structure

```
hr-recruitment-system/
├── README.md
├── backend/
│   ├── requirements.txt
│   ├── .env.example                 # template for the env file
│   ├── env.  /  .env                # local secrets (git-ignored)
│   ├── firebase_credentials.json    # Firestore service-account key (git-ignored)
│   ├── app/
│   │   ├── main.py                  # FastAPI app, CORS, router registration + auth requirements
│   │   ├── config.py                # Settings (pydantic-settings, reads env./.env)
│   │   ├── dependencies.py          # Cached Firestore / Gemini service providers
│   │   ├── security.py              # Token verification, CurrentUser, require_member / require_admin
│   │   ├── models/
│   │   │   ├── job.py               # Job schemas
│   │   │   ├── candidate.py         # Candidate schemas, VALID_STATUSES, search profile models
│   │   │   ├── maternity.py         # Maternity record + settings schemas
│   │   │   └── user.py              # User schemas, VALID_ROLES
│   │   ├── routers/
│   │   │   ├── jobs.py              # Jobs CRUD + Excel export
│   │   │   ├── candidates.py        # Candidate CRUD, CV upload, status updates
│   │   │   ├── search.py            # Global candidate search
│   │   │   ├── maternity.py         # Maternity CRUD + settings
│   │   │   └── users.py             # /api/auth/me + admin user management
│   │   └── services/
│   │       ├── firestore_service.py         # All Firestore access
│   │       ├── auth_service.py              # Firebase Auth admin ops (verify token, create/delete accounts)
│   │       ├── gemini_service.py            # CV parsing with model fallback/retries
│   │       ├── export_service.py            # .xlsx generation
│   │       ├── dedup_service.py             # Email/phone normalization + duplicate detection
│   │       └── candidate_search_service.py  # Matching + merging records into people
│   ├── scripts/
│   │   └── create_admin.py          # Bootstrap / recover an admin user (server-side)
│   └── tests/
│       ├── test_status_sync.py              # statuses: backend ↔ frontend
│       ├── test_roles_sync.py               # user roles: backend ↔ frontend
│       └── test_maternity_fields_sync.py    # maternity fields: backend ↔ frontend
└── frontend/
    ├── index.html                   # lang="he" dir="rtl", Rubik font
    ├── .env.example                 # Firebase web config + optional settings
    ├── package.json, vite.config.js, tailwind.config.js, postcss.config.js
    └── src/
        ├── main.jsx, App.jsx        # Entry + routes (public /login, protected the rest)
        ├── firebase.js              # Firebase app + Auth init from VITE_FIREBASE_* env
        ├── api/client.js            # Axios client (auto Bearer token, 401 → sign out) + all API groups
        ├── auth/
        │   ├── AuthContext.jsx      # Auth state, /api/auth/me check, login/logout/reset
        │   └── RequireAuth.jsx      # Route guard (optionally by role)
        ├── constants/
        │   ├── modules.js           # HR modules (home cards + navbar tabs)
        │   ├── roles.js             # User roles + labels/badge styles
        │   ├── statuses.js          # Recruitment statuses + badge styles
        │   └── maternityColumns.js  # Maternity table/form column config + helpers
        ├── utils/
        │   ├── outlook.js           # Outlook mail/calendar deep-link builders
        │   └── maternityTemplates.js# Summary email + Teams message templates, clipboard
        ├── pages/
        │   ├── Login.jsx            # Email/password sign-in + password reset
        │   ├── Home.jsx             # Module selection dashboard
        │   ├── JobsDashboard.jsx    # Jobs list + stats
        │   ├── JobDetails.jsx       # Job header, export, upload, candidates table
        │   ├── MaternityLeave.jsx   # Maternity table, stats, dialogs
        │   └── UserManagement.jsx   # Admin: authorized users and roles
        └── components/
            ├── Navbar.jsx, UserMenu.jsx, RoleBadge.jsx
            ├── GlobalSearch.jsx, CandidateProfileModal.jsx
            ├── CandidatesTable.jsx, StatusSelect.jsx, StatusBadge.jsx
            ├── UploadBox.jsx, JobCard.jsx, CreateJobModal.jsx, Modal.jsx
            └── maternity/
                ├── MaternityFormModal.jsx
                ├── MaternityActionsModal.jsx
                └── MaternitySettingsModal.jsx
```

---

## Getting started (local development)

### Prerequisites
- **Python 3.11+** and **Node.js 18+** (developed with Python 3.14 and Node 24)
- A **Firebase project** with **Firestore** enabled, and a **service-account key** (Firebase Console → Project settings → Service accounts → *Generate new private key*)
- A **Gemini API key** (Google AI Studio)

### 0. One-time Firebase Authentication setup (Firebase Console)
1. **Authentication → Get started → Sign-in method → Email/Password → Enable.**
2. *Recommended:* **Authentication → Settings → User actions → turn off "Enable create (sign-up)"**, so accounts can only be created by admins through the app.
3. **Project settings → General → Your apps → Add app → Web (`</>`)**, then register it and keep the config values (`apiKey`, `authDomain`, `projectId`, `appId`) for the frontend `.env`.
4. *Recommended:* **Firestore Database → Rules**: deny all direct client access (`allow read, write: if false;`). The backend's Admin SDK isn't affected by rules, and the browser never accesses Firestore directly.

`localhost` is an authorized domain by default. For production, add your domain under **Authentication → Settings → Authorized domains**.

### 1. Backend (FastAPI)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env                 # then edit .env and set GEMINI_API_KEY
# place the Firebase service-account key at backend/firebase_credentials.json

python -m uvicorn app.main:app --reload --port 8000
```

- API: http://localhost:8000 · Swagger docs: http://localhost:8000/docs
- If port 8000 is busy: `kill -9 $(lsof -t -i:8000)` (macOS/Linux). Check what is running there first.

**Create the first admin** (once, with the venv active, from `backend/`):

```bash
python scripts/create_admin.py you@company.com --name "Your Name"
```

This creates the Firebase Auth account (it prompts for a password) and the `users/{email}` record with role `admin`. If an account with that email already exists, it asks before linking it. The same script recovers admin access if it's ever lost.

### 2. Frontend (Vite)

```bash
cd frontend
npm install
cp .env.example .env                 # then fill in the Firebase web app values
npm run dev
```

- App: http://localhost:5173 → sign in at `/login` with the admin you created. Add more users from the user menu → *ניהול משתמשים*.
- Vite reads `.env` only at startup, so **restart `npm run dev` after editing it**. Without the Firebase values, the login page shows a "Firebase לא מוגדר" (Firebase not configured) notice.
- The frontend must run on an origin listed in the backend's `CORS_ORIGINS` (default: `localhost:5173` and `localhost:3000`). If Vite falls back to another port because 5173 is taken, API calls will fail with CORS errors.

---

## Configuration reference

### Backend (`backend/.env` or `backend/env.`)

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | (required) | Google Gemini API key |
| `GOOGLE_APPLICATION_CREDENTIALS` | — | Path to Firebase service-account JSON (takes precedence) |
| `FIREBASE_CREDENTIALS_PATH` | `firebase_credentials.json` | Fallback credentials path |
| `GEMINI_MODEL` | see `config.py` | Primary Gemini model |
| `GEMINI_FALLBACK_MODELS` | see `config.py` | JSON list of models tried on 503/404 (`[]` disables) |
| `GEMINI_RETRIES_PER_MODEL` | `2` | Retries per model before falling back |
| `CORS_ORIGINS` | `["http://localhost:5173","http://localhost:3000"]` | Allowed frontend origins (JSON list) |

### Frontend (`frontend/.env`, template: `frontend/.env.example`)

| Variable | Default | Description |
|---|---|---|
| `VITE_FIREBASE_API_KEY` | (required) | Firebase web app config |
| `VITE_FIREBASE_AUTH_DOMAIN` | (required) | e.g. `<project-id>.firebaseapp.com` |
| `VITE_FIREBASE_PROJECT_ID` | (required) | Firebase project ID |
| `VITE_FIREBASE_APP_ID` | recommended | Firebase web app ID |
| `VITE_API_BASE_URL` | `http://localhost:8000` | Backend base URL |
| `VITE_OUTLOOK_BASE_URL` | `https://outlook.office.com` | Outlook on the web host. Use `https://outlook.live.com` for personal Outlook.com accounts |

The Firebase web config values are **public identifiers, not secrets**. Security is enforced by the backend's token verification and allow-list.

---

## Testing

The backend includes contract tests that keep shared definitions in sync between the backend and frontend:

```bash
cd backend
python tests/test_status_sync.py              # or: python -m pytest tests/  (requires pytest)
python tests/test_roles_sync.py
python tests/test_maternity_fields_sync.py
python tests/test_budgets.py
python tests/test_exports.py
python tests/test_invoices.py
python tests/test_referrals.py
```

- `test_status_sync.py`: the backend `VALID_STATUSES` equals the frontend `RECRUITMENT_STATUSES` (same order), every status has a badge style, and unknown statuses are rejected.
- `test_roles_sync.py`: the backend `VALID_ROLES` equals the frontend `ROLES` (same order).
- `test_maternity_fields_sync.py`: the maternity Pydantic model fields equal the data fields in `maternityColumns.js`.

There is currently no frontend test suite.

---

## Deployment & environment

> *Placeholder: no deployment target is configured yet. The notes below describe how the app is structured for deployment.*

The app deploys as **two independent units**:

1. **Frontend: static SPA.** `npm run build` produces `frontend/dist/`, which can be hosted on any static host (Firebase Hosting, Netlify, Vercel, S3 + CloudFront, Nginx). Because it uses client-side routing, configure the host to **rewrite all paths to `index.html`**.
2. **Backend: stateless ASGI service.** Run with Uvicorn (or Gunicorn + Uvicorn workers) in a container or on a managed platform (e.g. Google Cloud Run, which pairs naturally with Firestore). The process is stateless; all state lives in Firestore.

Before deploying:
- [ ] Set `VITE_API_BASE_URL` and the `VITE_FIREBASE_*` values at **build time** for the production frontend.
- [ ] Set `CORS_ORIGINS` to the production frontend origin.
- [ ] Add the production domain to **Firebase Authentication → Authorized domains**.
- [ ] Provide `GEMINI_API_KEY` and Firebase credentials through the platform's **secret manager**, not files in the image. On Google Cloud, prefer the runtime service account (Application Default Credentials). The service account needs both Firestore and Firebase Auth admin permissions.
- [ ] Lock down Firestore security rules to deny all client access (the backend's Admin SDK bypasses rules, so `allow read, write: if false;` is appropriate while the frontend doesn't access Firestore directly).
- [ ] Disable client self sign-up in Firebase Authentication (see setup step 0.2).
- [ ] Serve both frontend and API over **HTTPS** (ID tokens are bearer credentials).

---

## Security & known limitations

- **Authentication & authorization** are enforced server-side on every endpoint except `/health` (see [Authentication & permissions](#5-authentication--permissions)). Hiding a button in the UI is never relied on for security.
- **Two roles only.** `editor` has full data access, so there is no read-only role yet (see [Extending](#extending-the-system)).
- **Role changes take effect on the user's next request**, because the role is read from Firestore on every call. Removing a user deletes their login account, so access ends immediately.
- **Per-request Firestore read:** each authenticated request reads `users/{email}` once. That's negligible at this scale; add a short TTL cache if traffic grows.
- **Firestore rules** must be configured in the Firebase Console (deny-all recommended). Rules aren't managed in this repository.
- **Secrets** (`firebase_credentials.json`, `env.`/`.env`) are git-ignored. Never commit them. The personal data stored (names, phones, emails, addresses, birth dates) makes protecting the service-account key critical.
- **Global search** reads all candidates and filters in Python, because Firestore has no substring search. This is fine for thousands of records. Beyond that, use a search index such as Algolia, Typesense or Meilisearch.
- **Duplicate detection** runs after Gemini parsing (it needs the extracted email/phone), so a duplicate still costs one AI call. Simultaneous uploads to the same job are not transactionally de-duplicated.
- **Legacy `.doc` files** are accepted by the upload endpoint, but `python-docx` only reads `.docx`, so `.doc` parsing will fail and be reported as an upload error.
- **Outlook deep links** target Outlook on the web. The desktop Outlook client is not opened directly.
- **Teams** messages are copy-and-paste. Automatic posting would require a Teams Workflows (Power Automate) webhook or Microsoft Graph permissions.

---

## Extending the system

| Task | Where |
|---|---|
| **Add a new HR module** (e.g. annual budget) | Add an entry to `frontend/src/constants/modules.js`, a page + route in `App.jsx`, and a router in `backend/app/routers/` registered in `main.py` |
| **Add a recruitment status** | `VALID_STATUSES` in `backend/app/models/candidate.py` **and** `RECRUITMENT_STATUSES` + `STATUS_STYLES` in `frontend/src/constants/statuses.js`, then run `test_status_sync.py` |
| **Add a maternity column** | One entry in `frontend/src/constants/maternityColumns.js` **and** the field in `MaternityLeaveBase` + `MaternityLeaveUpdate` in `backend/app/models/maternity.py`, then run `test_maternity_fields_sync.py` |
| **Change email / Teams wording** | `frontend/src/utils/outlook.js` (rejection email, interview invite) and `frontend/src/utils/maternityTemplates.js` |
| **Change preset recipients / Teams channel** | In the app: Maternity → *הגדרות התראות* (stored in Firestore `settings/maternity`) |
| **Add / remove users or change roles** | In the app: user menu → *ניהול משתמשים* (admins only) |
| **Add a role** (e.g. read-only `viewer`) | `VALID_ROLES` in `backend/app/models/user.py` **and** `ROLES` in `frontend/src/constants/roles.js` (run `test_roles_sync.py`). Then apply it with `require_roles(...)` in `backend/app/security.py` / `main.py`, and hide edit controls in the UI for that role |
| **Protect a new router** | Register it in `main.py` with `dependencies=[Depends(require_member)]` (or `require_admin`) |
