import React from "react";
import { Link } from "react-router-dom";
import { Play, Trash2, Shield, ExternalLink } from "lucide-react";
import { DeviceWithLatestAuditOut } from "../../types/api";
import { STRINGS } from "../../i18n/strings";
import { formatDateTime, formatRelativeTime } from "../../utils/format";
import { StatusBadge } from "../audits/StatusBadge";
import { Button } from "../ui/Button";

export interface DeviceTableProps {
  devices: DeviceWithLatestAuditOut[];
  onRunAudit: (device: DeviceWithLatestAuditOut) => void;
  onDeleteDevice: (device: DeviceWithLatestAuditOut) => void;
}

export function DeviceTable({
  devices,
  onRunAudit,
  onDeleteDevice,
}: DeviceTableProps): React.JSX.Element {
  return (
    <div className="overflow-x-auto border border-gray-200 rounded-xl shadow-sm bg-white">
      <table className="min-w-full divide-y divide-gray-200 text-left text-sm">
        <thead className="bg-gray-50 text-gray-500 font-medium">
          <tr>
            <th scope="col" className="px-6 py-3.5">
              {STRINGS.devicesTable.colDevice}
            </th>
            <th scope="col" className="px-6 py-3.5">
              {STRINGS.devicesTable.colHostPort}
            </th>
            <th scope="col" className="px-6 py-3.5">
              {STRINGS.devicesTable.colPlatform}
            </th>
            <th scope="col" className="px-6 py-3.5">
              {STRINGS.devicesTable.colLatestAudit}
            </th>
            <th scope="col" className="px-6 py-3.5">
              {STRINGS.devicesTable.colResult}
            </th>
            <th scope="col" className="px-6 py-3.5 text-right">
              {STRINGS.devicesTable.colActions}
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-200 bg-white">
          {devices.map((device) => {
            const latest = device.latest_audit;

            return (
              <tr key={device.device_id} className="hover:bg-gray-50/80 transition-colors">
                {/* Device ID and Name */}
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="flex items-center space-x-2.5">
                    <div className="w-8 h-8 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center flex-shrink-0">
                      <Shield className="w-4 h-4" />
                    </div>
                    <div>
                      <Link
                        to={`/devices/${encodeURIComponent(device.device_id)}`}
                        className="font-semibold text-gray-900 hover:text-indigo-600 inline-flex items-center space-x-1"
                      >
                        <span>{device.device_id}</span>
                        <ExternalLink className="w-3.5 h-3.5 text-gray-400" />
                      </Link>
                      {device.name && (
                        <p className="text-xs text-gray-500 line-clamp-1">{device.name}</p>
                      )}
                    </div>
                  </div>
                </td>

                {/* Host:Port */}
                <td className="px-6 py-4 whitespace-nowrap text-gray-700 font-mono text-xs">
                  {device.host}:{device.port}
                </td>

                {/* Platform */}
                <td className="px-6 py-4 whitespace-nowrap text-gray-600 text-xs">
                  <span className="px-2 py-0.5 rounded bg-gray-100 border border-gray-200 font-mono">
                    {device.platform}
                  </span>
                </td>

                {/* Latest Audit Time */}
                <td className="px-6 py-4 whitespace-nowrap text-gray-600 text-xs">
                  {latest ? (
                    <span title={formatDateTime(latest.finished_at)}>
                      {formatRelativeTime(latest.finished_at)}
                    </span>
                  ) : (
                    <span className="text-gray-400 italic">
                      {STRINGS.devicesTable.neverAudited}
                    </span>
                  )}
                </td>

                {/* Result */}
                <td className="px-6 py-4 whitespace-nowrap">
                  {latest ? (
                    <div className="flex items-center space-x-2">
                      <StatusBadge status={latest.status} size="sm" />
                      {latest.status === "COMPLETED" && (
                        <span className="text-xs font-mono text-gray-600">
                          <span className="text-emerald-700 font-medium">{latest.pass_count}P</span>
                          {" / "}
                          <span className="text-rose-700 font-medium">{latest.fail_count}F</span>
                          {" / "}
                          <span className="text-amber-700 font-medium">{latest.unknown_count}U</span>
                        </span>
                      )}
                      {latest.status === "FAILED" && latest.error_code && (
                        <span className="text-xs text-rose-600 font-mono">
                          [{latest.error_code}]
                        </span>
                      )}
                    </div>
                  ) : (
                    <span className="text-xs text-gray-400">–</span>
                  )}
                </td>

                {/* Actions */}
                <td className="px-6 py-4 whitespace-nowrap text-right space-x-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    icon={<Play className="w-3.5 h-3.5 text-indigo-600" />}
                    onClick={() => onRunAudit(device)}
                  >
                    {STRINGS.devicesTable.actionAudit}
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-gray-400 hover:text-rose-600"
                    icon={<Trash2 className="w-3.5 h-3.5" />}
                    onClick={() => onDeleteDevice(device)}
                    aria-label={`Xóa ${device.device_id}`}
                  />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
