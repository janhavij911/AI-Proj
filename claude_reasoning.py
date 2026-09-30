"""
claude_reasoning.py
Takes the structured JSON output from document_extraction.py and asks Claude
to summarize each document and flag anomalies (missing fields, unusually high
amounts, inconsistent dates, etc.).

Setup:
    pip install anthropic python-dotenv

Environment variables required (.env file):
    ANTHROPIC_API_KEY=<your-key>
"""

import os
import json
from dotenv import load_dotenv
import anthropic

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """You are a financial document review assistant. You will be given
structured fields extracted from an invoice or receipt by an OCR/extraction system.

Your job:
1. Write a 2-3 sentence plain-English summary of the document.
2. Flag any anomalies you notice: missing critical fields (vendor, total, date),
   unusually high or low amounts, inconsistent or suspicious dates, or low
   extraction confidence scores (below 0.7).
3. If nothing looks unusual, explicitly say "No anomalies detected."

Respond ONLY in this JSON format, with no preamble or markdown fences:
{
  "summary": "...",
  "anomalies": ["...", "..."],
  "anomaly_count": 0
}
"""


def analyze_document(extracted_doc: dict) -> dict:
    """Send one extracted document's fields to Claude and get back summary + anomalies."""
    fields_text = json.dumps(extracted_doc.get("fields", {}), indent=2, default=str)

    user_prompt = f"""Document: {extracted_doc.get('file_name')}

Extracted fields:
{fields_text}
"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw_text = response.content[0].text.strip()

    # Defensive parsing in case Claude wraps output in code fences despite instructions
    cleaned = raw_text.replace("```json", "").replace("```", "").strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        parsed = {
            "summary": raw_text,
            "anomalies": ["Could not parse structured response"],
            "anomaly_count": -1,
        }

    return parsed


def run_batch(extracted_json_path: str, output_path: str) -> list:
    with open(extracted_json_path, "r") as f:
        extracted_docs = json.load(f)

    results = []
    for doc in extracted_docs:
        print(f"Analyzing: {doc.get('file_name')}")
        analysis = analyze_document(doc)
        results.append({
            "file_name": doc.get("file_name"),
            "extracted_fields": doc.get("fields"),
            "claude_analysis": analysis,
        })
        print(f"  Summary: {analysis.get('summary', '')[:80]}...")
        print(f"  Anomalies: {analysis.get('anomaly_count', 0)}")

    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nSaved {len(results)} analyses to {output_path}")
    return results


if __name__ == "__main__":
    run_batch(
        extracted_json_path="data/extracted_results.json",
        output_path="data/final_analysis.json",
    )
