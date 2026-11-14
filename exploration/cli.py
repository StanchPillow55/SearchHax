"""Print an investigation's nodes, edges, quotations, and stop reason."""

from __future__ import annotations

import argparse
import sys

from exploration.backend.config import default_db_path
from exploration.backend.orchestrator import Orchestrator


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="exploration.cli", description="Inspect a FrontierGraph evidence graph.")
    parser.add_argument("--db", default=str(default_db_path()))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("story-c", help="Run the offline Story C corpus and print the graph.")
    show = sub.add_parser("show", help="Print a stored investigation.")
    show.add_argument("investigation_id")

    args = parser.parse_args(argv)
    orchestrator = Orchestrator(args.db)
    if args.command == "story-c":
        export = orchestrator.run_story_c()
    else:
        try:
            export = orchestrator.get(args.investigation_id)
        except KeyError:
            print(f"investigation not found: {args.investigation_id}", file=sys.stderr)
            return 1
    print_export(export)
    return 0


def print_export(export) -> None:
    investigation = export.investigation
    names = {entity.id: entity.name for entity in export.entities}
    versions = {version.id: version for version in export.document_versions}
    print(f"Investigation: {investigation.id}")
    print(f"Question: {investigation.question}")
    print(f"Status: {investigation.status}")
    print(f"Stop reason: {investigation.stop_reason}")
    print(f"Decision source: {investigation.decision_source}")
    print(f"Rationale: {investigation.decision_rationale}")
    if investigation.blocker:
        print(f"Blocker: {investigation.blocker}")
    print(
        "Usage: "
        f"searches={investigation.usage.search_calls} "
        f"provider_calls={investigation.usage.provider_calls} "
        f"urls_fetched={investigation.usage.urls_fetched} "
        f"llm_calls={investigation.usage.llm_calls} "
        f"network_calls={investigation.usage.network_calls}"
    )
    print("\nNodes:")
    if not export.entities:
        print("- (none)")
    for entity in export.entities:
        print(f"- {entity.id} {entity.name} ({entity.type})")
    print("\nEdges:")
    if not export.relationships:
        print("- (none)")
    for rel in export.relationships:
        subject = rel.subject_name or names.get(rel.subject_id, rel.subject_id)
        obj = rel.object_name or names.get(rel.object_id, rel.object_id)
        print(f"- {subject} --{rel.predicate}--> {obj} [{rel.status}]")
    print("\nQuotes:")
    if not export.evidence_spans:
        print("- (none)")
    for span in export.evidence_spans:
        version = versions.get(span.version_id)
        exact = bool(version and version.content[span.start : span.end] == span.text)
        print(f"- {span.id} offsets={span.start}:{span.end} exact={exact} valid={span.quote_valid}")
        print(f"  {span.text}")
    print("\nShared origins:")
    if not export.origin_clusters:
        print("- (none)")
    for cluster in export.origin_clusters:
        print(
            f"- {cluster.origin_id} documents={len(cluster.document_ids)} "
            f"original={len(cluster.original_document_ids)} derivative={len(cluster.derivative_document_ids)}"
        )
    print("\nContradictions:")
    if not export.contradictions:
        print("- (none)")
    for item in export.contradictions:
        print(f"- {item.subject_name} {item.predicate}: {item.supported_object} vs {item.conflicting_object}")
        print(f"  {item.detail}")
    print("\nUnresolved questions:")
    if not export.unresolved_questions:
        print("- (none)")
    for question in export.unresolved_questions:
        print(f"- {question.text}")


if __name__ == "__main__":
    raise SystemExit(main())
