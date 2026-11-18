import { useMutation, useQueryClient, UseMutationResult } from "@tanstack/react-query";
import { deleteDevice } from "../services/devicesApi";
import { DEVICES_QUERY_KEY } from "./useDevices";

export function useDeleteDevice(): UseMutationResult<void, Error, string> {
  const queryClient = useQueryClient();

  return useMutation<void, Error, string>({
    mutationFn: deleteDevice,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: DEVICES_QUERY_KEY });
    },
  });
}
