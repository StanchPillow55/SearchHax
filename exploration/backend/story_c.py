"""Load the fictional Story C corpus. These files never leave the repository."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from exploration.backend.config import story_c_dir

STORY_C_QUESTION = "Do three articles independently substantiate a company's claim?"


@dataclass(frozen=True)
class StoryDocument:
    url: str
    title: str
    publish_date: str
    content: str


def load_story_c(directory: Path | None = None) -> list[StoryDocument]:
    root = directory or story_c_dir()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    documents: list[StoryDocument] = []
    for item in manifest["documents"]:
        content = (root / item["file"]).read_text(encoding="utf-8")
        documents.append(
            StoryDocument(
                url=item["url"],
                title=item["title"],
                publish_date=item["publish_date"],
                content=content,
            )
        )
    return documents
