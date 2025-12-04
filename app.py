import io
import json
import re
import time
from typing import List, Tuple, Dict, Any

import streamlit as st
import requests
import pdfplumber
import fitz
from PIL import Image
import pytesseract
import pandas as pd

st.set_page_config(page_title="AI-Powered Document Orchestrator", layout="wide")


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    parts = []
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for p in pdf.pages:
                t = p.extract_text()
                if t:
                    parts.append(t)
    except Exception:
        pass
    combined = "\n\n".join(parts)
    if combined.strip():
        return combined
    # PyMuPDF fallback
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        for p in doc:
            txt = p.get_text("text")
            if txt:
                parts.append(txt)
    except Exception:
        pass
    combined = "\n\n".join(parts)
    if combined.strip():
        return combined
    # OCR fallback
    ocr = []
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for p in pdf.pages:
                pil = p.to_image(resolution=300).original
                ocr.append(pytesseract.image_to_string(pil))
    except Exception:
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            for p in doc:
                pix = p.get_pixmap(dpi=200)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                ocr.append(pytesseract.image_to_string(img))
        except Exception:
            pass
    return "\n\n".join([o for o in ocr if o and o.strip()])


def extract_text_from_txt(b: bytes) -> str:
    for enc in ("utf-8", "latin-1", "utf-16"):
        try:
            return b.decode(enc)
        except Exception:
            continue
    return b.decode("utf-8", errors="replace")


def chunk_text(text: str, max_chars: int = 6000) -> List[str]:
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]
    chunks = []
    i = 0
    while i < len(text):
        j = min(len(text), i + max_chars)
        if j < len(text):
            split = max(text.rfind("\n", i, j), text.rfind(". ", i, j))
            if split > i:
                j = split + 1
        chunks.append(text[i:j].strip())
        i = j
    return chunks


def safe_json_load(s: str) -> Tuple[bool, Any]:
    try:
        return True, json.loads(s)
    except Exception:
        m = re.search(r"(\{(?:.|\n)*\})", s)
        if m:
            try:
                return True, json.loads(m.group(1))
            except Exception:
                pass
    return False, s


def redact_sensitive(extracted: dict, keys: List[str] = None) -> dict:
    if keys is None:
        keys = ["Account_Number", "Account No", "Account_No", "AccountNumber", "Account"]
    out = json.loads(json.dumps(extracted))
    kf = out.get("best_candidate", {}).get("key_fields", {})
    for key in list(kf.keys()):
        if any(k.lower() in key.lower() for k in keys):
            val = str(kf.get(key, ""))
            kf[key] = ("****" + val[-4:]) if len(val) > 4 else "****"
    return out


def normalize_numbers(extracted: dict) -> dict:
    out = json.loads(json.dumps(extracted))
    kf = out.get("best_candidate", {}).get("key_fields", {})
    for k, v in list(kf.items()):
        if isinstance(v, str):
            s = v.replace(",", "").replace("₹", "").replace("$", "").strip()
            if re.fullmatch(r"\d+(\.\d+)?", s):
                kf[k] = int(s) if "." not in s else float(s)
    return out


def call_n8n_webhook(webhook_url: str, payload: dict) -> dict:
    try:
        r = requests.post(webhook_url, json=payload, timeout=60)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def stub_gemini_response(doc_text: str, question: str) -> dict:
    return {
        "best_candidate": {
            "summary": "Demo summary: extracted sample findings.",
            "key_fields": {
                "Account_Holder": "Ankita Sharma",
                "Statement_Period": "01 Nov 2025 - 30 Nov 2025",
                "Total_Credits": "45000",
                "Total_Debits": "5000",
                "Closing_Balance": "64252"
            },
            "confidence": 0.85,
            "risk_level": "Medium"
        },
        "merged_key_fields": {},
        "chunks_considered": 1,
        "raw_aggregated": []
    }


