# Copyright © 2025-2026 Cognizant Technology Solutions Corp, www.cognizant.com.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# END COPYRIGHT
"""MetricsAnalyzer coded tool.

Loads a service's metric time-series and flags anomalies deterministically:
for each numeric metric it compares the baseline (first sample) against the peak,
detects sustained threshold breaches, and reports when the anomaly began. This gives
the reasoning agents quantitative, non-hallucinated evidence.
"""

import json
from logging import Logger
from logging import getLogger
from typing import Any
from typing import Dict
from typing import List
from typing import Union

from neuro_san.interfaces.coded_tool import CodedTool

from coded_tools.industry.incident_commander.data_access import get_data_dir
from coded_tools.industry.incident_commander.data_access import known_services

# Metrics where a HIGHER value is worse, with the threshold considered "anomalous".
HIGHER_IS_WORSE = {
    "error_rate": 0.05,
    "latency_p99_ms": 1000,
    "gc_pct": 0.30,
    "upstream_error_rate": 0.30,
    "restarts": 1,
    "db_pool_active": 10,  # pinned at max == exhausted
    "served_from_cache_pct": 0.50,
}


class MetricsAnalyzer(CodedTool):
    """Detect anomalies in a service's metric time-series."""

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Union[Dict[str, Any], str]:
        logger: Logger = getLogger(self.__class__.__name__)
        service = str(args.get("service") or sly_data.get("incident_service") or "").strip()
        if not service:
            return "Error: 'service' argument is required. Known services: " + ", ".join(known_services())

        path = get_data_dir() / "metrics" / f"{service}.json"
        if not path.is_file():
            return f"Error: no metrics for service '{service}'. Known services: {', '.join(known_services())}"

        logger.info("Analyzing metrics: %s", path)
        doc = json.loads(path.read_text(encoding="utf-8"))
        series: List[Dict[str, Any]] = doc.get("series", [])
        if not series:
            return f"Error: metrics file for '{service}' has no samples."

        metric_keys = [k for k in series[0].keys() if k != "ts" and isinstance(series[0][k], (int, float))]
        anomalies = []
        for key in metric_keys:
            values = [(row["ts"], row[key]) for row in series if isinstance(row.get(key), (int, float))]
            if not values:
                continue
            baseline_ts, baseline = values[0]
            peak_ts, peak = max(values, key=lambda tv: tv[1])
            threshold = HIGHER_IS_WORSE.get(key)
            breached = None
            if threshold is not None:
                for ts, v in values:
                    if v >= threshold:
                        breached = ts
                        break
            if threshold is not None and peak >= threshold:
                anomalies.append(
                    {
                        "metric": key,
                        "baseline": baseline,
                        "peak": peak,
                        "peak_ts": peak_ts,
                        "threshold": threshold,
                        "breach_started_ts": breached,
                        "delta_x": round(peak / baseline, 1) if baseline else None,
                    }
                )

        # Earliest breach across all metrics = when the incident became visible in metrics.
        breach_times = [a["breach_started_ts"] for a in anomalies if a["breach_started_ts"]]
        incident_onset = min(breach_times) if breach_times else None

        result = {
            "service": service,
            "samples": len(series),
            "window": {"from": series[0]["ts"], "to": series[-1]["ts"]},
            "metrics_tracked": metric_keys,
            "anomalies": sorted(anomalies, key=lambda a: (a["breach_started_ts"] or "")),
            "incident_onset_ts": incident_onset,
            "notes": doc.get("unit_notes"),
        }
        sly_data["incident_service"] = service
        return result
