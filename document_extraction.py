"""
document_extraction.py
Extracts structured fields (vendor, date, total, line items, etc.) from
invoice/receipt documents using Azure AI Document Intelligence (Foundry Tools).

Setup:
    pip install azure-ai-documentintelligence python-dotenv

Environment variables required (create a .env file, see .env.example):
    AZURE_DOC_INTEL_ENDPOINT=https://<your-resource>.cognitiveservices.azure.com/
    AZURE_DOC_INTEL_KEY=<your-key>
"""

import os
import json
import glob
from pathlib import Path
from dotenv import load_dotenv
from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeResult

load_dotenv()

ENDPOINT = os.getenv("AZURE_DOC_INTEL_ENDPOINT")
KEY = os.getenv("AZURE_DOC_INTEL_KEY")

# Choose the prebuilt model that fits your sample docs:
# "prebuilt-invoice" for invoices, "prebuilt-receipt" for receipts,
# "prebuilt-layout" for generic text/table extraction from any document.
MODEL_ID = "prebuilt-invoice"


def get_client() -> DocumentIntelligenceClient:
    if not ENDPOINT or not KEY:
        raise EnvironmentError(
            "Missing AZURE_DOC_INTEL_ENDPOINT or AZURE_DOC_INTEL_KEY. "
            "Set them in a .env file or your environment."
        )
    return DocumentIntelligenceClient(endpoint=ENDPOINT, credential=AzureKeyCredential(KEY))


def extract_fields(client: DocumentIntelligenceClient, file_path: str) -> dict:
    """Send one document to Document Intelligence and return extracted fields as a dict."""
    with open(file_path, "rb") as f:
        poller = client.begin_analyze_document(
            model_id=MODEL_ID,
            body=f,
            content_type="application/octet-stream",
        )
    result: AnalyzeResult = poller.result()

    extracted = {
        "file_name": Path(file_path).name,
        "fields": {},
        "raw_text_preview": (result.content[:500] if result.content else ""),
    }

    if result.documents:
        doc = result.documents[0]
        for field_name, field in (doc.fields or {}).items():
            # field.value_string / value_number / value_date etc. depending on type
            value = (
                field.get("valueString")
                or field.get("valueNumber")
                or field.get("valueDate")
                or field.get("content")
            )
            extracted["fields"][field_name] = {
                "value": value,
                "confidence": field.get("confidence"),
            }

    return extracted


def run_batch(input_dir: str, output_path: str) -> list:
    """Process every PDF/image in input_dir and save all results as one JSON file."""
    client = get_client()
    file_paths = sorted(
        glob.glob(os.path.join(input_dir, "*.pdf"))
        + glob.glob(os.path.join(input_dir, "*.png"))
        + glob.glob(os.path.join(input_dir, "*.jpg"))
    )

    if not file_paths:
        print(f"No documents found in {input_dir}. Add sample PDFs/images there first.")
        return []

    results = []
    for path in file_paths:
        print(f"Processing: {path}")
        try:
            extracted = extract_fields(client, path)
            results.append(extracted)
            print(f"  ✓ Extracted {len(extracted['fields'])} fields")
        except Exception as e:
            print(f"  ✗ Failed on {path}: {e}")

    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nSaved {len(results)} results to {output_path}")
    return results


if __name__ == "__main__":
    INPUT_DIR = "data/sample_documents"
    OUTPUT_PATH = "data/extracted_results.json"
    os.makedirs(INPUT_DIR, exist_ok=True)
    os.makedirs("data", exist_ok=True)
    run_batch(INPUT_DIR, OUTPUT_PATH)
