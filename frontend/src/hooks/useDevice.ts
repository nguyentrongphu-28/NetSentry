import { useQuery, UseQueryResult } from "@tanstack/react-query";
import { getDevice } from "../services/devicesApi";
import { DeviceWithLatestAuditOut } from "../types/api";

export function useDevice(
  deviceId: string | undefined
): UseQueryResult<DeviceWithLatestAuditOut, Error> {
  return useQuery<DeviceWithLatestAuditOut, Error>({
    queryKey: ["device", deviceId],
    queryFn: () => {
      if (!deviceId) throw new Error("Mã thiết bị không hợp lệ.");
      return getDevice(deviceId);
    },
    enabled: Boolean(deviceId),
  });
}
