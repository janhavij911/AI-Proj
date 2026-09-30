# AI Document Analyzer

An AI-powered pipeline that extracts structured data from invoices and flags anomalies using Azure AI Document Intelligence and Claude.

## Problem

Manually reviewing invoices for missing fields, unusual amounts, or inconsistencies is slow and error-prone. This project automates both the extraction and the reasoning layer of that review process.

## Architecture

Document (PDF/image)
│
▼
Azure AI Document Intelligence (prebuilt-invoice model)
│ → extracts structured fields: vendor, dates, totals, line items, confidence scores
▼
Claude (reasoning layer)
│ → summarizes the document in plain English
│ → flags anomalies: missing fields, unusual amounts, low-confidence extractions, stale dates
▼
Streamlit UI — displays extracted fields, summary, and anomaly warnings


## Tech Stack

- **Azure AI Document Intelligence** — OCR + structured field extraction (prebuilt-invoice model)
- **Claude (Anthropic)** — reasoning layer for summarization and anomaly detection
- **Streamlit** — interactive UI
- **Python** — azure-ai-documentintelligence, anthropic, python-dotenv

## How It Works

1. `document_extraction.py` sends a document to Azure Document Intelligence and extracts structured fields as JSON
2. `claude_reasoning.py` takes those fields and asks Claude to summarize the document and flag anomalies
3. `app.py` combines both steps into an interactive Streamlit app — upload a document and see the full pipeline run

## Running It

```bash
pip install -r requirements.txt
```

Create a `.env` file with:

AZURE_DOC_INTEL_ENDPOINT=https://your-resource.cognitiveservices.azure.com/
AZURE_DOC_INTEL_KEY=your-azure-key
ANTHROPIC_API_KEY=your-anthropic-key


Then run:
```bash
python document_extraction.py
python claude_reasoning.py
streamlit run app.py
```

## Demo

![Demo](demo.png)

*Sample output: Azure Document Intelligence extracted 26 fields from a test invoice, and Claude flagged 5 anomalies including missing line items, an amount mismatch, and stale invoice dates.*

## Design Decisions

- Used the `prebuilt-invoice` model rather than training a custom model, since it covers standard invoice fields (vendor, totals, dates, line items) without requiring labeled training data
- Separated extraction and reasoning into independent scripts so each stage can be tested, debugged, and swapped out on its own
- Added a guardrail-style prompt structure asking Claude to explicitly flag low-confidence fields (below 0.7) rather than silently trusting all OCR output

## Limitations & Next Steps

- Currently tested against a single sample invoice; a larger, evaluated test set would strengthen accuracy claims
- No destructive-action guardrails needed here since this is a read-only analysis pipeline, but a production version handling write operations would need them
- Could add: batch processing for multiple documents at once, a vector-based lookup for flagging duplicate invoices, and confidence-based auto-routing (e.g., auto-approve high-confidence extractions, flag low-confidence ones for human review)

## Certifications Behind This Project

Built while completing:
- Microsoft AI-103 (Azure AI Apps and Agents Developer Associate)
- Claude Certified Associate: Foundations