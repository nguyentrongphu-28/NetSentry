import { useQuery, UseQueryResult } from "@tanstack/react-query";
import { listDevices } from "../services/devicesApi";
import { DeviceListOut } from "../types/api";

export const DEVICES_QUERY_KEY = ["devices"];

export function useDevices(): UseQueryResult<DeviceListOut, Error> {
  return useQuery<DeviceListOut, Error>({
    queryKey: DEVICES_QUERY_KEY,
    queryFn: listDevices,
  });
}
