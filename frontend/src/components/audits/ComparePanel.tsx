// ComparePanel.tsx – UI panel to show config diff between the latest audit run and the previous one.
import React from "react";
import { Box, Text, Spinner, Alert, AlertIcon } from "@chakra-ui/react";
import { useQuery } from "@tanstack/react-query";
import { fetchConfigDiff } from "../../services/auditsApi";

interface DiffLine {
  op: " " | "+" | "-";
  text: string;
}

interface DiffHunk {
  oldStart: number;
  newStart: number;
  lines: DiffLine[];
}

interface ConfigDiff {
  fromRunId: number;
  toRunId: number;
  identical: boolean;
  added: number;
  removed: number;
  hunks: DiffHunk[];
  truncated: boolean;
}

interface Props {
  deviceId: string;
  currentRunId: number;
}

export const ComparePanel: React.FC<Props> = ({ deviceId, currentRunId }) => {
  const { data: diff, isLoading, error } = useQuery<ConfigDiff, Error>(
    ["configDiff", deviceId, currentRunId],
    () => fetchConfigDiff(deviceId, currentRunId),
    { staleTime: Infinity }
  );

  if (isLoading) {
    return (
      <Box p={4} textAlign="center">
        <Spinner />
      </Box>
    );
  }

  if (error) {
    return (
      <Alert status="error" variant="left-accent" my={2}>
        <AlertIcon />
        {error.message}
      </Alert>
    );
  }

  if (!diff) {
    return (
      <Text my={2}>Chưa có lần audit trước để so sánh.</Text>
    );
  }

  if (diff.identical) {
    return (
      <Text my={2}>Cấu hình không có thay đổi so với lần trước.</Text>
    );
  }

  return (
    <Box py={2}>
      {diff.truncated && (
        <Alert status="warning" variant="subtle" my={2}>
          <AlertIcon />
          Kết quả diff đã cắt bớt (giới hạn 2000 dòng).
        </Alert>
      )}
      {diff.hunks.map((hunk, idx) => (
        <Box key={idx} fontFamily="monospace" whiteSpace="pre" my={1}>
          {hunk.lines.map((line, i) => (
            <Text key={i} as="span" color={
              line.op === "+" ? "green.600" : line.op === "-" ? "red.600" : "gray.600"
            }>
              {line.op}{line.text}\n            </Text>
          ))}
        </Box>
      ))}
    </Box>
  );
};

import { Box, Text, Spinner, Alert, AlertIcon, Button } from "@chakra-ui/react";
import { useQuery } from "@tanstack/react-query";
import { fetchConfigDiff } from "../../services/auditsApi"; // API wrapper (to be added)

interface DiffLine {
  op: " " | "+" | "-";
  text: string;
}

interface DiffHunk {
  oldStart: number;
  newStart: number;
  lines: DiffLine[];
}

interface ConfigDiff {
  fromRunId: number;
  toRunId: number;
  identical: boolean;
  added: number;
  removed: number;
  hunks: DiffHunk[];
  truncated: boolean;
}

interface Props {
  deviceId: string;
  currentRunId: number;
}

export const ComparePanel: React.FC<Props> = ({ deviceId, currentRunId }) => {
  const [diff, setDiff] = useState<ConfigDiff | null>(null);
  const { data, isLoading, error } = useQuery<ConfigDiff, Error>(
    ["configDiff", deviceId, currentRunId],
    () => fetchConfigDiff(deviceId, currentRunId),
    { staleTime: Infinity }
  );

  useEffect(() => {
    if (data) {
      setDiff(data);
    }
  }, [data]);

  if (isLoading) {
    return (
      <Box p={4} textAlign="center">
        <Spinner />
      </Box>
    );
  }

  if (error) {
    return (
      <Alert status="error" variant="left-accent" my={2}>
        <AlertIcon />
        {error.message}
      </Alert>
    );
  }

  if (!diff) {
    return (
      <Text my={2}>Chưa có lần audit trước để so sánh.</Text>
    );
  }

  if (diff.identical) {
    return (
      <Text my={2}>Cấu hình không có thay đổi so với lần trước.</Text>
    );
  }

  return (
    <Box py={2}>
      {diff.truncated && (
        <Alert status="warning" variant="subtle" my={2}>
          <AlertIcon />
          Kết quả diff đã cắt bớt (giới hạn 2000 dòng).
        </Alert>
      )}
      {diff.hunks.map((hunk, idx) => (
        <Box key={idx} fontFamily="monospace" whiteSpace="pre" my={1}>
          {hunk.lines.map((line, i) => (
            <Text key={i} as="span" color={
              line.op === "+" ? "green.600" : line.op === "-" ? "red.600" : "gray.600"
            }>
              {line.op}{line.text}\n            </Text>
          ))}
        </Box>
      ))}
    </Box>
  );
};
