# YottaFlex Payment Reconciliation and AI Exception Investigation

A full-stack payment reconciliation system designed to automate payment matching, settlement verification, bank reconciliation, anomaly detection, and exception investigation.

The project combines Python, SQL, FastAPI, JavaScript, SQLite, and OpenAI API integration.

**GitHub Repository:**
https://github.com/anusha-ammu/yottaflex-payment-reconciliation

---

## 1. Project Overview

Payment reconciliation is the process of comparing payment records from multiple financial systems to identify mismatches, missing records, duplicate transactions, and settlement differences.

YottaFlex provides an automated reconciliation workflow that:

- Generates synthetic payment and settlement data.
- Processes processor events and bank statements.
- Matches payment and settlement records.
- Detects reconciliation anomalies.
- Creates and manages exceptions.
- Maintains an investigation audit trail.
- Provides REST API access.
- Offers AI-assisted exception investigation.

---

## 2. Technology Stack

| Technology | Purpose |
|---|---|
| Python | Backend development and reconciliation logic |
| SQL | Database queries and reconciliation |
| SQLite | Relational database |
| FastAPI | REST API development |
| JavaScript | Frontend and API integration |
| HTML5 | Frontend structure |
| CSS3 | Frontend styling |
| Streamlit | Reconciliation dashboard |
| OpenAI API | AI-assisted exception explanations |
| Git and GitHub | Version control and project collaboration |
| Pytest | Automated testing |

---

## 3. System Architecture

```text
                  YOTTAFLEX SYSTEM
                         |
             +-----------+-----------+
             |                       |
       Streamlit UI             JavaScript UI
             |                       |
             |                   HTTP / JSON
             |                       |
             +-----------+-----------+
                         |
                    FastAPI
                    Backend
                         |
             +-----------+-----------+
             |                       |
       SQLite Database         OpenAI API
             |                       |
       Payment Data          AI Exception Analysis
       Settlement Data       Explanation
       Bank Statements       Possible Causes
       Reconciliation        Investigation Steps
       Exceptions
       Audit History
```

---

## 4. Key Features

### Payment Reconciliation

- Payment order generation.
- Payment attempt tracking.
- Processor event processing.
- Settlement batch generation.
- Bank statement generation.
- Automated transaction matching.
- Reconciliation result tracking.

### Anomaly Detection

The system detects six reconciliation anomaly types:

1. Fee Variance
2. Duplicate Settlement Line
3. Duplicate Processor Event
4. Refund Before Capture
5. Currency Mismatch
6. Missing Source Record

### Exception Management

- Exception creation and tracking.
- Exception assignment.
- Investigation notes.
- Exception resolution.
- Exception closure.
- Audit history tracking.

### Full-Stack REST API

FastAPI provides endpoints for accessing exception records, reconciliation summaries, and investigation history.

### AI-Assisted Investigation

The OpenAI integration retrieves an exception and its investigation history from SQLite.

It can generate:

- Plain-language exception explanations.
- Supporting evidence summaries.
- Possible causes.
- Recommended investigation steps.
- Missing information required for further investigation.

AI recommendations require human verification. The assistant does not execute financial actions or independently resolve exceptions.

---

## 5. REST API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | API home |
| GET | `/api/health` | API health check |
| GET | `/api/exceptions` | List exceptions |
| GET | `/api/exceptions/{exception_id}` | Get exception details |
| GET | `/api/exceptions/{exception_id}/history` | Get exception audit history |
| GET | `/api/reconciliation/summary` | Get reconciliation summary |
| POST | `/api/ai/explain-exception` | Generate an AI exception explanation |

Interactive API documentation:

`http://127.0.0.1:8000/docs`

---

## 6. Project Structure

yottaflex-payment-reconciliation/
  api/
    __init__.py
    main.py
  app/
    app.py
  web/
    index.html
    app.js
    style.css
  src/
    database/
    reconciliation/
    exceptions/
  data/
  docs/
    SYSTEM_ARCHITECTURE.md
    DATABASE_SCHEMA.md
  scripts/
  tests/
  .env.example
  .gitignore
  README.md
  requirements.txt

## 7. Installation and Setup

### Step 1: Clone the Repository

```bash
git clone https://github.com/anusha-ammu/yottaflex-payment-reconciliation.git
```

### Step 2: Navigate to the Project

```bash
cd yottaflex-payment-reconciliation
```

### Step 3: Create a Virtual Environment

```bash
python -m venv .venv
```

### Step 4: Activate the Environment (Windows PowerShell)

```powershell
.\.venv\Scripts\Activate.ps1
```

### Step 5: Install Dependencies

```bash
python -m pip install -r requirements.txt
```

### Step 6: Configure Environment Variables

Copy `.env.example` to `.env` if the local `.env` file does not already exist.

Configure:

```text
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-6-luna
```

Use your own API key. Never upload the actual `.env` file to GitHub.

---

## 8. Running the Application

### Run the Streamlit Dashboard

```bash
python -m streamlit run app/app.py
```

### Run the FastAPI Backend

```bash
python -m uvicorn api.main:app --reload
```

### Open the JavaScript Frontend

`http://127.0.0.1:8000/web/`

### Open FastAPI Swagger Documentation

`http://127.0.0.1:8000/docs`

---

## 9. Running Tests

Execute the test suite:

```bash
python -m pytest -q
```

The tests cover the existing reconciliation and exception workflow functionality.

---

## 10. Database and Reconciliation Validation

The project includes large-scale synthetic reconciliation datasets.

The full-scale test scenario includes:

- 2,000 merchants.
- 50,000 payment orders.
- 55,000 payment attempts.
- 100,000 original processor events.
- 1,000 settlement batches.
- 90,000 settlement lines.
- 5,000 bank statement lines.

The anomaly test scenario includes six deliberately injected anomalies and a separate ground-truth comparison.

The large full-scale database files are generated locally and are not included in the GitHub repository.

---

## 11. Security and Limitations

- OpenAI API credentials are stored in local environment variables.
- The `.env` file is excluded from Git tracking.
- `.env.example` contains placeholders only.
- AI-generated findings are recommendations and require human review.
- Live AI responses require an accessible OpenAI API model and available API credits.
- The current API is designed for local demonstration.
- Authentication, authorization, production-grade CORS restrictions, and additional deployment security must be implemented before public production use.

---

## 12. Learning Outcomes

This project demonstrates practical experience with:

- Python backend engineering.
- SQL and relational database design.
- Payment reconciliation workflows.
- Data validation and anomaly detection.
- Exception management and audit trails.
- REST API design and development.
- JavaScript frontend development.
- HTTP and JSON integration.
- LLM integration using the OpenAI API.
- Git and GitHub workflows.
- Automated testing.

---

## Author

**Anusha**

GitHub: https://github.com/anusha-ammu

**Project:** YottaFlex Payment Reconciliation and AI Exception Investigation