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
"""CommsDispatcher coded tool -- the human-in-the-loop action gate.

This is the only tool that performs an outward action (sending incident
communications). It enforces the approval gate *in code*, not just in the prompt:
nothing is dispatched unless ``approved`` is explicitly true. In demo mode the
message is written to a local outbox and echoed back; if ``SLACK_WEBHOOK_URL`` is
set, it also posts to Slack. This makes the trust boundary auditable.
"""

import json
import os
import urllib.error
import urllib.request
from datetime import datetime
from datetime import timezone
from logging import Logger
from logging import getLogger
from typing import Any
from typing import Dict
from typing import Union

from neuro_san.interfaces.coded_tool import CodedTool

from coded_tools.industry.incident_commander.data_access import get_data_dir

TRUTHY = {"true", "yes", "y", "approve", "approved", "1", "go", "ok", "confirm", "confirmed"}


def _is_approved(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in TRUTHY


class CommsDispatcher(CodedTool):
    """Dispatch incident communications, but only after explicit human approval."""

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Union[Dict[str, Any], str]:
        logger: Logger = getLogger(self.__class__.__name__)
        channel = str(args.get("channel", "incident-updates")).strip()
        message = str(args.get("message", "")).strip()
        approved = _is_approved(args.get("approved", False))

        if not message:
            return "Error: 'message' argument is required."

        if not approved:
            # HITL gate: refuse to act without approval and say so plainly.
            return {
                "status": "BLOCKED_AWAITING_APPROVAL",
                "detail": (
                    "No communication was sent. A human approver must explicitly approve this action "
                    "(pass approved=true) before the Incident Commander may dispatch comms."
                ),
                "would_have_sent": {"channel": channel, "message": message},
            }

        now = datetime.now(timezone.utc).isoformat()
        record = {
            "ts": now,
            "channel": channel,
            "message": message,
            "incident_service": sly_data.get("incident_service"),
            "approved_by": str(args.get("approver", "human-approver")),
        }

        # Persist to a local outbox (auditable demo artifact).
        outbox_dir = get_data_dir() / "outbox"
        outbox_dir.mkdir(parents=True, exist_ok=True)
        with (outbox_dir / "sent_comms.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")

        delivery = ["outbox"]
        webhook = os.environ.get("SLACK_WEBHOOK_URL")
        if webhook:
            try:
                payload = json.dumps({"text": f"[{channel}] {message}"}).encode("utf-8")
                req = urllib.request.Request(webhook, data=payload, headers={"Content-Type": "application/json"})
                urllib.request.urlopen(req, timeout=10)  # nosec B310 - user-provided webhook
                delivery.append("slack")
            except (urllib.error.URLError, ValueError) as exc:
                logger.warning("Slack dispatch failed: %s", exc)
                delivery.append(f"slack_failed:{exc}")

        logger.info("Dispatched incident comms to %s via %s", channel, delivery)
        # Track dispatched comms in incident state.
        sent = sly_data.setdefault("comms_sent", [])
        sent.append(record)
        return {
            "status": "SENT",
            "delivered_via": delivery,
            "record": record,
            "outbox_file": str(outbox_dir / "sent_comms.jsonl"),
        }
