// SnapshotList.tsx – List snapshots for a device and allow selecting two for diff
// SnapshotList.tsx – List snapshots for a device and allow selecting two for diff
import React, { useState } from "react";
import { Box, Text, Spinner, Alert, AlertIcon, Button, Badge } from "@chakra-ui/react";
import { useQuery } from "@tanstack/react-query";
import { listDeviceSnapshots } from "../../services/auditsApi";
import { DiffViewer } from "./DiffViewer";

interface SnapshotMeta {
  id: number;
  run_id: number;
  created_at: string;
  size_bytes: number;
  line_count: number;
}

interface Props {
  deviceId: string;
}

export const SnapshotList: React.FC<Props> = ({ deviceId }) => {
  const { data: snapshots, isLoading, error } = useQuery<SnapshotMeta[], Error>(
    ["snapshots", deviceId],
    () => listDeviceSnapshots(deviceId),
    { staleTime: Infinity }
  );

  const [first, setFirst] = useState<SnapshotMeta | null>(null);
  const [second, setSecond] = useState<SnapshotMeta | null>(null);

  if (isLoading) {
    return <Spinner size="sm" />;
  }
  if (error) {
    return (
      <Alert status="error" variant="left-accent"><AlertIcon />{error.message}</Alert>
    );
  }
  if (!snapshots?.length) {
    return <Text>Chưa có snapshot nào.</Text>;
  }

  return (
    <Box>
      <Box className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
        {snapshots.map(s => (
          <Box key={s.id} border="1px" borderColor="gray.200" rounded="md" p={3}>
            <Text fontSize="sm" fontWeight="medium">Run #{s.run_id}</Text>
            <Text fontSize="xs" color="gray.600">{new Date(s.created_at).toLocaleString()}</Text>
            <Box mt={2} flexWrap="wrap" display="flex" gap={2}>
              <Button size="xs" onClick={() => setFirst(s)} isDisabled={second?.id === s.id}>Select 1</Button>
              <Button size="xs" onClick={() => setSecond(s)} isDisabled={first?.id === s.id}>Select 2</Button>
            </Box>
          </Box>
        ))}
      </Box>
      {first && second && (
        <Box mt={4} border="1px" borderColor="gray.300" rounded="md" p={3}>
          <Badge colorScheme="green" mb={2}>Diff between Run {first.run_id} &amp; {second.run_id}</Badge>
          <DiffViewer deviceId={deviceId} fromRun={first.run_id} toRun={second.run_id} />
        </Box>
      )}
    </Box>
  );
};

import { Box, Text, Spinner, Alert, AlertIcon, Button, Badge } from "@chakra-ui/react";
import { useQuery } from "@tanstack/react-query";
import { listDeviceSnapshots, getSnapshotContent } from "../../services/auditsApi";
import { DiffViewer } from "./DiffViewer";
import { STRINGS } from "../../i18n/strings";

interface SnapshotMeta {
  id: number;
  run_id: number;
  created_at: string;
  size_bytes: number;
  line_count: number;
}

interface Props {
  deviceId: string;
}

export const SnapshotList: React.FC<Props> = ({ deviceId }) => {
  const { data: snapshots, isLoading, error } = useQuery<SnapshotMeta[], Error>(
    ["snapshots", deviceId],
    () => listDeviceSnapshots(deviceId),
    { staleTime: Infinity }
  );

  const [first, setFirst] = useState<SnapshotMeta | null>(null);
  const [second, setSecond] = useState<SnapshotMeta | null>(null);

  if (isLoading) {
    return <Spinner size="sm" />;
  }
  if (error) {
    return (
      <Alert status="error" variant="left-accent"><AlertIcon />{error.message}</Alert>
    );
  }
  if (!snapshots?.length) {
    return <Text>Chưa có snapshot nào.</Text>;
  }

  return (
    <Box>
      <Box className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
        {snapshots.map(s => (
          <Box key={s.id} border="1px" borderColor="gray.200" rounded="md" p={3}>
            <Text fontSize="sm" fontWeight="medium">Run #{s.run_id}</Text>
            <Text fontSize="xs" color="gray.600">{new Date(s.created_at).toLocaleString()}</Text>
            <Box mt={2} flexWrap="wrap" display="flex" gap={2}>
              <Button size="xs" onClick={() => setFirst(s)} isDisabled={second?.id === s.id}>Select 1</Button>
              <Button size="xs" onClick={() => setSecond(s)} isDisabled={first?.id === s.id}>Select 2</Button>
            </Box>
          </Box>
        ))}
      </Box>
      {first && second && (
        <Box mt={4} border="1px" borderColor="gray.300" rounded="md" p={3}>
          <Badge colorScheme="green" mb={2}>Diff between Run {first.run_id} &amp; {second.run_id}</Badge>
          <DiffViewer deviceId={deviceId} fromRun={first.run_id} toRun={second.run_id} />
        </Box>
      )}
    </Box>
  );
};
