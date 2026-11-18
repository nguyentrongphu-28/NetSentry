import { useQuery, UseQueryResult } from "@tanstack/react-query";
import { getAuditRun } from "../services/auditsApi";
import { AuditRunDetailOut } from "../types/api";

export function useAuditRun(
  runId: number | undefined
): UseQueryResult<AuditRunDetailOut, Error> {
  return useQuery<AuditRunDetailOut, Error>({
    queryKey: ["audit-run", runId],
    queryFn: () => {
      if (runId === undefined || isNaN(runId)) {
        throw new Error("Mã lượt audit không hợp lệ.");
      }
      return getAuditRun(runId);
    },
    enabled: runId !== undefined && !isNaN(runId),
  });
}
