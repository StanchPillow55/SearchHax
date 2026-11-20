"""Display layout for the investigation map.

Grouping changes what is drawn first. It does not drop passages, provenance,
or edges that still connect visible nodes.
"""

from __future__ import annotations


def collapse_evidence(nodes: list[dict], edges: list[dict], expanded: set[str] | frozenset[str]) -> tuple[list[dict], list[dict]]:
    """Collapse repeated evidence into one node per normalized claim or source.

    A group of one stays as the original evidence node. Expanded groups show
    every member. Non-evidence nodes are unchanged.
    """
    groups: dict[str, list[dict]] = {}
    order: list[str] = []
    visible: list[dict] = []
    replacement: dict[str, str] = {}
    for node in nodes:
        if node.get("type") != "evidence":
            visible.append(node)
            replacement[node["id"]] = node["id"]
            continue
        key = evidence_group_key(node)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(node)
    for key in order:
        members = groups[key]
        if len(members) < 2 or key in expanded:
            for member in members:
                visible.append(member)
                replacement[member["id"]] = member["id"]
            continue
        group = _group_node(key, members)
        visible.append(group)
        for member in members:
            replacement[member["id"]] = group["id"]
    visible_ids = {node["id"] for node in visible}
    collapsed_edges: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for edge in edges:
        source = replacement.get(edge["source"], edge["source"])
        target = replacement.get(edge["target"], edge["target"])
        if source == target or source not in visible_ids or target not in visible_ids:
            continue
        kind = edge.get("kind") or "sequence"
        identity = (source, target, kind)
        if identity in seen:
            continue
        seen.add(identity)
        collapsed_edges.append({
            "id": f"{edge['id']}:{source}:{target}",
            "source": source,
            "target": target,
            "kind": kind,
        })
    return visible, collapsed_edges


def evidence_group_key(node: dict) -> str:
    payload = node.get("payload") or {}
    claim = " ".join(str(payload.get("claim_text") or "").casefold().split())
    if claim:
        return f"claim:{claim[:180]}"
    document_id = payload.get("document_id")
    if document_id:
        return f"doc:{document_id}"
    return f"node:{node['id']}"


def _group_node(key: str, members: list[dict]) -> dict:
    statuses = [member.get("epistemic_status") or "unknown" for member in members]
    if "contradicted" in statuses:
        status = "contradicted"
    elif "unresolved" in statuses:
        status = "unresolved"
    elif statuses and all(item == "supported" for item in statuses):
        status = "supported"
    else:
        status = "unknown"
    sources = []
    for member in members:
        payload = member.get("payload") or {}
        source = payload.get("document_id") or payload.get("origin_id") or payload.get("provider")
        if source and source not in sources:
            sources.append(source)
    label = (members[0].get("label") or "Evidence").strip()
    return {
        "id": f"group:{key}",
        "type": "evidence_group",
        "label": label,
        "kicker": f"{len(members)} passages · {len(sources) or 1} source(s)",
        "epistemic_status": status,
        "verification_basis": "none",
        "payload": {
            "group_key": key,
            "count": len(members),
            "source_count": len(sources) or 1,
            "members": members,
        },
    }
