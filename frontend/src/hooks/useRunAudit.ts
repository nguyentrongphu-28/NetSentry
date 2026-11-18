import { useMutation, useQueryClient, UseMutationResult } from "@tanstack/react-query";
import { runDeviceAudit } from "../services/auditsApi";
import { AuditRequestPayload, AuditRunDetailOut } from "../types/api";
import { DEVICES_QUERY_KEY } from "./useDevices";

export interface RunAuditVariables {
  deviceId: string;
  payload: AuditRequestPayload;
}

export function useRunAudit(): UseMutationResult<
  AuditRunDetailOut,
  Error,
  RunAuditVariables
> {
  const queryClient = useQueryClient();

  return useMutation<AuditRunDetailOut, Error, RunAuditVariables>({
    mutationFn: ({ deviceId, payload }) => runDeviceAudit(deviceId, payload),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: DEVICES_QUERY_KEY });
      queryClient.invalidateQueries({ queryKey: ["device", variables.deviceId] });
      queryClient.invalidateQueries({ queryKey: ["device-audits", variables.deviceId] });
    },
  });
}
