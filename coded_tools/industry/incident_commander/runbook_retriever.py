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
"""RunbookRetriever coded tool.

A dependency-free RAG retriever over the markdown runbook knowledge base. It scores
each runbook against the query using TF-IDF-style term weighting (no external vector
store, so the demo runs fully offline and deterministically) and returns the best
matching runbooks so the agents can ground remediation in approved procedure.
"""

import math
import re
from collections import Counter
from logging import Logger
from logging import getLogger
from typing import Any
from typing import Dict
from typing import List
from typing import Union

from neuro_san.interfaces.coded_tool import CodedTool

from coded_tools.industry.incident_commander.data_access import get_data_dir

TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOP = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "is", "are", "be",
    "with", "this", "that", "it", "as", "at", "by", "from", "was", "were", "has",
}


def _tokenize(text: str) -> List[str]:
    return [t for t in TOKEN_RE.findall(text.lower()) if t not in _STOP and len(t) > 2]


class RunbookRetriever(CodedTool):
    """Retrieve the most relevant runbook(s) for an incident query."""

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Union[Dict[str, Any], str]:
        logger: Logger = getLogger(self.__class__.__name__)
        query = str(args.get("query", "")).strip()
        if not query:
            return "Error: 'query' argument is required (describe the symptoms or suspected cause)."

        top_k = int(args.get("top_k", 2))
        runbook_dir = get_data_dir() / "runbooks"
        if not runbook_dir.is_dir():
            return f"Error: runbook directory not found at {runbook_dir}"

        docs = []
        for path in sorted(runbook_dir.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            docs.append({"name": path.stem, "text": text, "tokens": _tokenize(text)})
        if not docs:
            return "Error: no runbooks found."

        # Compute IDF across the corpus.
        df: Counter = Counter()
        for d in docs:
            for term in set(d["tokens"]):
                df[term] += 1
        n_docs = len(docs)
        idf = {term: math.log((n_docs + 1) / (freq + 0.5)) for term, freq in df.items()}

        q_terms = _tokenize(query)
        scored = []
        for d in docs:
            tf = Counter(d["tokens"])
            length = max(len(d["tokens"]), 1)
            score = 0.0
            matched = set()
            for term in q_terms:
                if tf.get(term):
                    score += (tf[term] / length) * idf.get(term, 0.0)
                    matched.add(term)
            scored.append((score, len(matched), d, sorted(matched)))

        scored.sort(key=lambda s: (s[0], s[1]), reverse=True)
        results = []
        for score, n_matched, d, matched in scored[:top_k]:
            if score <= 0:
                continue
            results.append(
                {
                    "runbook": d["name"],
                    "relevance_score": round(score, 4),
                    "matched_terms": matched,
                    "content": d["text"],
                }
            )

        logger.info("Runbook retrieval for %r -> %s", query, [r["runbook"] for r in results])
        if not results:
            return {"query": query, "matches": [], "note": "No runbook matched; escalate to a human SRE."}
        return {"query": query, "matches": results}
