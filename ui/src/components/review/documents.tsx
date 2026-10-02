"use client";

import { FileText, Highlighter } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { ExtractedValue, ParsedDocument } from "@/lib/types";

export const evidenceKey = (file: string, field: string) => `${file}::${field.trim().toLowerCase()}`;

function Row({ item, file, highlighted }: { item: ExtractedValue; file: string; highlighted: Set<string> }) {
  const hit = highlighted.has(evidenceKey(file, item.name));
  return (
    <tr className={cn("border-t align-top", hit && "bg-brand-yellow-subtle")} data-evidence={hit || undefined}>
      <th scope="row" className="w-1/3 px-3 py-1.5 text-left font-medium text-muted-foreground">
        <span className="inline-flex items-center gap-1">
          {hit && <Highlighter className="size-3.5 text-brand-navy" aria-label="Cited as evidence" />}
          {item.name}
        </span>
      </th>
      <td className="px-3 py-1.5">
        {item.value ? item.value : <span className="italic text-error">(blank)</span>}
      </td>
    </tr>
  );
}

export function DocumentsView({ documents, highlighted }: { documents: ParsedDocument[]; highlighted: Set<string> }) {
  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
      {documents.map((doc) => (
        <Card key={doc.file} className="gap-3 py-4">
          <CardHeader className="px-4">
            <CardTitle className="flex items-center gap-2 text-base">
              <FileText className="size-4 text-brand-blue" aria-hidden />
              {doc.document_type}
            </CardTitle>
            <p className="font-mono text-[11px] text-muted-foreground break-all">
              {doc.file} · sha256 {doc.sha256.slice(0, 12)}
            </p>
          </CardHeader>
          <CardContent className="space-y-3 px-4">
            <div className="overflow-hidden rounded-lg border">
              <table className="w-full text-sm">
                <caption className="bg-muted/60 px-3 py-1.5 text-left text-xs font-medium text-muted-foreground">
                  Table fields
                </caption>
                <tbody>
                  {doc.fields.map((f) => (
                    <Row key={f.location} item={f} file={doc.file} highlighted={highlighted} />
                  ))}
                </tbody>
              </table>
            </div>
            {doc.sections.length > 0 && (
              <div className="overflow-hidden rounded-lg border">
                <table className="w-full text-sm">
                  <caption className="bg-muted/60 px-3 py-1.5 text-left text-xs font-medium text-muted-foreground">
                    Narrative sections
                  </caption>
                  <tbody>
                    {doc.sections.map((s) => (
                      <Row key={s.location} item={s} file={doc.file} highlighted={highlighted} />
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
