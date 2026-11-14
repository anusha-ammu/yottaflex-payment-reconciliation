const summaryEl = document.getElementById("summary");
const exceptionsEl = document.getElementById("exceptions");
const selectedEl = document.getElementById("selected");
const explainBtn = document.getElementById("explain");
const resultEl = document.getElementById("result");

let selectedExceptionId = null;

async function apiRequest(url, options = {}) {
    const response = await fetch(url, options);
    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.detail || `HTTP ${response.status}`);
    }

    return data;
}

async function loadData() {
    try {
        const summary = await apiRequest("/api/reconciliation/summary");

        summaryEl.textContent =
            `Total exceptions: ${summary.total_exceptions} | ` +
            JSON.stringify(summary.exceptions_by_status);

        const exceptions = await apiRequest("/api/exceptions");

        exceptionsEl.replaceChildren();

        exceptions.forEach(exception => {
            const button = document.createElement("button");
            button.className = "exception";

            button.textContent =
                `${exception.exception_id} | ` +
                `${exception.exception_type} | ` +
                `${exception.title}`;

            button.addEventListener("click", () => {
                selectedExceptionId = exception.exception_id;
                selectedEl.textContent =
                    `Selected: ${exception.exception_id} - ${exception.title}`;

                explainBtn.disabled = false;
                resultEl.textContent = "Ready to investigate.";
            });

            exceptionsEl.appendChild(button);
        });

    } catch (error) {
        summaryEl.textContent = "Error: " + error.message;
        exceptionsEl.textContent = "Could not load exceptions.";
    }
}

explainBtn.addEventListener("click", async () => {
    if (!selectedExceptionId) return;

    explainBtn.disabled = true;
    resultEl.textContent = "Requesting AI explanation...";

    try {
        const data = await apiRequest(
            "/api/ai/explain-exception",
            {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({
                    exception_id: selectedExceptionId,
                    question:
                        "Explain this exception, identify evidence, " +
                        "possible causes and recommended investigation steps."
                })
            }
        );

        resultEl.textContent =
            data.ai_explanation +
            "\n\nHuman review required: " +
            data.human_review_required;

    } catch (error) {
        resultEl.textContent =
            "AI request failed: " + error.message +
            "\nCheck that OpenAI API credits are available.";
    } finally {
        explainBtn.disabled = false;
    }
});

document.getElementById("refresh").addEventListener("click", loadData);

loadData();
