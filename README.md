# YottaFlex - Payment Reconciliation and AI Exception Investigation

A full-stack payment reconciliation system designed to automate payment matching, settlement verification, bank reconciliation, anomaly detection, and exception investigation.

The project combines Python, SQL, SQLite, FastAPI, JavaScript, and OpenAI API integration to demonstrate an end-to-end financial reconciliation workflow.

**GitHub Repository:** https://github.com/anusha-ammu/yottaflex-payment-reconciliation

---

## 1. Project Overview

Payment reconciliation is the process of comparing financial records across payment processors, settlement systems, and bank statements to identify discrepancies and ensure accurate financial reporting.

YottaFlex provides an automated reconciliation workflow that:

- Generates synthetic payment and settlement data.
- Processes payment attempts and processor events.
- Matches settlement records against bank statements.
- Detects payment and settlement anomalies.
- Creates and manages reconciliation exceptions.
- Maintains an investigation audit trail.
- Provides REST API access to exception and reconciliation data.
- Offers a JavaScript-based dashboard.
- Integrates an AI assistant for exception investigation.

---

## 2. Technology Stack

| Technology | Purpose |
|---|---|
| Python | Backend development and reconciliation logic |
| SQL | Database queries and reconciliation |
| SQLite | Relational database |
| FastAPI | REST API development |
| JavaScript | Frontend development and API integration |
| HTML5 | Frontend structure |
| CSS3 | Frontend styling |
| Streamlit | Reconciliation dashboard |
| OpenAI API | AI-assisted exception explanations |
| Pytest | Automated testing |
| Git and GitHub | Version control and project hosting |

---

## 3. System Architecture

```text
                    YOTTAFLEX SYSTEM
                           |
              +------------+------------+
              |                         |
         Streamlit UI              JavaScript UI
              |                         |
              |                      HTTP/JSON
              |                         |
              +------------+------------+
                           |
                     FastAPI Backend
                           |
              +------------+------------+
              |                         |
        SQLite Database             OpenAI API
              |                         |
       Payment Records          AI Exception Analysis
       Processor Events         Explanation
       Settlement Records       Possible Causes
       Bank Statements          Investigation Steps
       Reconciliation Results
       Exceptions
       Audit History
```

---

## 4. Core Features

### 4.1 Payment Reconciliation

- Payment order generation.
- Payment attempt tracking.
- Processor event processing.
- Settlement batch generation.
- Bank statement generation.
- Automated payment and settlement matching.
- Reconciliation result tracking.

### 4.2 Anomaly Detection

The system detects six reconciliation anomaly types:

1. Fee Variance
2. Duplicate Settlement Line
3. Duplicate Processor Event
4. Refund Before Capture
5. Currency Mismatch
6. Missing Source Record

### 4.3 Exception Management

- Exception creation and tracking.
- Exception assignment.
- Investigation notes.
- Exception resolution.
- Exception closure.
- Audit history tracking.

### 4.4 Full-Stack REST API

The FastAPI backend exposes REST endpoints for accessing exception records, reconciliation summaries, and investigation history.

### 4.5 JavaScript Dashboard

The frontend uses HTML, CSS, and JavaScript to communicate with the FastAPI backend through HTTP and JSON requests.

Dashboard capabilities include:

- Reconciliation summary.
- Exception listing.
- Exception selection.
- AI explanation requests.
- API-driven data loading.

### 4.6 AI-Assisted Exception Investigation

The OpenAI integration uses exception information and investigation history from SQLite to generate:

- Plain-language explanations.
- Evidence summaries.
- Possible causes.
- Recommended investigation steps.
- Missing information required for further investigation.

AI-generated recommendations require human verification. The assistant does not execute financial actions or independently resolve exceptions.

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
| POST | `/api/ai/explain-exception` | Generate AI exception explanation |

### Interactive API Documentation

FastAPI Swagger documentation:

http://127.0.0.1:8000/docs

---

## 6. Project Structure

