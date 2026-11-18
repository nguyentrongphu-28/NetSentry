import { useQuery, UseQueryResult } from "@tanstack/react-query";
import { listDeviceAudits } from "../services/auditsApi";
import { AuditRunListOut } from "../types/api";

export function useAuditRuns(
  deviceId: string | undefined,
  limit = 20,
  offset = 0
): UseQueryResult<AuditRunListOut, Error> {
  return useQuery<AuditRunListOut, Error>({
    queryKey: ["device-audits", deviceId, limit, offset],
    queryFn: () => {
      if (!deviceId) throw new Error("Mã thiết bị không hợp lệ.");
      return listDeviceAudits(deviceId, limit, offset);
    },
    enabled: Boolean(deviceId),
  });
}
