import React, { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { FindingOut } from "../../types/api";
import { FindingRow } from "./FindingRow";
import { FINDING_STATUS_ORDER, SEVERITY_ORDER } from "../../utils/format";
import { STRINGS } from "../../i18n/strings";
import { getRemediationTemplates } from "../../services/remediationApi";

export interface FindingsTableProps {
  findings: FindingOut[];
  runId?: number;
}

export function FindingsTable({ findings, runId }: FindingsTableProps): React.JSX.Element {
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [severityFilter, setSeverityFilter] = useState<string>("ALL");

  const { data: templatesData } = useQuery({
    queryKey: ["remediation-templates"],
    queryFn: getRemediationTemplates,
    staleTime: 5 * 60 * 1000,
  });

  const filteredAndSortedFindings = useMemo(() => {
    return [...findings]
      .filter((f) => {
        if (statusFilter !== "ALL" && f.status !== statusFilter) return false;
        if (severityFilter !== "ALL" && f.severity !== severityFilter) return false;
        return true;
      })
      .sort((a, b) => {
        // 1. Status: FAIL > UNKNOWN > PASS
        const statusDiff =
          (FINDING_STATUS_ORDER[b.status] || 0) - (FINDING_STATUS_ORDER[a.status] || 0);
        if (statusDiff !== 0) return statusDiff;

        // 2. Severity: CRITICAL > HIGH > MEDIUM > LOW > INFO
        const severityDiff =
          (SEVERITY_ORDER[b.severity] || 0) - (SEVERITY_ORDER[a.severity] || 0);
        if (severityDiff !== 0) return severityDiff;

        // 3. rule_id alphabetical
        return a.rule_id.localeCompare(b.rule_id);
      });
  }, [findings, statusFilter, severityFilter]);

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-xs overflow-hidden">
      {/* Header and Filters Bar */}
      <div className="px-6 py-4 border-b border-gray-100 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 bg-gray-50/50">
        <div>
          <h2 className="text-base font-semibold text-gray-900">
            {STRINGS.auditDetail.findingsTitle}
          </h2>
          <p className="text-xs text-gray-500 mt-0.5">
            Tổng cộng {findings.length} quy tắc được đánh giá
          </p>
        </div>

        {/* Filters */}
        <div className="flex items-center space-x-3">
          {/* Status filter */}
          <div>
            <label htmlFor="filter-status" className="sr-only">
              {STRINGS.auditDetail.filterStatus}
            </label>
            <select
              id="filter-status"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="text-xs border border-gray-300 rounded-md px-2.5 py-1.5 bg-white text-gray-700 shadow-xs focus:outline-none focus:ring-1 focus:ring-indigo-500"
            >
              <option value="ALL">{STRINGS.auditDetail.filterStatus}: {STRINGS.auditDetail.all}</option>
              <option value="FAIL">FAIL</option>
              <option value="UNKNOWN">UNKNOWN</option>
              <option value="PASS">PASS</option>
            </select>
          </div>

          {/* Severity filter */}
          <div>
            <label htmlFor="filter-severity" className="sr-only">
              {STRINGS.auditDetail.filterSeverity}
            </label>
            <select
              id="filter-severity"
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              className="text-xs border border-gray-300 rounded-md px-2.5 py-1.5 bg-white text-gray-700 shadow-xs focus:outline-none focus:ring-1 focus:ring-indigo-500"
            >
              <option value="ALL">{STRINGS.auditDetail.filterSeverity}: {STRINGS.auditDetail.all}</option>
              <option value="CRITICAL">CRITICAL</option>
              <option value="HIGH">HIGH</option>
              <option value="MEDIUM">MEDIUM</option>
              <option value="LOW">LOW</option>
              <option value="INFO">INFO</option>
            </select>
          </div>
        </div>
      </div>

      {/* Table / List */}
      {filteredAndSortedFindings.length === 0 ? (
        <div className="py-12 text-center text-sm text-gray-500">
          {STRINGS.auditDetail.noFindingsMatch}
        </div>
      ) : (
        <div className="divide-y divide-gray-100">
          {filteredAndSortedFindings.map((finding) => {
            const template = templatesData?.templates?.find((t) => t.rule_id === finding.rule_id);
            const manualGuidance = templatesData?.manual_guidance?.find((g) => g.rule_id === finding.rule_id);
            return (
              <FindingRow
                key={finding.rule_id}
                finding={finding}
                runId={runId}
                template={template}
                manualGuidance={manualGuidance}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}