```text
yottaflex-payment-reconciliation/
|
+-- api/
|   +-- __init__.py
|   +-- main.py
|
+-- app/
|   +-- app.py
|
+-- web/
|   +-- index.html
|   +-- app.js
|   +-- style.css
|
+-- src/
|   +-- database/
|   +-- reconciliation/
|   +-- exceptions/
|
+-- data/
|
+-- docs/
|   +-- SYSTEM_ARCHITECTURE.md
|   +-- DATABASE_SCHEMA.md
|
+-- scripts/
|
+-- tests/
|
+-- .env.example
+-- .gitignore
+-- README.md
+-- requirements.txt
```

---

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

### Step 4: Activate the Virtual Environment

For Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

### Step 5: Install Dependencies

```powershell
python -m pip install -r requirements.txt
```

### Step 6: Configure Environment Variables

Create a local `.env` file from the example:

```powershell
Copy-Item .env.example .env
```

Edit `.env` and add your own OpenAI API key and an API model available to your account:

```text
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=your_available_model_id
```

Never upload your real `.env` file or API credentials to GitHub.

---

## 8. Running the Application

### 8.1 Run the Streamlit Dashboard

```powershell
python -m streamlit run .\app\app.py
```

### 8.2 Run the FastAPI Backend

```powershell
python -m uvicorn api.main:app --reload
```

### 8.3 Open the JavaScript Frontend

http://127.0.0.1:8000/web/

### 8.4 Open API Documentation

http://127.0.0.1:8000/docs

The FastAPI server must be running to use the JavaScript frontend.

---

## 9. Automated Testing

Run the project's automated test suite:

```powershell
python -m pytest -q
```

The existing tests cover reconciliation anomaly detection and exception workflow functionality.

A previously verified test run completed with four passing tests.

---

## 10. Database and Large-Scale Validation

The project includes large-scale synthetic payment reconciliation datasets.

The full-scale test scenario includes:

- 2,000 merchants.
- 50,000 payment orders.
- 55,000 payment attempts.
- 100,000 original processor events.
- 1,000 settlement batches.
- 90,000 settlement lines.
- 5,000 bank statement lines.

The clean baseline reconciliation produced:

- 1,000 matched settlement batches.
- Zero reconciliation exceptions.

A separate anomaly test dataset includes six deliberately injected anomalies and an independent ground-truth comparison.

Database integrity and foreign key validation were also performed.

Large-scale database files are generated locally and are not included in the public GitHub repository.

---

## 11. AI Integration and Limitations

The project includes an OpenAI Responses API integration for AI-assisted payment exception investigation.

The AI endpoint retrieves exception data and investigation history from the database and submits the evidence for analysis.

Live AI responses require:

- A valid OpenAI API key.
- Access to the configured model.
- Available OpenAI API credits.

The AI integration code is implemented. However, successful live AI response generation has not been demonstrated because the development API account currently has insufficient credits.

The reconciliation engine, REST API, and JavaScript dashboard can be used independently of the live AI service.

---

## 12. Security Considerations

- API keys are stored in a local `.env` file.
- `.env` is excluded from Git tracking.
- `.env.example` contains placeholder values only.
- API keys must never be embedded in frontend JavaScript.
- AI recommendations require human verification.
- The current API is intended for local development and demonstration.
- Authentication, authorization, restricted CORS settings, and additional security controls are required before public production deployment.

---

## 13. Learning Outcomes

This project demonstrates practical experience with:

- Python backend development.
- SQL and relational database design.
- Payment reconciliation workflows.
- Data validation and anomaly detection.
- Exception management and audit trails.
- REST API design and development.
- JavaScript frontend development.
- HTTP and JSON integration.
- OpenAI API integration.
- Automated testing with Pytest.
- Git and GitHub workflows.
- Financial data investigation and validation.

---

## 14. Author

**Anusha**

GitHub: https://github.com/anusha-ammu

**Project:** YottaFlex Payment Reconciliation and AI Exception Investigation