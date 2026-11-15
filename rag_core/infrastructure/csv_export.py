"""CSV output for review and offline exchange (proposal section 9.3). Plain UTF-8, LF line endings, no BOM."""
import csv
from pathlib import Path

CATALOG_COLUMNS = ["item_id", "node_id", "version_tag", "sequence", "active", "title", "file_format", "extraction_method",
                   "source_file", "chunks", "words", "text_sha256", "diff_summary"]
CHUNK_COLUMNS = ["chunk_id", "item_id", "version_tag", "node_id", "order", "source_file", "page_start", "page_end",
                 "heading_path", "char_start", "char_end", "words", "text"]
REPORT_COLUMNS = ["source_file", "item_id", "version_tag", "node_id", "outcome", "chunks", "detail"]
DUPLICATE_COLUMNS = ["kind", "left_item", "left_version", "right_item", "right_version", "score", "shared_groups",
                     "same_node", "metadata_differences"]


def write_rows(path, columns, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def catalog_rows(repo):
    for item in repo.all_items():
        for v in item.versions:
            yield {"item_id": str(item.item_id), "node_id": item.node_id, "version_tag": str(v.tag), "sequence": v.sequence,
                   "active": "yes" if v.tag == item.active_tag else "no", "title": v.metadata["title"],
                   "file_format": v.metadata["file_format"], "extraction_method": v.metadata["extraction_method"],
                   "source_file": v.metadata["source_file"], "chunks": len(v.chunks), "words": len(v.text.split()),
                   "text_sha256": v.metadata["text_sha256"], "diff_summary": v.diff_summary}


def chunk_rows(repo):
    for item in repo.all_items():
        for v in item.versions:
            for c in v.chunks:
                loc = c.location
                yield {"chunk_id": c.chunk_id, "item_id": str(item.item_id), "version_tag": str(v.tag), "node_id": c.node_id,
                       "order": c.order, "source_file": loc.source_file, "page_start": loc.page_start or "",
                       "page_end": loc.page_end or "", "heading_path": " > ".join(loc.heading_path),
                       "char_start": loc.char_start, "char_end": loc.char_end, "words": len(c.text.split()), "text": c.text}


def duplicate_rows(records):
    for r in records:
        yield {"kind": r.kind.value, "left_item": r.left_item, "left_version": r.left_tag, "right_item": r.right_item,
               "right_version": r.right_tag, "score": f"{r.score:.3f}", "shared_groups": r.shared_groups,
               "same_node": "yes" if r.same_node else "no", "metadata_differences": " ".join(r.metadata_differences)}


def export(repo, folder):
    folder = Path(folder)
    write_rows(folder / "catalog.csv", CATALOG_COLUMNS, catalog_rows(repo))
    write_rows(folder / "chunks.csv", CHUNK_COLUMNS, chunk_rows(repo))
