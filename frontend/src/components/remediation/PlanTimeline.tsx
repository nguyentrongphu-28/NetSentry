import React from "react";
import { PlanEventOut } from "../../types/api";
import { STRINGS } from "../../i18n/strings";
import { Clock, ShieldCheck, XCircle, Ban, AlertCircle } from "lucide-react";

interface PlanTimelineProps {
  timeline: PlanEventOut[];
}

export function PlanTimeline({ timeline }: PlanTimelineProps): React.JSX.Element {
  if (!timeline || timeline.length === 0) {
    return (
      <div className="text-sm text-gray-500 py-3">
        {STRINGS.remediation.timeline.empty}
      </div>
    );
  }

  const getEventIcon = (eventType: string) => {
    switch (eventType.toUpperCase()) {
      case "PROPOSED":
        return <Clock className="w-4 h-4 text-sky-500" />;
      case "APPROVED":
        return <ShieldCheck className="w-4 h-4 text-emerald-500" />;
      case "REJECTED":
        return <XCircle className="w-4 h-4 text-rose-500" />;
      case "CANCELLED":
        return <Ban className="w-4 h-4 text-gray-500" />;
      case "EXPIRED":
        return <AlertCircle className="w-4 h-4 text-amber-500" />;
      default:
        return <Clock className="w-4 h-4 text-gray-400" />;
    }
  };

  return (
    <div className="flow-root">
      <ul className="-mb-8">
        {timeline.map((event, idx) => (
          <li key={event.id || idx}>
            <div className="relative pb-8">
              {idx !== timeline.length - 1 && (
                <span
                  className="absolute left-4 top-4 -ml-px h-full w-0.5 bg-gray-200"
                  aria-hidden="true"
                />
              )}
              <div className="relative flex space-x-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gray-50 border border-gray-200">
                  {getEventIcon(event.event_type)}
                </div>
                <div className="flex min-w-0 flex-1 justify-between space-x-4 pt-1.5">
                  <div>
                    <p className="text-sm font-medium text-gray-900">
                      <span className="font-semibold">{event.event_type}</span>
                      {event.actor && (
                        <span className="text-gray-500 font-normal ml-1">
                          bởi <span className="font-medium text-gray-700">{event.actor}</span>
                        </span>
                      )}
                    </p>
                    {event.detail && (
                      <p className="mt-1 text-sm text-gray-600 bg-gray-50 rounded p-2 border border-gray-100 whitespace-pre-wrap">
                        {event.detail}
                      </p>
                    )}
                  </div>
                  <div className="whitespace-nowrap text-right text-xs text-gray-500">
                    <time dateTime={event.occurred_at}>
                      {new Date(event.occurred_at).toLocaleString("vi-VN")}
                    </time>
                  </div>
                </div>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
