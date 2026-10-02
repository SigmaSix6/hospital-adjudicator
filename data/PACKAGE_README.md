# Clinical Document Review Assistant - Candidate Package

This package contains synthetic data for the Senior AI Engineer (LLM) take-home
test. No real patient data is included.

## Package contents

- `patient_cases/CASE-001` through `CASE-010`: synthetic `.docx` case documents
- `policies_sops/`: review policies and validation guidance
- `case_manifest.csv`: one row per supplied case document
- `data_dictionary.md`: common document and field definitions
- `docs/requirement-analysis.md`: example requirement-gathering format
- `docs/architecture.md`: example architecture format with a Mermaid starter diagram
- `docs/cost-summary.md`: example per-LLM-call usage and cost format

Some cases intentionally contain missing, inconsistent, ambiguous, or incomplete
information. Rely on the supplied evidence and SOPs rather than assuming every
difference is an error.

## Required product interface

Build an API-based review service. The API must accept or identify one patient
case, process its document set, and return a structured JSON review result. A
chatbot, web application, or polished frontend is not required. A CLI may be
included as a helper, but it is not a substitute for the API.

## Documentation deliverables

The three files under `docs/` are example formats. You may adapt them or replace
them with another format that communicates your reasoning more clearly.

Your submission must still include:

1. requirement analysis covering requirement gathering, ambiguities, assumptions,
   scope, and success criteria;
2. architecture documentation containing a valid Mermaid architecture diagram;
3. a cost summary with one record for every LLM call, plus per-case and overall
   totals and the pricing source/calculation method.

The Mermaid diagram is mandatory regardless of the surrounding document format.

Automated test files and a standalone evaluation folder are not required.
Include clear setup and run instructions so reviewers can exercise the API with
the supplied cases. Do not commit API keys or secrets.
