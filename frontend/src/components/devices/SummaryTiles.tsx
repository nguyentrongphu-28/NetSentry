import React, { useMemo } from "react";
import { DeviceWithLatestAuditOut } from "../../types/api";
import { STRINGS } from "../../i18n/strings";
import { Server, HelpCircle, AlertOctagon, ShieldAlert, AlertTriangle } from "lucide-react";

export interface SummaryTilesProps {
  devices: DeviceWithLatestAuditOut[];
}

export function SummaryTiles({ devices }: SummaryTilesProps): React.JSX.Element {
  const stats = useMemo(() => {
    const totalDevices = devices.length;
    let unaudited = 0;
    let failedRuns = 0;
    let devicesWithFail = 0;
    let totalFailFindings = 0;

    for (const d of devices) {
      if (!d.latest_audit) {
        unaudited += 1;
      } else {
        if (d.latest_audit.status === "FAILED") {
          failedRuns += 1;
        } else if (d.latest_audit.status === "COMPLETED") {
          if (d.latest_audit.fail_count > 0) {
            devicesWithFail += 1;
            totalFailFindings += d.latest_audit.fail_count;
          }
        }
      }
    }

    return {
      totalDevices,
      unaudited,
      failedRuns,
      devicesWithFail,
      totalFailFindings,
    };
  }, [devices]);

  const tiles = [
    {
      testId: "tile-total-devices",
      label: STRINGS.summaryTiles.totalDevices,
      value: stats.totalDevices,
      icon: <Server className="w-5 h-5 text-indigo-600" />,
      bg: "bg-indigo-50 border-indigo-100",
      textColor: "text-indigo-950",
    },
    {
      testId: "tile-unaudited",
      label: STRINGS.summaryTiles.unauditedDevices,
      value: stats.unaudited,
      icon: <HelpCircle className="w-5 h-5 text-gray-500" />,
      bg: "bg-gray-50 border-gray-200",
      textColor: "text-gray-900",
    },
    {
      testId: "tile-failed-audits",
      label: STRINGS.summaryTiles.failedAudits,
      value: stats.failedRuns,
      icon: <AlertOctagon className="w-5 h-5 text-rose-600" />,
      bg: "bg-rose-50 border-rose-100",
      textColor: "text-rose-950",
    },
    {
      testId: "tile-devices-with-fail",
      label: STRINGS.summaryTiles.devicesWithFailFindings,
      value: stats.devicesWithFail,
      icon: <ShieldAlert className="w-5 h-5 text-amber-600" />,
      bg: "bg-amber-50 border-amber-100",
      textColor: "text-amber-950",
    },
    {
      testId: "tile-total-fail-findings",
      label: STRINGS.summaryTiles.totalFailFindings,
      value: stats.totalFailFindings,
      icon: <AlertTriangle className="w-5 h-5 text-rose-600" />,
      bg: "bg-rose-50 border-rose-100",
      textColor: "text-rose-950",
    },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
      {tiles.map((tile, idx) => (
        <div
          key={idx}
          data-testid={tile.testId}
          className={`p-4 rounded-xl border ${tile.bg} shadow-sm flex flex-col justify-between`}
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-gray-600 line-clamp-1">{tile.label}</span>
            <div className="p-1.5 rounded-lg bg-white bg-opacity-80 shadow-xs flex-shrink-0">
              {tile.icon}
            </div>
          </div>
          <div className={`mt-3 text-2xl font-bold tracking-tight ${tile.textColor}`}>
            {tile.value}
          </div>
        </div>
      ))}
    </div>
  );
}
