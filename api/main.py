import os
import sqlite3
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from openai import OpenAI, OpenAIError
from pydantic import BaseModel, Field

from src.exceptions.workflow import list_exceptions, get_exception_history

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

DB_PATH = Path(
    os.getenv(
        "YOTTAFLEX_DB_PATH",
        str(ROOT / "data" / "exception_workflow_test.db")
    )
)

MODEL = os.getenv("OPENAI_MODEL", "gpt-6-luna")

app = FastAPI(
    title="YottaFlex Payment Reconciliation API",
    description="REST API with AI-assisted exception investigation.",
    version="1.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AIExplanationRequest(BaseModel):
    exception_id: str = Field(min_length=1, max_length=100)
    question: str = Field(
        default="Explain this exception and recommend investigation steps.",
        max_length=1000
    )


def get_connection():
    if not DB_PATH.exists():
        raise HTTPException(status_code=500, detail="Database not found.")

    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@app.get("/")
def home():
    return {
        "message": "YottaFlex Payment Reconciliation API",
        "docs": "/docs",
        "status": "running"
    }


@app.get("/api/health")
def health():
    return {
        "status": "healthy",
        "database_exists": DB_PATH.exists(),
        "openai_key_configured": bool(os.getenv("OPENAI_API_KEY"))
    }


@app.get("/api/exceptions")
def exceptions(status: Optional[str] = None):
    connection = get_connection()
    try:
        return list_exceptions(connection, status)
    finally:
        connection.close()


@app.get("/api/exceptions/{exception_id}")
def exception_detail(exception_id: str):
    connection = get_connection()
    try:
        row = connection.execute(
            "SELECT * FROM exceptions WHERE exception_id = ?",
            (exception_id,)
        ).fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail="Exception not found.")

        return dict(row)
    finally:
        connection.close()


@app.get("/api/exceptions/{exception_id}/history")
def exception_history(exception_id: str):
    connection = get_connection()
    try:
        return get_exception_history(connection, exception_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Exception not found.")
    finally:
        connection.close()


@app.get("/api/reconciliation/summary")
def reconciliation_summary():
    connection = get_connection()
    try:
        total = connection.execute(
            "SELECT COUNT(*) FROM exceptions"
        ).fetchone()[0]

        rows = connection.execute(
            """
            SELECT exception_status, COUNT(*) AS total
            FROM exceptions
            GROUP BY exception_status
            """
        ).fetchall()

        return {
            "total_exceptions": total,
            "exceptions_by_status": {
                row["exception_status"]: row["total"]
                for row in rows
            }
        }
    finally:
        connection.close()


@app.post("/api/ai/explain-exception")
def explain_exception(request: AIExplanationRequest):
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="OpenAI API key is not configured."
        )

    connection = get_connection()

    try:
        row = connection.execute(
            "SELECT * FROM exceptions WHERE exception_id = ?",
            (request.exception_id,)
        ).fetchone()

        if row is None:
            raise HTTPException(
                status_code=404,
                detail="Exception not found."
            )

        exception_data = dict(row)
        history = get_exception_history(
            connection,
            request.exception_id
        )
    finally:
        connection.close()

    prompt = f"""
Analyze this payment reconciliation exception.

Exception record:
{exception_data}

Investigation history:
{history}

Analyst question:
{request.question}

Provide:
1. Plain-language explanation.
2. Evidence available in the records.
3. Possible causes, clearly marked as hypotheses.
4. Recommended investigation steps.
5. Missing information needed to confirm the cause.

Never invent financial facts or claim an action was performed.
Human review is required before any financial decision.
"""

    try:
        client = OpenAI(api_key=api_key)

        response = client.responses.create(
            model=MODEL,
            instructions=(
                "You are an evidence-based payment reconciliation "
                "investigation assistant. Be accurate and cautious. "
                "Never invent transaction evidence."
            ),
            input=prompt
        )

        return {
            "exception_id": request.exception_id,
            "model": MODEL,
            "ai_explanation": response.output_text,
            "human_review_required": True
        }

    except OpenAIError:
        raise HTTPException(
            status_code=502,
            detail="OpenAI request failed. Check API access, model availability and billing."
        )


app.mount('/web', StaticFiles(directory=ROOT / 'web', html=True), name='web')

