# Data Dictionary

All documents are synthetic `.docx` files. Their visible text and tables are
part of the case evidence.

| Field | Meaning |
|---|---|
| Case ID | Identifier for a patient-case bundle |
| Patient ID | Synthetic identifier expected to match across case documents |
| Patient Name | Synthetic patient name; harmless formatting differences may be normalized |
| Date of Birth | Synthetic date used for identity matching |
| Admission Date | Beginning of the documented encounter |
| Discharge Date | End of the documented encounter |
| Encounter / Study Date | Date of a clinical note, investigation, or procedure |
| Primary Diagnosis | Diagnosis recorded in a summary or claim |
| Claimed Procedure | Procedure submitted for review |
| Physician Signature | Claim-form signature status |
| Findings / Impression | Required radiology or procedure-report evidence where applicable |

Use `case_manifest.csv` to determine which files are present. Blank sections,
missing files, inconsistent values, different clinical wording, and uncertain
diagnoses may be meaningful under the supplied SOPs.
