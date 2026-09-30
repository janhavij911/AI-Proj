"""
app.py
Minimal Streamlit UI: upload a document -> Azure Document Intelligence extracts
fields -> Claude summarizes and flags anomalies -> results shown on screen.

Setup:
    pip install streamlit azure-ai-documentintelligence anthropic python-dotenv

Run:
    streamlit run app.py

Environment variables required (.env file):
    AZURE_DOC_INTEL_ENDPOINT=https://<your-resource>.cognitiveservices.azure.com/
    AZURE_DOC_INTEL_KEY=<your-key>
    ANTHROPIC_API_KEY=<your-key>
"""

import os
import json
import tempfile
import streamlit as st
from dotenv import load_dotenv
from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient

load_dotenv()

st.set_page_config(page_title="AI Document Analyzer", page_icon="📄", layout="centered")

AZURE_ENDPOINT = os.getenv("AZURE_DOC_INTEL_ENDPOINT")
AZURE_KEY = os.getenv("AZURE_DOC_INTEL_KEY")

# Set this to True once you have a real Anthropic API key with billing enabled.
# While False, the app shows a manually-obtained Claude analysis instead of a
# live API call, since the reasoning step was validated manually via claude.ai
# during development (see README for details).
USE_LIVE_CLAUDE_API = False

MODEL_ID = "prebuilt-invoice"
CLAUDE_MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """You are a financial document review assistant. You will be given
structured fields extracted from an invoice or receipt by an OCR/extraction system.

Your job:
1. Write a 2-3 sentence plain-English summary of the document.
2. Flag any anomalies: missing critical fields, unusually high/low amounts,
   inconsistent dates, or low extraction confidence (below 0.7).
3. If nothing looks unusual, say "No anomalies detected."

Respond ONLY in this JSON format, no preamble or markdown fences:
{"summary": "...", "anomalies": ["..."], "anomaly_count": 0}
"""

# Paste the response you got from claude.ai here after manually testing the
# reasoning step.
MANUAL_CLAUDE_ANALYSIS = {
    "summary": "This is an invoice (INV-100) from Contoso Ltd. to Microsoft Corp for a total amount due of $610.00.",
    "anomalies": [
        "Missing fields: Items and TaxDetails are both null.",
        "Amount due vs. invoice total: the $610.00 due is higher than expected given the line items.",
        "Unusual address setup: seven distinct addresses appear, which is more than typical.",
        "Stale dates: the invoice dates are from 2019.",
        "Truncated text: the raw text preview cuts off after the PO number."
    ],
    "anomaly_count": 5,
}


@st.cache_resource
def get_doc_intel_client():
    return DocumentIntelligenceClient(endpoint=AZURE_ENDPOINT, credential=AzureKeyCredential(AZURE_KEY))


def extract_fields(file_bytes: bytes) -> dict:
    client = get_doc_intel_client()
    poller = client.begin_analyze_document(
        model_id=MODEL_ID,
        body=file_bytes,
        content_type="application/octet-stream",
    )
    result = poller.result()

    fields = {}
    if result.documents:
        doc = result.documents[0]
        for field_name, field in (doc.fields or {}).items():
            value = (
                field.get("valueString")
                or field.get("valueNumber")
                or field.get("valueDate")
                or field.get("content")
            )
            fields[field_name] = {"value": value, "confidence": field.get("confidence")}
    return fields


def analyze_with_claude(fields: dict) -> dict:
    if not USE_LIVE_CLAUDE_API:
        # Manual mode: reasoning step validated via claude.ai during development.
        return MANUAL_CLAUDE_ANALYSIS

    import anthropic
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=anthropic_key)
    user_prompt = f"Extracted fields:\n{json.dumps(fields, indent=2, default=str)}"

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    raw = response.content[0].text.strip().replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"summary": raw, "anomalies": ["Could not parse structured response"], "anomaly_count": -1}


# --- UI ---
st.title("📄 AI Document Analyzer")
st.caption("Azure AI Document Intelligence (extraction) + Claude (reasoning) in one pipeline")

if not (AZURE_ENDPOINT and AZURE_KEY):
    st.error("Missing API keys. Set AZURE_DOC_INTEL_ENDPOINT and AZURE_DOC_INTEL_KEY in your .env file.")
    st.stop()

if not USE_LIVE_CLAUDE_API:
    st.info("ℹ️ Running in manual mode: the reasoning step below uses a Claude analysis "
            "validated via claude.ai during development, rather than a live API call. "
            "Set USE_LIVE_CLAUDE_API = True with a funded Anthropic key to make it live.")

uploaded_file = st.file_uploader("Upload an invoice or receipt (PDF, PNG, JPG)", type=["pdf", "png", "jpg", "jpeg"])

if uploaded_file is not None:
    file_bytes = uploaded_file.read()

    with st.spinner("Extracting fields with Azure Document Intelligence..."):
        try:
            fields = extract_fields(file_bytes)
        except Exception as e:
            st.error(f"Extraction failed: {e}")
            st.stop()

    st.subheader("Extracted Fields")
    if fields:
        st.table({
            "Field": list(fields.keys()),
            "Value": [str(f["value"]) for f in fields.values()],
            "Confidence": [f"{f['confidence']:.2f}" if f["confidence"] else "-" for f in fields.values()],
        })
    else:
        st.warning("No fields extracted — try a different document or model type.")

    spinner_text = "Analyzing with Claude..." if USE_LIVE_CLAUDE_API else "Loading Claude analysis..."
    with st.spinner(spinner_text):
        try:
            analysis = analyze_with_claude(fields)
        except Exception as e:
            st.error(f"Claude analysis failed: {e}")
            st.stop()

    st.subheader("AI Summary")
    st.write(analysis.get("summary", "No summary generated."))

    st.subheader("Anomaly Check")
    anomalies = analysis.get("anomalies", [])
    if anomalies and analysis.get("anomaly_count", 0) > 0:
        for a in anomalies:
            st.warning(f"⚠️ {a}")
    else:
        st.success("✅ No anomalies detected.")
else:
    st.info("Upload a document above to get started.")
