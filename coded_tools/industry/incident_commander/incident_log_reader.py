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
"""IncidentLogReader coded tool.

Deterministically parses a service's log file and returns a structured summary the
agents can reason over: log-level counts, distinct error/warning signatures with
counts, the incident window (first ERROR -> last line), detected deploy transitions,
and a handful of representative lines. Doing the parsing in code (not the LLM) keeps
the evidence trustworthy and cheap.
"""

import re
from collections import Counter
from collections import OrderedDict
from logging import Logger
from logging import getLogger
from typing import Any
from typing import Dict
from typing import Union

from neuro_san.interfaces.coded_tool import CodedTool

from coded_tools.industry.incident_commander.data_access import get_data_dir
from coded_tools.industry.incident_commander.data_access import known_services

# Matches: 2026-07-09T14:33:10Z ERROR checkout-service [v2.3.1] pod=... message
LINE_RE = re.compile(
    r"^(?P<ts>\S+)\s+(?P<level>INFO|WARN|ERROR|DEBUG)\s+(?P<service>\S+)\s+\[(?P<version>[^\]]+)\]\s+(?P<rest>.*)$"
)


def _signature(message: str) -> str:
    """Collapse a log message into a signature by stripping volatile tokens
    (ids, numbers, timings) so identical error classes group together."""
    sig = re.sub(r"\b[A-Z]{2,}-\d+\b", "<ID>", message)          # ORD-88251 -> <ID>
    sig = re.sub(r"\bpod=\S+", "pod=<POD>", sig)
    sig = re.sub(r"\d+(\.\d+)?(ms|MB|%)?", "<N>", sig)            # numbers/units -> <N>
    return sig.strip()[:160]


class IncidentLogReader(CodedTool):
    """Parse a synthetic service log and summarize errors, warnings and deploys."""

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Union[Dict[str, Any], str]:
        logger: Logger = getLogger(self.__class__.__name__)
        service = str(args.get("service", "")).strip()
        if not service:
            return "Error: 'service' argument is required. Known services: " + ", ".join(known_services())

        log_path = get_data_dir() / "logs" / f"{service}.log"
        if not log_path.is_file():
            return (
                f"Error: no log file for service '{service}'. "
                f"Known services: {', '.join(known_services()) or '(none found)'}"
            )

        logger.info("Reading incident log: %s", log_path)
        lines = log_path.read_text(encoding="utf-8").splitlines()

        level_counts: Counter = Counter()
        error_sigs: "OrderedDict[str, int]" = OrderedDict()
        warn_sigs: "OrderedDict[str, int]" = OrderedDict()
        versions_seen: "OrderedDict[str, str]" = OrderedDict()  # version -> first ts seen
        first_error_ts = None
        last_ts = None
        sample_errors = []

        for raw in lines:
            m = LINE_RE.match(raw.strip())
            if not m:
                continue
            level = m.group("level")
            ts = m.group("ts")
            version = m.group("version")
            rest = m.group("rest")
            level_counts[level] += 1
            last_ts = ts
            if version not in versions_seen:
                versions_seen[version] = ts
            if level == "ERROR":
                if first_error_ts is None:
                    first_error_ts = ts
                sig = _signature(rest)
                error_sigs[sig] = error_sigs.get(sig, 0) + 1
                if len(sample_errors) < 5:
                    sample_errors.append(f"{ts} {rest}")
            elif level == "WARN":
                sig = _signature(rest)
                warn_sigs[sig] = warn_sigs.get(sig, 0) + 1

        # Correlate with deploy history for this service.
        deploy_note = None
        deploys_summary = []
        import json

        deploys_path = get_data_dir() / "deploys.json"
        if deploys_path.is_file():
            try:
                data = json.loads(deploys_path.read_text(encoding="utf-8"))
                svc_deploys = [d for d in data.get("deploys", []) if d.get("service") == service]
                deploys_summary = svc_deploys
                if svc_deploys and first_error_ts:
                    latest = max(svc_deploys, key=lambda d: d.get("ts", ""))
                    if latest.get("ts", "") <= first_error_ts:
                        deploy_note = (
                            f"Most recent deploy {latest['version']} at {latest['ts']} "
                            f"PRECEDES first error at {first_error_ts}. Change: {latest.get('change')}"
                        )
            except (ValueError, OSError) as exc:  # pragma: no cover - defensive
                logger.warning("Could not parse deploys.json: %s", exc)

        top_errors = [{"signature": s, "count": c} for s, c in sorted(error_sigs.items(), key=lambda kv: -kv[1])]
        top_warnings = [{"signature": s, "count": c} for s, c in sorted(warn_sigs.items(), key=lambda kv: -kv[1])]

        result = {
            "service": service,
            "lines_parsed": sum(level_counts.values()),
            "level_counts": dict(level_counts),
            "first_error_ts": first_error_ts,
            "last_log_ts": last_ts,
            "distinct_error_types": len(error_sigs),
            "top_error_signatures": top_errors[:6],
            "top_warning_signatures": top_warnings[:5],
            "versions_seen": versions_seen,
            "recent_deploys": deploys_summary,
            "deploy_correlation": deploy_note,
            "sample_error_lines": sample_errors,
        }
        # Persist the service under investigation for downstream tools.
        sly_data["incident_service"] = service
        return result
