import { useMutation, useQueryClient, UseMutationResult } from "@tanstack/react-query";
import { createDevice } from "../services/devicesApi";
import { DeviceCreatePayload, DeviceOut } from "../types/api";
import { DEVICES_QUERY_KEY } from "./useDevices";

export function useCreateDevice(): UseMutationResult<DeviceOut, Error, DeviceCreatePayload> {
  const queryClient = useQueryClient();

  return useMutation<DeviceOut, Error, DeviceCreatePayload>({
    mutationFn: createDevice,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: DEVICES_QUERY_KEY });
    },
  });
}
