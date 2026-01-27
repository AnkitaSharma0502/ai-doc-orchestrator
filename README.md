


# AI-Powered Document Orchestrator
Document processing system using Python, Gemini AI, and n8n for intelligent text extraction and risk-based email alerting

🔗 Link:
https://ai-doc-orchestrator-p53cg75jnaovj4kdbf3tpv.streamlit.app/

## Problem Statement

Organizations deal with many documents such as statements, reports, and forms.
Manually reading each document to identify key details and check for sensitive or risky content is slow and inefficient.

The goal of this project is to:

Extract structured data from documents using Gemini AI
Assess risk levels with confidence scores
Integrate with n8n to send email alerts for high-risk documents
Provide a user-friendly interface for document analysis

## Approach:

Accepts PDF or TXT documents through a Streamlit interface

Extracts text using pdfplumber, PyMuPDF, and OCR (pytesseract) as fallback

Sends the text to Gemini AI for structured extraction (summary, key fields, confidence, risk level)

Displays the extracted data clearly in the UI

Sends the result to n8n via webhook

n8n evaluates conditions and triggers an email workflow if required

The focus was on building a practical, understandable automation pipeline rather than a complex system.

## Key Features:

Upload and process PDF / TXT files(200 MB)

Automatic text extraction with fallback OCR

Structured data extraction using Gemini AI

Identification of risk level and confidence score

Redaction of sensitive fields before sending data

Conditional email automation using n8n

## Workflow:

User uploads a document in the Streamlit app

Text is extracted from the file

Gemini AI processes the text and returns:

- Summary

- Key fields

- Confidence score

- Risk level

- Extracted data is normalized and sensitive values are masked

- Data is sent to n8n via webhook

- n8n checks conditions using If node

- If condition is met → email is sent

- If not → workflow ends with response to webhook

## Tech Stack:

Frontend: Streamlit

Backend: Python

AI Model: Gemini

Automation: n8n

OCR: pytesseract

PDF Processing: pdfplumber, PyMuPDF

# n8n Workflow Overview:

Webhook node – receives data from Streamlit

Edit Fields – formats incoming data

Message a Model – processes content

Store Analysis – saves result

If condition – checks risk / condition

Send Message (Gmail) – sends email if condition is true

Respond to Webhook – returns final status

This allows conditional automation without manual intervention.

<img width="1676" height="706" alt="image" src="https://github.com/user-attachments/assets/3ebff7f7-519c-479f-af0d-abb4187b88f0" />

<img width="1875" height="718" alt="image" src="https://github.com/user-attachments/assets/63ed8004-07c0-4004-8b5a-8b2e7df0c3e3" />





