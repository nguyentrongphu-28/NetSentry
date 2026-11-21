import React, { useState } from "react";
import { useInfiniteQuery } from "@tanstack/react-query";
import { ShieldAlert, Filter, RefreshCw, AlertCircle } from "lucide-react";
import { SecurityEventRecord } from "../types/api";
import { apiFetch } from "../services/apiClient";
import { STRINGS } from "../i18n/strings";
import { Button } from "../components/ui/Button";
import { Spinner } from "../components/ui/Spinner";
import { formatDateTime } from "../utils/format";

const PAGE_SIZE = 50;

// Must match backend SecurityEventType exactly.
const EVENT_TYPES = [
  "LOGIN_SUCCESS",
  "LOGIN_FAILED",
  "LOGIN_LOCKED",
  "LOGOUT",
  "PASSWORD_CHANGED",
  "PASSWORD_RESET",
  "USER_CREATED",
  "USER_UPDATED",
  "DEVICE_CREATED",
  "DEVICE_DELETED",
  "AUDIT_STARTED",
  "ACCESS_DENIED",
  "SNAPSHOT_VIEWED",
  "SNAPSHOT_DELETED",
  "AI_EXPLAIN_REQUESTED",
  "BASELINE_APPROVED",
  "BASELINE_RETIRED",
  "REMEDIATION_PROPOSED",
  "REMEDIATION_APPROVED",
  "REMEDIATION_REJECTED",
  "REMEDIATION_CANCELLED",
];

async function fetchEvents(
  eventType: string,
  beforeId: number | undefined,
): Promise<SecurityEventRecord[]> {
  const params = new URLSearchParams();
  params.set("limit", String(PAGE_SIZE));
  if (eventType) params.set("event_type", eventType);
  if (beforeId !== undefined) params.set("before_id", String(beforeId));
  return apiFetch<SecurityEventRecord[]>(`/api/v1/security-events?${params.toString()}`);
}

export function SecurityEventsPage(): React.JSX.Element {
  const [selectedType, setSelectedType] = useState<string>("");

  const query = useInfiniteQuery({
    queryKey: ["security-events", selectedType],
    initialPageParam: undefined as number | undefined,
    queryFn: ({ pageParam }) => fetchEvents(selectedType, pageParam),
    getNextPageParam: (lastPage) =>
      lastPage.length === PAGE_SIZE ? lastPage[lastPage.length - 1]?.id : undefined,
  });

  const events: SecurityEventRecord[] = query.data?.pages.flat() ?? [];
  const isLoading = query.isPending;
  const isLoadingMore = query.isFetchingNextPage;
  const hasMore = query.hasNextPage;
  const error = query.isError ? STRINGS.securityEvents.errorLoad : null;

  const loadInitial = (): void => {
    void query.refetch();
  };
  const handleLoadMore = (): void => {
    void query.fetchNextPage();
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">
            {STRINGS.securityEvents.title}
          </h1>
          <p className="mt-1 text-sm text-gray-500">{STRINGS.securityEvents.subtitle}</p>
        </div>

        <div className="flex items-center space-x-3">
          <div className="relative">
            <Filter className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
            <select
              value={selectedType}
              onChange={(e) => setSelectedType(e.target.value)}
              className="pl-9 pr-8 py-2 text-xs border border-gray-300 rounded-lg bg-white shadow-xs focus:outline-none focus:ring-1 focus:ring-indigo-500"
            >
              <option value="">{STRINGS.securityEvents.allTypes}</option>
              {EVENT_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>
          <Button
            variant="secondary"
            size="sm"
            icon={<RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />}
            onClick={loadInitial}
          >
            Làm mới
          </Button>
        </div>
      </div>

      {isLoading && (
        <div className="py-20 flex flex-col items-center justify-center space-y-3">
          <Spinner size="lg" className="text-indigo-600" />
          <p className="text-sm text-gray-500">{STRINGS.securityEvents.loading}</p>
        </div>
      )}

      {error && (
        <div
          role="alert"
          className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-sm text-rose-700 flex items-center justify-between"
        >
          <div className="flex items-center space-x-2">
            <AlertCircle className="w-5 h-5 flex-shrink-0" />
            <span>{error}</span>
          </div>
          <Button variant="secondary" size="sm" onClick={loadInitial}>
            Thử lại
          </Button>
        </div>
      )}

      {!isLoading && !error && (
        <>
          {events.length === 0 ? (
            <div className="py-16 text-center bg-white rounded-xl border border-gray-200 p-8 space-y-3">
              <ShieldAlert className="w-10 h-10 text-gray-400 mx-auto" />
              <p className="text-sm font-medium text-gray-900">{STRINGS.securityEvents.noEvents}</p>
            </div>
          ) : (
            <div className="overflow-x-auto border border-gray-200 rounded-xl shadow-xs bg-white">
              <table className="min-w-full divide-y divide-gray-200 text-left text-sm">
                <thead className="bg-gray-50 text-gray-500 font-medium text-xs">
                  <tr>
                    <th scope="col" className="px-6 py-3.5">{STRINGS.securityEvents.colTime}</th>
                    <th scope="col" className="px-6 py-3.5">{STRINGS.securityEvents.colType}</th>
                    <th scope="col" className="px-6 py-3.5">{STRINGS.securityEvents.colActor}</th>
                    <th scope="col" className="px-6 py-3.5">{STRINGS.securityEvents.colIp}</th>
                    <th scope="col" className="px-6 py-3.5">{STRINGS.securityEvents.colTarget}</th>
                    <th scope="col" className="px-6 py-3.5">{STRINGS.securityEvents.colDetail}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200 bg-white font-mono text-xs">
                  {events.map((ev) => (
                    <tr key={ev.id} className="hover:bg-gray-50/80 transition-colors">
                      <td className="px-6 py-3.5 whitespace-nowrap text-gray-500">
                        {formatDateTime(ev.occurred_at)}
                      </td>
                      <td className="px-6 py-3.5 whitespace-nowrap">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold ${
                            ev.event_type.includes("FAILED") ||
                            ev.event_type.includes("DENIED") ||
                            ev.event_type.includes("LOCKED")
                              ? "bg-rose-50 text-rose-700 border border-rose-200"
                              : ev.event_type.includes("CREATED") ||
                                  ev.event_type.includes("RESET")
                                ? "bg-blue-50 text-blue-700 border border-blue-200"
                                : "bg-gray-100 text-gray-700 border border-gray-200"
                          }`}
                        >
                          {ev.event_type}
                        </span>
                      </td>
                      <td className="px-6 py-3.5 whitespace-nowrap text-gray-800">
                        {ev.actor_username || "–"}
                      </td>
                      <td className="px-6 py-3.5 whitespace-nowrap text-gray-500">
                        {ev.client_ip || "–"}
                      </td>
                      <td className="px-6 py-3.5 whitespace-nowrap text-gray-600">
                        {ev.target || "–"}
                      </td>
                      <td className="px-6 py-3.5 text-gray-500 max-w-xs truncate">
                        {ev.detail || "–"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {hasMore && (
            <div className="text-center pt-2">
              <Button
                variant="secondary"
                isLoading={isLoadingMore}
                disabled={isLoadingMore}
                onClick={handleLoadMore}
              >
                {isLoadingMore ? "Đang tải thêm..." : STRINGS.securityEvents.loadMore}
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
