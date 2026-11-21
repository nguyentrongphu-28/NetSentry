// AiExplainPanel.tsx – UI panel to request and display AI explanation for an audit run.
// AiExplainPanel.tsx – UI panel to request and display AI explanation for an audit run.
import React, { useState } from "react";
import { Box, Text, Spinner, Alert, AlertIcon, Button, Badge } from "@chakra-ui/react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getAuditExplanation, postExplainAuditRun } from "../../services/auditsApi";
import { STRINGS } from "../../i18n/strings";

interface Props {
  runId: number;
  enabled: boolean; // from /ai/status (operator can see)
}

export const AiExplainPanel: React.FC<Props> = ({ runId, enabled }) => {
  const queryClient = useQueryClient();
  const [showExplanation, setShowExplanation] = useState(false);

  const { data: explanation, isLoading, error } = useQuery<unknown, Error>(
    ["aiExplanation", runId],
    () => getAuditExplanation(runId),
    { enabled: showExplanation, staleTime: Infinity }
  );

  const explainMutation = useMutation(
    (force: boolean) => postExplainAuditRun(runId, force),
    {
      onSuccess: () => {
        queryClient.invalidateQueries(["aiExplanation", runId]);
        setShowExplanation(true);
      },
    }
  );

  if (!enabled) {
    return null;
  }

  const queryClient = useQueryClient();
  const [showExplanation, setShowExplanation] = useState(false);

  const { data: explanation, isLoading, error, refetch } = useQuery<unknown, Error>(
    ["aiExplanation", runId],
    () => getAuditExplanation(runId),
    { enabled: showExplanation, staleTime: Infinity }
  );

  const explainMutation = useMutation(
    (force: boolean) => postExplainAuditRun(runId, force),
    {
      onSuccess: () => {
        queryClient.invalidateQueries(["aiExplanation", runId]);
        setShowExplanation(true);
      },
    }
  );

  if (!enabled) {
    return null; // panel hidden when AI feature disabled
  }

  const handleExplain = (force = false) => {
    explainMutation.mutate(force);
  };

  return (
    <Box border="1px" borderColor="gray.200" rounded="md" p={4} mt={4}>
      <Text fontWeight="semibold" mb={2}>Giải thích AI</Text>
      {explainMutation.isLoading && (
        <Spinner size="sm" mr={2} />
      )}
      <Button size="sm" onClick={() => handleExplain(false)} isDisabled={explainMutation.isLoading}>
        {STRINGS.ai.explain}
      </Button>
      {explainMutation.isError && (
        <Alert status="error" mt={2} variant="left-accent">
          <AlertIcon />
          {explainMutation.error instanceof Error ? explainMutation.error.message : "Lỗi khi yêu cầu AI."}
        </Alert>
      )}
      {showExplanation && (
        <Box mt={3} bg="gray.50" p={3} rounded="md">
          {isLoading ? (
            <Spinner size="sm" />
          ) : error ? (
            <Alert status="error" variant="left-accent"><AlertIcon />{error.message}</Alert>
          ) : explanation ? (
            <Box>
              <Badge colorScheme="green" mb={2}>Generated</Badge>
              <Text>{(explanation as any).summary}</Text>
              {/* render priorities and risks if present */}
              {(explanation as any).priorities && (
                <Box mt={2}>
                  <Text fontWeight="medium">Ưu tiên:</Text>
                  <ul>
                    {(explanation as any).priorities.map((p: any, i: number) => (
                      <li key={i}>{p.rule_id}: {p.reason}</li>
                    ))}
                  </ul>
                </Box>
              )}
              {(explanation as any).risks && (
                <Box mt={2}>
                  <Text fontWeight="medium">Rủi ro:</Text>
                  <ul>
                    {(explanation as any).risks.map((r: any, i: number) => (
                      <li key={i}>{r.rule_id}: {r.warning}</li>
                    ))}
                  </ul>
                </Box>
              )}
            </Box>
          ) : (
            <Text>Không có giải thích.</Text>
          )}
        </Box>
      )}
    </Box>
  );
};

