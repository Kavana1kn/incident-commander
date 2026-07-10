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
"""Shared data-location helpers for the Incident Commander coded tools.

All synthetic incident data (logs, metrics, runbooks, deploy history) lives under
``data/incident_commander/`` at the repository root. Paths are resolved relative to
this file so the tools work regardless of the process working directory, with an
optional ``INCIDENT_DATA_DIR`` environment override.
"""

import os
from pathlib import Path


def get_data_dir() -> Path:
    """Return the incident_commander data directory.

    Resolution order:
    1. ``INCIDENT_DATA_DIR`` environment variable, if set.
    2. ``<repo_root>/data/incident_commander`` — repo root is 3 levels up from this
       file (coded_tools/industry/incident_commander/data_access.py).
    3. A ``data`` folder co-located with this package (fallback for relocated copies).
    """
    env_dir = os.environ.get("INCIDENT_DATA_DIR")
    if env_dir:
        return Path(env_dir).expanduser().resolve()

    repo_root = Path(__file__).resolve().parents[3]
    candidate = repo_root / "data" / "incident_commander"
    if candidate.is_dir():
        return candidate

    return Path(__file__).resolve().parent / "data"


def known_services() -> list:
    """List services that have a log file, so tools can validate/suggest inputs."""
    logs_dir = get_data_dir() / "logs"
    if not logs_dir.is_dir():
        return []
    return sorted(p.stem for p in logs_dir.glob("*.log"))
