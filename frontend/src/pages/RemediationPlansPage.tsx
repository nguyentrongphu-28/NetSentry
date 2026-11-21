import React, { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useDevices } from "../hooks/useDevices";
import { listDeviceRemediationPlans } from "../services/remediationApi";
import { PlanStatusBadge } from "../components/remediation/PlanStatusBadge";
import { Badge } from "../components/ui/Badge";
import { Spinner } from "../components/ui/Spinner";
import { EmptyState } from "../components/ui/EmptyState";
import { STRINGS } from "../i18n/strings";
import { ShieldCheck, ChevronRight, Filter } from "lucide-react";

export function RemediationPlansPage(): React.JSX.Element {
  const { data: devicesData, isLoading: isDevicesLoading } = useDevices();
  const devices = devicesData?.items || [];

  const [selectedDeviceId, setSelectedDeviceId] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");

  const effectiveDeviceId =
    selectedDeviceId || (devices.length > 0 && devices[0] ? devices[0].device_id : "");

  const {
    data: plans = [],
    isLoading: isPlansLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ["device-remediation-plans", effectiveDeviceId, statusFilter],
    queryFn: () =>
      listDeviceRemediationPlans(
        effectiveDeviceId,
        statusFilter === "ALL" ? undefined : statusFilter
      ),
    enabled: !!effectiveDeviceId,
  });

  const isLoading = isDevicesLoading || (isPlansLoading && !!effectiveDeviceId);

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight flex items-center space-x-2">
            <ShieldCheck className="w-7 h-7 text-sky-600" />
            <span>{STRINGS.remediation.title}</span>
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Xem và quản lý các đề xuất cấu hình an toàn cho thiết bị mạng
          </p>
        </div>

        {/* Filter controls */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Device selector */}
          <div>
            <label htmlFor="device-select" className="sr-only">
              {STRINGS.remediation.colDevice}
            </label>
            <select
              id="device-select"
              value={effectiveDeviceId}
              onChange={(e) => setSelectedDeviceId(e.target.value)}
              className="text-xs border border-gray-300 rounded-md px-3 py-2 bg-white text-gray-700 shadow-xs focus:outline-none focus:ring-1 focus:ring-sky-500"
            >
              {devices.map((d) => (
                <option key={d.device_id} value={d.device_id}>
                  {d.name ? `${d.name} (${d.device_id})` : d.device_id}
                </option>
              ))}
            </select>
          </div>

          {/* Status filter */}
          <div className="flex items-center space-x-1.5">
            <Filter className="w-3.5 h-3.5 text-gray-400" />
            <select
              id="status-select"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="text-xs border border-gray-300 rounded-md px-3 py-2 bg-white text-gray-700 shadow-xs focus:outline-none focus:ring-1 focus:ring-sky-500"
            >
              <option value="ALL">{STRINGS.remediation.allStatuses}</option>
              <option value="PROPOSED">{STRINGS.remediation.statuses.PROPOSED}</option>
              <option value="APPROVED">{STRINGS.remediation.statuses.APPROVED}</option>
              <option value="REJECTED">{STRINGS.remediation.statuses.REJECTED}</option>
              <option value="CANCELLED">{STRINGS.remediation.statuses.CANCELLED}</option>
              <option value="EXPIRED">{STRINGS.remediation.statuses.EXPIRED}</option>
            </select>
          </div>
        </div>
      </div>

      {/* Main Content */}
      {isLoading ? (
        <div className="py-24 flex flex-col items-center justify-center space-y-3">
          <Spinner size="lg" className="text-sky-600" />
          <p className="text-sm text-gray-500">{STRINGS.common.loading}</p>
        </div>
      ) : isError ? (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
          {error instanceof Error ? error.message : "Không thể tải danh sách kế hoạch."}
        </div>
      ) : plans.length === 0 ? (
        <EmptyState
          title={STRINGS.remediation.empty}
          description="Chưa có kế hoạch khắc phục nào được tạo cho thiết bị này hoặc theo bộ lọc hiện tại."
          icon={<ShieldCheck className="w-12 h-12 text-gray-300" />}
        />
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 shadow-xs overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs divide-y divide-gray-200">
              <thead className="bg-gray-50/75 text-gray-500 uppercase tracking-wider font-semibold">
                <tr>
                  <th scope="col" className="px-6 py-3.5">
                    {STRINGS.remediation.colDevice}
                  </th>
                  <th scope="col" className="px-6 py-3.5">
                    {STRINGS.remediation.colRule}
                  </th>
                  <th scope="col" className="px-6 py-3.5">
                    {STRINGS.remediation.colRisk}
                  </th>
                  <th scope="col" className="px-6 py-3.5">
                    {STRINGS.remediation.colStatus}
                  </th>
                  <th scope="col" className="px-6 py-3.5">
                    {STRINGS.remediation.colProposer}
                  </th>
                  <th scope="col" className="px-6 py-3.5">
                    {STRINGS.remediation.colExpires}
                  </th>
                  <th scope="col" className="px-6 py-3.5 text-right">
                    Hành động
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 bg-white">
                {plans.map((p) => {
                  const riskVariant =
                    p.risk_level === "HIGH"
                      ? "danger"
                      : p.risk_level === "MEDIUM"
                      ? "warning"
                      : "info";
                  return (
                    <tr
                      key={p.id}
                      className="hover:bg-gray-50/60 transition-colors cursor-pointer"
                    >
                      <td className="px-6 py-4 font-mono font-medium text-gray-900">
                        {p.device_id}
                      </td>
                      <td className="px-6 py-4 font-mono font-semibold text-gray-900">
                        {p.rule_id}
                      </td>
                      <td className="px-6 py-4">
                        <Badge variant={riskVariant}>
                          {STRINGS.remediation.riskLevels[p.risk_level]}
                        </Badge>
                      </td>
                      <td className="px-6 py-4">
                        <PlanStatusBadge status={p.status} />
                      </td>
                      <td className="px-6 py-4 text-gray-600">
                        {p.proposed_by}
                      </td>
                      <td className="px-6 py-4 text-gray-500 whitespace-nowrap">
                        {new Date(p.expires_at).toLocaleString("vi-VN")}
                      </td>
                      <td className="px-6 py-4 text-right">
                        <Link
                          to={`/remediation/${p.id}`}
                          className="inline-flex items-center space-x-1 text-sky-600 hover:text-sky-800 font-medium"
                        >
                          <span>Xem chi tiết</span>
                          <ChevronRight className="w-3.5 h-3.5" />
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