import { Box, Text, Spinner, Alert, AlertIcon, Button, Badge } from "@chakra-ui/react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getAuditExplanation, postExplainAuditRun } from "../../services/auditsApi";
import { STRINGS } from "../../i18n/strings";

interface Props {
  runId: number;
  enabled: boolean; // from /ai/status (operator can see)
}

export const AiExplainPanel: React.FC<Props> = ({ runId, enabled }) => {
  const queryClient = useQueryClient();
  const [showExplanation, setShowExplanation] = useState(false);

  const { data: explanation, isLoading, error } = useQuery<unknown, Error>(
    ["aiExplanation", runId],
    () => getAuditExplanation(runId),
    { enabled: showExplanation, staleTime: Infinity }
  );

  const explainMutation = useMutation(
    (force: boolean) => postExplainAuditRun(runId, force),
    {
      onSuccess: () => {
        queryClient.invalidateQueries(["aiExplanation", runId]);
        setShowExplanation(true);
      },
    }
  );

  if (!enabled) {
    return null;
  }

  const queryClient = useQueryClient();
  const [showExplanation, setShowExplanation] = useState(false);

  const { data: explanation, isLoading, error, refetch } = useQuery<any, Error>(
    ["aiExplanation", runId],
    () => getAuditExplanation(runId),
    { enabled: showExplanation, staleTime: Infinity }
  );

  const explainMutation = useMutation(
    (force: boolean) => postExplainAuditRun(runId, force),
    {
      onSuccess: () => {
        queryClient.invalidateQueries(["aiExplanation", runId]);
        setShowExplanation(true);
      },
    }
  );

  if (!enabled) {
    return null; // panel hidden when AI feature disabled
  }

  const handleExplain = (force = false) => {
    explainMutation.mutate(force);
  };

  return (
    <Box border="1px" borderColor="gray.200" rounded="md" p={4} mt={4}>
      <Text fontWeight="semibold" mb={2}>Giải thích AI</Text>
      {explainMutation.isLoading && (
        <Spinner size="sm" mr={2} />
      )}
      <Button size="sm" onClick={() => handleExplain(false)} isDisabled={explainMutation.isLoading}>
        {STRINGS.ai.explain}
      </Button>
      {explainMutation.isError && (
        <Alert status="error" mt={2} variant="left-accent">
          <AlertIcon />
          {explainMutation.error instanceof Error ? explainMutation.error.message : "Lỗi khi yêu cầu AI."}
        </Alert>
      )}
      {showExplanation && (
        <Box mt={3} bg="gray.50" p={3} rounded="md">
          {isLoading ? (
            <Spinner size="sm" />
          ) : error ? (
            <Alert status="error" variant="left-accent"><AlertIcon />{error.message}</Alert>
          ) : explanation ? (
            <Box>
              <Badge colorScheme="green" mb={2}>Generated</Badge>
              <Text>{explanation.summary}</Text>
              {/* render priorities and risks if present */}
              {explanation.priorities && (
                <Box mt={2}>
                  <Text fontWeight="medium">Ưu tiên:</Text>
                  <ul>
                    {explanation.priorities.map((p: any, i: number) => (
                      <li key={i}>{p.rule_id}: {p.reason}</li>
                    ))}
                  </ul>
                </Box>
              )}
              {explanation.risks && (
                <Box mt={2}>
                  <Text fontWeight="medium">Rủi ro:</Text>
                  <ul>
                    {explanation.risks.map((r: any, i: number) => (
                      <li key={i}>{r.rule_id}: {r.warning}</li>
                    ))}
                  </ul>
                </Box>
              )}
            </Box>
          ) : (
            <Text>Không có giải thích.</Text>
          )}
        </Box>
      )}
    </Box>
  );
};
