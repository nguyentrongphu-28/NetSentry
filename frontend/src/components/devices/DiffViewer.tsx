// DiffViewer.tsx – Show unified diff between two snapshots using API
import React from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchConfigDiff } from "../../services/auditsApi";
import { Box, Text, Spinner, Alert, AlertIcon } from "@chakra-ui/react";
import { STRINGS } from "../../i18n/strings";

type DiffLine = { op: " " | "+" | "-"; text: string };

type DiffHunk = { oldStart: number; newStart: number; lines: DiffLine[] };

type ConfigDiff = {
  fromRunId: number;
  toRunId: number;
  identical: boolean;
  added: number;
  removed: number;
  hunks: DiffHunk[];
  truncated: boolean;
};

interface Props {
  deviceId: string;
  fromRun: number;
  toRun: number;
}

export const DiffViewer: React.FC<Props> = ({ deviceId, fromRun, toRun }) => {
  const { data, isLoading, error } = useQuery<ConfigDiff, Error>(
    ["configDiff", deviceId, fromRun, toRun],
    () => fetchConfigDiff(deviceId, toRun),
    { staleTime: Infinity }
  );

  if (isLoading) return <Spinner size="sm" />;
  if (error) return <Alert status="error" variant="left-accent"><AlertIcon />{error.message}</Alert>;
  if (!data) return null;

  if (data.identical) {
    return <Text>Không có thay đổi giữa hai lần audit.</Text>;
  }

  return (
    <Box fontFamily="monospace" whiteSpace="pre" overflowX="auto">
      {data.truncated && (
        <Alert status="warning" variant="subtle" my={2}><AlertIcon />{STRINGS.diff.truncated}</Alert>
      )}
      {data.hunks.map((h, i) => (
        <Box key={i}>
          {h.lines.map((ln, idx) => (
            <Text key={idx} as="span" color={ln.op === "+" ? "green.600" : ln.op === "-" ? "red.600" : "gray.600"}>
              {ln.op}{ln.text}\n            </Text>
          ))}
        </Box>
      ))}
    </Box>
  );
};
