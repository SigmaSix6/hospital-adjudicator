"use client";

import { Bot, FileSearch, FileText, ScrollText, UserCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import type { Finding } from "@/lib/types";
import { RuleTag, SeverityBadge } from "./status";

export function FindingCard({ finding, onShowEvidence }: { finding: Finding; onShowEvidence: (f: Finding) => void }) {
  const docEvidence = finding.evidence.some((e) => e.file !== "case_manifest.csv");
  return (
    <Card className="gap-3 py-4" id={finding.finding_id}>
      <CardHeader className="gap-2 px-4">
        <div className="flex flex-wrap items-center gap-2">
          <SeverityBadge severity={finding.severity} />
          <RuleTag>{finding.rule_id}</RuleTag>
          <span className="text-xs text-muted-foreground">{finding.category.replaceAll("_", " ")}</span>
          <span className="ml-auto inline-flex items-center gap-1 text-xs text-muted-foreground">
            {finding.basis === "model_judgment" ? (
              <>
                <Bot className="size-3.5" aria-hidden /> Model judgment
                {finding.confidence !== null && <> · confidence {Math.round(finding.confidence * 100)}%</>}
              </>
            ) : (
              <>
                <FileText className="size-3.5" aria-hidden /> Documented fact
              </>
            )}
          </span>
        </div>
        <h3 className="text-base font-semibold leading-snug">{finding.title}</h3>
        <p className="text-sm text-muted-foreground">{finding.description}</p>
        {finding.requires_human_review ? (
          <p className="inline-flex w-fit items-center gap-1.5 rounded-md bg-brand-yellow-subtle px-2 py-1 text-xs font-medium text-brand-navy">
            <UserCheck className="size-3.5" aria-hidden /> Requires human review
          </p>
        ) : (
          <p className="text-xs text-muted-foreground">Informational: does not by itself require review.</p>
        )}
      </CardHeader>
      <CardContent className="space-y-3 px-4">
        <div>
          <div className="mb-1.5 flex items-center justify-between gap-2">
            <h4 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Source evidence</h4>
            {docEvidence && (
              <Button variant="ghost" size="xs" onClick={() => onShowEvidence(finding)}>
                <FileSearch aria-hidden /> Show in documents
              </Button>
            )}
          </div>
          <div className="overflow-x-auto rounded-lg border">
            <table className="w-full text-left text-sm">
              <thead className="bg-muted/60 text-xs text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 font-medium">Document</th>
                  <th className="px-3 py-2 font-medium">Field / section</th>
                  <th className="px-3 py-2 font-medium">Value</th>
                  <th className="hidden px-3 py-2 font-medium md:table-cell">Location</th>
                </tr>
              </thead>
              <tbody>
                {finding.evidence.map((e, i) => (
                  <tr key={i} className="border-t align-top">
                    <td className="px-3 py-2">
                      <div className="font-medium">{e.document_type}</div>
                      <div className="font-mono text-[11px] text-muted-foreground break-all">{e.file}</div>
                    </td>
                    <td className="px-3 py-2">{e.field}</td>
                    <td className="px-3 py-2">
                      {e.value ? (
                        <span className="font-mono text-[13px]">{e.value}</span>
                      ) : (
                        <span className="italic text-error">(blank)</span>
                      )}
                      {e.note && <div className="mt-0.5 text-xs text-muted-foreground">{e.note}</div>}
                    </td>
                    <td className="hidden px-3 py-2 text-xs text-muted-foreground md:table-cell">{e.location}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        <div>
          <h4 className="mb-1.5 text-xs font-semibold tracking-wide text-muted-foreground uppercase">Policy references</h4>
          <ul className="space-y-1.5">
            {finding.policy_refs.map((p, i) => (
              <li key={i} className="flex gap-2 text-sm">
                <ScrollText className="mt-0.5 size-4 shrink-0 text-brand-blue" aria-hidden />
                <div>
                  <span className="font-medium">
                    {p.sop_id} · {p.section}
                  </span>{" "}
                  <span className="text-muted-foreground">({p.title})</span>
                  <blockquote className="mt-0.5 border-l-2 border-brand-yellow pl-2 text-xs text-muted-foreground">
                    {p.excerpt}
                  </blockquote>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </CardContent>
    </Card>
  );
}