def call_gemini_structured(api_key: str, doc_text: str, question: str, max_attempts: int = 2) -> Dict[str, Any]:
    if not api_key or api_key.strip().lower().startswith("test") or "example" in api_key:
        return stub_gemini_response(doc_text, question)
    try:
        from google import genai
    except Exception:
        return {"error": "google-genai SDK not installed."}
    client = genai.Client(api_key=api_key)
    example_schema = {
        "summary": "short summary",
        "key_fields": {"field_1": "value", "field_2": "value", "field_3": "value"},
        "confidence": 0.0,
        "risk_level": "Low"
    }
    example_text = json.dumps(example_schema, indent=2)
    instruction = (
        "You are an extractor. Output ONLY valid JSON matching the example exactly. "
        "Identify 5-8 most relevant simple key:value pairs in 'key_fields', include 'summary', 'confidence' (0-1), optionally 'risk_level'. "
        "Example:\n" + example_text
    )
    chunks = chunk_text(doc_text, max_chars=6000)
    raw_aggregated = []
    best_candidate = None
    for attempt in range(1, max_attempts + 1):
        raw_aggregated.clear()
        best_candidate = None
        for chunk in chunks or [doc_text]:
            prompt = f"{instruction}\n\nQUESTION: {question}\n\nDOCUMENT_CHUNK:\n{chunk}"
            try:
                resp = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
            except Exception as e:
                return {"error": f"Gemini SDK call failed: {e}"}
            content = getattr(resp, "text", None)
            if content is None:
                try:
                    content = resp.output[0].content[0].text
                except Exception:
                    content = str(resp)
            raw_aggregated.append(content)
            ok, parsed = safe_json_load(content)
            if ok and isinstance(parsed, dict):
                best_candidate = parsed
            time.sleep(0.15)
        if best_candidate:
            return {
                "best_candidate": best_candidate,
                "merged_key_fields": best_candidate.get("key_fields", {}),
                "chunks_considered": len(chunks) if chunks else 1,
                "raw_aggregated": raw_aggregated,
                "attempts": attempt
            }
        if attempt < max_attempts:
            instruction = "OUTPUT ONLY JSON. NOTHING ELSE. Follow the example exactly: " + example_text
            time.sleep(0.2)
    return {"error": "Model did not return valid JSON after retries.", "raw_aggregated": raw_aggregated}


def render_structured(structured: dict):
    sc = structured or {}
    summary = sc.get("summary", "")
    conf = sc.get("confidence")
    risk = sc.get("risk_level")
    kf = sc.get("key_fields", {}) or sc.get("key_fields", {})
    if summary:
        st.subheader("Quick Summary")
        st.write(summary)
    st.caption(f"Risk: {risk}    Confidence: {conf}")
    if isinstance(kf, dict) and kf:
        df = pd.DataFrame(list(kf.items()), columns=["Field", "Value"])
        st.subheader("Extracted Key-Value Pairs")
        st.table(df)


def main():
    st.title("AI-Powered Document Orchestrator")
    uploaded = st.file_uploader("Upload PDF or TXT", type=["pdf", "txt"])
    question = st.text_input("Analytical question", value="Identify key points and risk_level")
    run_extract = st.button("Run Structured Extraction (Gemini)")
    if uploaded:
        raw = uploaded.read()
        if uploaded.name.lower().endswith(".pdf"):
            doc_text = extract_text_from_pdf(raw)
        else:
            doc_text = extract_text_from_txt(raw)
        st.subheader("Document preview")
        st.code(doc_text[:3000] + ("..." if len(doc_text) > 3000 else ""))
        if run_extract:
            api_key = st.secrets.get("GEMINI_API_KEY", "")
            with st.spinner("Running structured extraction..."):
                gem = call_gemini_structured(api_key, doc_text, question)
            if "error" in gem:
                st.error(gem["error"])
                if "raw_aggregated" in gem:
                    st.subheader("Raw model outputs")
                    for i, r in enumerate(gem.get("raw_aggregated", []), start=1):
                        st.text(f"chunk {i} preview: {str(r)[:800]}...")
                return
            best = gem.get("best_candidate", {})
            st.subheader("Structured Data Extracted")
            st.json(best)
            render_structured(best)
            st.session_state["extracted"] = gem
            st.session_state["doc_text"] = doc_text
    if "extracted" in st.session_state:
        st.markdown("---")
        st.subheader("Trigger Email via n8n")
        recipient = st.text_input("Recipient Email ID")
        send = st.button("Send Alert Mail")
        if send:
            if not recipient or "@" not in recipient:
                st.error("Enter valid email")
            else:
                webhook = st.secrets.get("N8N_WEBHOOK_URL", "")
                if not webhook:
                    st.error("Missing N8N_WEBHOOK_URL in st.secrets")
                else:
                    payload = {
                        "document_text": st.session_state["doc_text"],
                        "extracted_json": normalize_numbers(redact_sensitive(st.session_state["extracted"])),
                        "question": question,
                        "recipient_email": recipient
                    }
                    with st.spinner("Calling n8n webhook..."):
                        res = call_n8n_webhook(webhook, payload)
                    if "error" in res:
                        st.error(f"n8n call failed: {res['error']}")
                    else:
                        st.subheader("Final Analytical Answer")
                        st.write(res.get("final_answer", ""))
                        st.subheader("Generated Email Body")
                        st.code(res.get("email_body", ""))
                        st.subheader("Email Automation Status")
                        st.info(res.get("automation_status", ""))


if __name__ == "__main__":
    main()
