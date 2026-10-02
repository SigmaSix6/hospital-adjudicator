"""Deterministic validation rules (SOP-01, SOP-02, SOP-04, SOP-05).

Every rule returns findings plus a CheckResult so the response shows what was checked,
not only what failed. Severity policy: `high` only where an SOP explicitly says high
severity; `medium` for other SOP-06 mandatory escalations; `low` for informational
observations that do not by themselves require review.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from .models import CaseBundle, CheckResult, Evidence, ExtractedValue, Finding, ParsedDocument
from .normalize import find_iso_dates, is_blank, norm_id, norm_name, norm_text, parse_date
from .sops import SopRegistry

REGISTRATION = "Patient Registration Form"
PHYSICIAN_NOTE = "Attending Physician Note"
DISCHARGE = "Discharge Summary"
CLAIM = "Claim Submission Form"
REQUIRED_DOCUMENTS = (REGISTRATION, PHYSICIAN_NOTE, DISCHARGE, CLAIM)

REQUIRED_CLAIM_FIELDS = (
    "Patient ID",
    "Patient Name",
    "Date of Birth",
    "Admission Date",
    "Discharge Date",
    "Primary Diagnosis",
    "Attending Physician",
    "Physician Signature",
)
SIGNED_VALUES = {"signed", "yes", "signed electronically", "e-signed"}
UNSIGNED_VALUES = {"not signed", "unsigned", "no", "missing"}
NO_PROCEDURE_VALUES = {"none", "no procedure", "nil"}


@dataclass(frozen=True)
class ProcedureRequirement:
    report_type: str
    sop_section: str
    elements: tuple[tuple[str, tuple[str, ...]], ...]


SOP05_PROCEDURES: dict[str, ProcedureRequirement] = {
    "colonoscopy": ProcedureRequirement(
        "Endoscopy Report",
        "Colonoscopy",
        (("procedure date", ("Procedure Date",)), ("findings", ("Findings",)),
         ("conclusion/impression", ("Conclusion", "Impression", "Conclusion/Impression"))),
    ),
    "ct abdomen with contrast": ProcedureRequirement(
        "Radiology Report",
        "CT abdomen with contrast",
        (("study date", ("Study Date",)), ("findings", ("Findings",)), ("impression", ("Impression",))),
    ),
    "appendectomy": ProcedureRequirement(
        "Operative Report",
        "Appendectomy",
        (("procedure date", ("Procedure Date",)), ("operative findings", ("Operative Findings",)),
         ("surgeon identification", ("Surgeon",))),
    ),
}
PROCEDURE_DATE_FIELDS = ("Study Date", "Procedure Date")


def evidence_for(doc: ParsedDocument, item: ExtractedValue, note: str | None = None) -> Evidence:
    return Evidence(
        document_type=doc.document_type, file=doc.file, field=item.name,
        value=item.value, location=item.location, note=note,
    )


def manifest_evidence(bundle: CaseBundle, note: str) -> Evidence:
    listed = ", ".join(e.document_type for e in bundle.manifest_entries)
    return Evidence(
        document_type="Case Manifest", file="case_manifest.csv", field="document_type",
        value=listed, location=f"rows where case_id = {bundle.case_id}", note=note,
    )


@dataclass
class RuleOutput:
    findings: list[Finding] = field(default_factory=list)
    checks: list[CheckResult] = field(default_factory=list)
    uncertainties: list[str] = field(default_factory=list)

    def extend(self, other: "RuleOutput") -> None:
        self.findings += other.findings
        self.checks += other.checks
        self.uncertainties += other.uncertainties


def _finding(**kwargs) -> Finding:
    kwargs.setdefault("basis", "documented_fact")
    kwargs.setdefault("confidence", 1.0)
    return Finding(finding_id="", **kwargs)


# --------------------------------------------------------------------------- SOP-01


def check_required_documents(bundle: CaseBundle, sops: SopRegistry) -> RuleOutput:
    out = RuleOutput()
    present = {d.document_type for d in bundle.documents}
    missing = [t for t in REQUIRED_DOCUMENTS if t not in present]
    for doc_type in missing:
        out.findings.append(_finding(
            rule_id="SOP-01.R1", category="missing_document", severity="medium",
            title=f"Required document missing: {doc_type}",
            description=(
                f"SOP-01 requires a {doc_type} for every case, but the case manifest has no "
                f"{doc_type} for {bundle.case_id}. Its content was not inferred from other documents."
            ),
            policy_refs=[sops.ref("SOP-01", "Required documents"), sops.ref("SOP-01", "Review action")],
            evidence=[manifest_evidence(bundle, f"No '{doc_type}' row in the manifest")],
            requires_human_review=True,
        ))
    if DISCHARGE in missing:
        out.uncertainties.append(
            "No Discharge Summary: the claim's discharge date and primary diagnosis cannot be "
            "cross-checked against a final clinical record."
        )
    for err in bundle.load_errors:
        out.findings.append(_finding(
            rule_id="SOP-01.R1", category="missing_document", severity="medium",
            title="Manifest document could not be read",
            description=err + " The document is treated as unavailable.",
            policy_refs=[sops.ref("SOP-01", "Review action")],
            evidence=[manifest_evidence(bundle, err)],
            requires_human_review=True,
        ))
    out.checks.append(CheckResult(
        rule_id="SOP-01.R1", sop_id="SOP-01", description="All four core documents are present",
        outcome="issue" if missing or bundle.load_errors else "pass",
        detail=f"Missing: {', '.join(missing)}" if missing else "Registration, physician note, discharge summary and claim present",
    ))
    return out


def check_required_claim_fields(bundle: CaseBundle, sops: SopRegistry) -> RuleOutput:
    out = RuleOutput()
    claim = bundle.get(CLAIM)
    if claim is None:
        out.checks.append(CheckResult(
            rule_id="SOP-01.R2", sop_id="SOP-01", description="Required claim fields are filled",
            outcome="not_applicable", detail="No Claim Submission Form (see SOP-01.R1)",
        ))
        return out
    problems: list[str] = []
    refs = [sops.ref("SOP-01", "Required claim fields"), sops.ref("SOP-01", "Review action")]
    for name in REQUIRED_CLAIM_FIELDS:
        item = claim.field(name)
        if item is None or is_blank(item.value):
            problems.append(name)
            ev = evidence_for(claim, item, "Field is blank") if item else Evidence(
                document_type=claim.document_type, file=claim.file, field=name, value="",
                location="not present in the claim table", note="Field label not found")
            out.findings.append(_finding(
                rule_id="SOP-01.R2", category="missing_field", severity="medium",
                title=f"Required claim field blank: {name}",
                description=(
                    f"The Claim Submission Form's '{name}' is blank. SOP-01 says not to infer "
                    "missing content from another document, so it is flagged rather than filled in."
                ),
                policy_refs=refs, evidence=[ev], requires_human_review=True,
            ))
            continue
        if name == "Physician Signature":
            status = item.value.strip().lower()
            if status in SIGNED_VALUES:
                continue
            problems.append(name)
            unsigned = status in UNSIGNED_VALUES
            out.findings.append(_finding(
                rule_id="SOP-01.R2", category="missing_field" if unsigned else "undetermined",
                severity="medium",
                title="Physician signature missing" if unsigned else "Physician signature status unclear",
                description=(
                    f"The claim records the physician signature as '{item.value}'. A required "
                    "signature that is recorded as absent is treated as a missing required field."
                    if unsigned else
                    f"The signature status '{item.value}' is not a recognised signed/unsigned value."
                ),
                policy_refs=refs, evidence=[evidence_for(claim, item)], requires_human_review=True,
            ))
    out.checks.append(CheckResult(
        rule_id="SOP-01.R2", sop_id="SOP-01", description="Required claim fields are filled",
        outcome="issue" if problems else "pass",
        detail=f"Problem fields: {', '.join(problems)}" if problems else f"{len(REQUIRED_CLAIM_FIELDS)} required fields present",
    ))
    return out


# --------------------------------------------------------------------------- SOP-02


def _collect(bundle: CaseBundle, name: str) -> list[tuple[ParsedDocument, ExtractedValue]]:
    found = []
    for doc in bundle.documents:
        item = doc.field(name)
        if item is not None and not is_blank(item.value):
            found.append((doc, item))
    return found


def _identity_mismatch(
    bundle: CaseBundle, sops: SopRegistry, name: str, rule_id: str, key
) -> RuleOutput:
    out = RuleOutput()
    values = _collect(bundle, name)
    groups: dict[str, list[tuple[ParsedDocument, ExtractedValue]]] = defaultdict(list)
    for doc, item in values:
        groups[key(item.value)].append((doc, item))
    desc = f"{name} matches across documents"
    if len(values) < 2:
        out.checks.append(CheckResult(rule_id=rule_id, sop_id="SOP-02", description=desc,
                                      outcome="undetermined", detail=f"Fewer than two documents carry {name}"))
        out.uncertainties.append(f"{name} appears on fewer than two documents; identity could not be cross-checked.")
        return out
    if len(groups) == 1:
        out.checks.append(CheckResult(rule_id=rule_id, sop_id="SOP-02", description=desc, outcome="pass",
                                      detail=f"Same {name} on {len(values)} documents"))
        return out
    ordered = sorted(groups.values(), key=len, reverse=True)
    majority, minority = ordered[0], [x for g in ordered[1:] for x in g]
    majority_value = majority[0][1].value
    outliers = "; ".join(f"{d.document_type} has '{i.value}'" for d, i in minority)
    out.findings.append(_finding(
        rule_id=rule_id, category="identity_mismatch", severity="high",
        title=f"{name} mismatch across documents",
        description=(
            f"{outliers}, while {len(majority)} other document(s) have '{majority_value}'. "
            f"SOP-02 requires {name} to match exactly; any mismatch is high severity."
        ),
        policy_refs=[sops.ref("SOP-02", "Exact identifiers"), sops.ref("SOP-02", "Escalation")],
        evidence=[evidence_for(d, i) for d, i in minority + majority],
        requires_human_review=True,
    ))
    out.checks.append(CheckResult(rule_id=rule_id, sop_id="SOP-02", description=desc, outcome="issue", detail=outliers))
    return out


def check_identity(bundle: CaseBundle, sops: SopRegistry) -> RuleOutput:
    out = RuleOutput()
    out.extend(_identity_mismatch(bundle, sops, "Patient ID", "SOP-02.R1", norm_id))
    out.extend(_identity_mismatch(
        bundle, sops, "Date of Birth", "SOP-02.R2", lambda v: str(parse_date(v) or v.strip())
    ))

    case_ids = _collect(bundle, "Case ID")
    wrong = [(d, i) for d, i in case_ids if norm_id(i.value) != norm_id(bundle.case_id)]
    if wrong:
        out.findings.append(_finding(
            rule_id="SOP-02.R4", category="identity_mismatch", severity="high",
            title="Document labelled with a different Case ID",
            description="; ".join(f"{d.document_type} is labelled '{i.value}'" for d, i in wrong)
            + f", but the manifest assigns it to {bundle.case_id}. The document may belong to another patient.",
            policy_refs=[sops.ref("SOP-02", "Purpose"), sops.ref("SOP-02", "Escalation")],
            evidence=[evidence_for(d, i) for d, i in wrong], requires_human_review=True,
        ))
    out.checks.append(CheckResult(
        rule_id="SOP-02.R4", sop_id="SOP-02", description="Document Case IDs match the manifest",
        outcome="issue" if wrong else "pass",
        detail=f"{len(case_ids)} documents labelled {bundle.case_id}" if not wrong else "Mismatched Case ID labels",
    ))

    names = _collect(bundle, "Patient Name")
    distinct = {norm_name(i.value) for _, i in names}
    ids_ok = not any(f.rule_id in {"SOP-02.R1", "SOP-02.R2"} for f in out.findings)
    if len(distinct) > 1:
        out.findings.append(_finding(
            rule_id="SOP-02.R3", category="observation" if ids_ok else "identity_mismatch",
            severity="low" if ids_ok else "medium",
            title="Patient name differs after normalisation",
            description=(
                "Names differ beyond case/spacing/punctuation/title. Patient ID and DOB agree, so per "
                "SOP-02 this alone is not treated as a mismatch." if ids_ok else
                "Names differ and an exact identifier also mismatches."
            ),
            policy_refs=[sops.ref("SOP-02", "Names")],
            evidence=[evidence_for(d, i) for d, i in names], requires_human_review=not ids_ok,
        ))
    out.checks.append(CheckResult(
        rule_id="SOP-02.R3", sop_id="SOP-02", description="Patient names agree after normalisation",
        outcome="issue" if len(distinct) > 1 else "pass",
        detail=f"{len(names)} name values, {len(distinct)} distinct after normalisation",
    ))
    return out


# --------------------------------------------------------------------------- SOP-04


def stay_window(bundle: CaseBundle) -> tuple[date | None, date | None, ParsedDocument | None]:
    for doc_type in (DISCHARGE, CLAIM):
        doc = bundle.get(doc_type)
        if doc is None:
            continue
        adm = doc.field("Admission Date")
        dis = doc.field("Discharge Date")
        a = parse_date(adm.value) if adm else None
        d = parse_date(dis.value) if dis else None
        if a and d:
            return a, d, doc
    return None, None, None


def check_dates(bundle: CaseBundle, sops: SopRegistry) -> RuleOutput:
    out = RuleOutput()
    reversed_evidence: list[Evidence] = []
    unparseable: list[str] = []
    pairs = 0
    for doc in bundle.documents:
        adm, dis = doc.field("Admission Date"), doc.field("Discharge Date")
        if adm is None or dis is None or is_blank(adm.value) or is_blank(dis.value):
            continue
        a, d = parse_date(adm.value), parse_date(dis.value)
        if a is None or d is None:
            unparseable.append(doc.document_type)
            continue
        pairs += 1
        if d < a:
            reversed_evidence += [evidence_for(doc, adm), evidence_for(doc, dis, "Earlier than admission")]
    if reversed_evidence:
        docs = sorted({e.document_type for e in reversed_evidence})
        out.findings.append(_finding(
            rule_id="SOP-04.R1", category="date_inconsistency", severity="high",
            title="Discharge date is before admission date",
            description=f"Discharge precedes admission on: {', '.join(docs)}. SOP-04 classes this as high severity.",
            policy_refs=[sops.ref("SOP-04", "Admission/discharge rule"), sops.ref("SOP-04", "Severity")],
            evidence=reversed_evidence, requires_human_review=True,
        ))
    if unparseable:
        out.uncertainties.append(f"Unparseable admission/discharge dates on: {', '.join(unparseable)}.")
    out.checks.append(CheckResult(
        rule_id="SOP-04.R1", sop_id="SOP-04", description="Discharge date is on or after admission date",
        outcome="issue" if reversed_evidence else ("pass" if pairs else "undetermined"),
        detail=f"{pairs} document(s) with both dates checked",
    ))

    # Cross-document agreement of encounter dates (interpretation of "chronological consistency").
    for name in ("Admission Date", "Discharge Date"):
        vals = [(d, i) for d, i in _collect(bundle, name)]
        distinct = {str(parse_date(i.value) or i.value.strip()) for _, i in vals}
        if len(distinct) > 1:
            out.findings.append(_finding(
                rule_id="SOP-04.R3", category="date_inconsistency", severity="medium",
                title=f"{name} differs between documents",
                description=f"Documents disagree on {name}: " + "; ".join(f"{d.document_type} '{i.value}'" for d, i in vals),
                policy_refs=[sops.ref("SOP-04", "Purpose")],
                evidence=[evidence_for(d, i) for d, i in vals], requires_human_review=True,
            ))
        out.checks.append(CheckResult(
            rule_id="SOP-04.R3", sop_id="SOP-04", description=f"{name} agrees across documents",
            outcome="issue" if len(distinct) > 1 else ("pass" if len(vals) > 1 else "not_applicable"),
            detail=f"{len(vals)} document(s) carry {name}",
        ))

    adm, dis, window_doc = stay_window(bundle)
    procedure_dates: list[tuple[ParsedDocument, ExtractedValue, date]] = []
    for doc in bundle.documents:
        for name in PROCEDURE_DATE_FIELDS:
            item = doc.field(name)
            if item and (d := parse_date(item.value)):
                procedure_dates.append((doc, item, d))
        section = doc.section("Procedure / Investigation")
        if section and "performed" in section.value.lower():
            for d in find_iso_dates(section.value):
                procedure_dates.append((doc, section, d))
    if not procedure_dates:
        out.checks.append(CheckResult(rule_id="SOP-04.R2", sop_id="SOP-04", description="Procedure dates fall within the stay",
                                      outcome="not_applicable", detail="No dated procedure documented"))
    elif adm is None or dis is None or dis < adm:
        out.checks.append(CheckResult(rule_id="SOP-04.R2", sop_id="SOP-04", description="Procedure dates fall within the stay",
                                      outcome="undetermined", detail="No valid admission-to-discharge window to compare against"))
        out.uncertainties.append("Procedure dates could not be validated because the stay window is invalid or missing.")
    else:
        outside = [(doc, item, d) for doc, item, d in procedure_dates if not adm <= d <= dis]
        for doc, item, d in outside:
            out.findings.append(_finding(
                rule_id="SOP-04.R2", category="date_inconsistency", severity="medium",
                title="Procedure date outside the admission period",
                description=(
                    f"{doc.document_type} dates a procedure on {d.isoformat()}, outside the stay "
                    f"{adm.isoformat()} to {dis.isoformat()} (from the {window_doc.document_type}). "
                    "No explanation was detected; a reviewer should confirm whether a note explains it."
                ),
                policy_refs=[sops.ref("SOP-04", "Procedure date rule")],
                evidence=[evidence_for(doc, item)], requires_human_review=True,
            ))
        out.checks.append(CheckResult(
            rule_id="SOP-04.R2", sop_id="SOP-04", description="Procedure dates fall within the stay",
            outcome="issue" if outside else "pass",
            detail=f"{len(procedure_dates)} procedure date(s) checked against {adm} to {dis}",
        ))
    return out


# --------------------------------------------------------------------------- SOP-05


def match_procedure(claimed: str) -> str | None:
    text = norm_text(claimed)
    return next((key for key in SOP05_PROCEDURES if key in text), None)


def check_procedure_support(bundle: CaseBundle, sops: SopRegistry) -> RuleOutput:
    out = RuleOutput()
    claim = bundle.get(CLAIM)
    item = claim.field("Claimed Procedure") if claim else None
    desc = "Claimed procedure has its SOP-05 supporting report"
    if item is None or is_blank(item.value) or item.value.strip().lower() in NO_PROCEDURE_VALUES:
        out.checks.append(CheckResult(rule_id="SOP-05.R1", sop_id="SOP-05", description=desc,
                                      outcome="not_applicable", detail="No procedure claimed"))
        return out
    key = match_procedure(item.value)
    if key is None:
        out.checks.append(CheckResult(rule_id="SOP-05.R1", sop_id="SOP-05", description=desc, outcome="not_applicable",
                                      detail=f"'{item.value}' is not a procedure listed in SOP-05"))
        return out
    req = SOP05_PROCEDURES[key]
    report = bundle.get(req.report_type)
    refs = [sops.ref("SOP-05", req.sop_section)]
    if report is None:
        out.findings.append(_finding(
            rule_id="SOP-05.R1", category="missing_document", severity="high",
            title=f"{req.report_type} missing for claimed {item.value}",
            description=(
                f"The claim includes '{item.value}', which SOP-05 says requires a {req.report_type}. "
                "No such report is in the case manifest. SOP-05 classes a missing required report as high severity."
            ),
            policy_refs=refs + [sops.ref("SOP-05", "Missing report"), sops.ref("SOP-01", "Procedure-specific support")],
            evidence=[evidence_for(claim, item), manifest_evidence(bundle, f"No '{req.report_type}' row in the manifest")],
            requires_human_review=True,
        ))
        out.checks.append(CheckResult(rule_id="SOP-05.R1", sop_id="SOP-05", description=desc, outcome="issue",
                                      detail=f"{req.report_type} absent"))
        return out
    out.checks.append(CheckResult(rule_id="SOP-05.R1", sop_id="SOP-05", description=desc, outcome="pass",
                                  detail=f"{req.report_type} present"))

    incomplete: list[str] = []
    for label, candidates in req.elements:
        found = next((v for c in candidates if (v := report.lookup(c)) is not None), None)
        if found is not None and not is_blank(found.value):
            continue
        incomplete.append(label)
        ev = evidence_for(report, found, "Section heading present but has no content") if found else Evidence(
            document_type=report.document_type, file=report.file, field=candidates[0], value="",
            location="not present in the report", note="Required element not found")
        out.findings.append(_finding(
            rule_id="SOP-05.R2", category="incomplete_report", severity="medium",
            title=f"{req.report_type} incomplete: {label} is blank",
            description=(
                f"The {req.report_type} supporting '{item.value}' exists, but its required "
                f"'{label}' is blank or absent. The missing section was not inferred."
            ),
            policy_refs=refs + [sops.ref("SOP-05", "Incomplete report")],
            evidence=[ev], requires_human_review=True,
        ))
    out.checks.append(CheckResult(
        rule_id="SOP-05.R2", sop_id="SOP-05", description=f"{req.report_type} has all required sections",
        outcome="issue" if incomplete else "pass",
        detail=f"Blank/absent: {', '.join(incomplete)}" if incomplete else "All required sections filled",
    ))
    return out


def run_deterministic_rules(bundle: CaseBundle, sops: SopRegistry) -> RuleOutput:
    out = RuleOutput()
    for rule in (check_required_documents, check_required_claim_fields, check_identity,
                 check_dates, check_procedure_support):
        out.extend(rule(bundle, sops))
    return out
