"""Turn the case-study manifest into registration requests. The case study stays read-only."""
import csv
from pathlib import Path

from .service import RegistrationRequest


def manifest_requests(case_dir, documents_dir=None, replace_suffix=None):
    """One request per manifest row, in manifest order. The item id is the doc_id (D10), the version tag is the
    manifest version.

    `documents_dir` and `replace_suffix` read converted copies, for example the DOCX files in team/C/files/ with
    replace_suffix='.docx'. A copy may sit in the node subfolder or directly in documents_dir. A file with no copy is
    read from the case study as usual. The file stem stays the same, so citations stay the same."""
    case_dir = Path(case_dir)
    originals = case_dir / "documents"
    copies = Path(documents_dir) if documents_dir else None
    with (case_dir / "documents_manifest.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    requests = []
    for row in rows:
        relative = Path(row["file"])
        path = originals / relative
        if copies is not None:
            suffix = replace_suffix or relative.suffix
            candidates = [copies / relative.with_suffix(suffix), copies / relative.with_suffix(suffix).name]
            path = next((c for c in candidates if c.exists()), path)
        requests.append(RegistrationRequest(path=path, item_id=row["doc_id"], node_id=row["node_id"],
                                            version_tag=row["version"], title=row["title"], language=row["language"],
                                            source_file=relative.with_suffix(path.suffix).as_posix()))
    return requests
