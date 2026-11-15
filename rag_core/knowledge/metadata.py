"""The metadata schema and the MetadataRecord value object.

FIELDS is the single source of the schema. architecture/metadata_fields.csv repeats it for people,
and a unit test keeps the two the same. Every value is text, so a record fits a CSV row and a SQLite column.
"""
import re
from dataclasses import dataclass
from types import MappingProxyType

from ..shared.kernel import DomainError

# The proposal's knowledge types (section 7.1). Every case-study file is a "document".
DOCUMENT_TYPES = ("document", "profile", "project_report", "research_record", "achievement_record",
                  "challenge_record", "issue_answer", "rfp", "rfp_response", "feedback_report", "ike_model")
FORMATS = ("md", "txt", "docx", "doc", "pdf")
EXTRACTION_METHODS = ("markdown", "plain_text", "docx_xml", "pdf_text", "doc_convert", "lvm_ocr")
SHA256 = r"[0-9a-f]{64}"


@dataclass(frozen=True)
class Field:
    name: str
    required: bool
    rule: str          # "text", "date", "int", "sha256", "list", or "one of" (then `allowed` is set)
    allowed: tuple = ()
    meaning: str = ""
    source: str = ""   # where the field comes from: the proposal section, or "ingestion"


FIELDS = (
    # who and what
    Field("node_id", True, "text", meaning="The node that owns the item.", source="proposal 7.5 (organization or node)"),
    Field("title", True, "text", meaning="The title of the item.", source="ingestion"),
    Field("document_type", True, "one of", DOCUMENT_TYPES, "The kind of knowledge (proposal section 7.1).", "proposal 7.5 (document type)"),
    Field("field_of_activity", True, "text", meaning="The subject area, copied from the node unless given.", source="proposal 7.5 (field)"),
    Field("confidentiality", True, "one of", ("internal", "confidential"), "Who may see it, copied from the node unless given.", "proposal 7.5 (confidentiality level)"),
    Field("language", True, "text", meaning="Language code, such as en.", source="ingestion"),
    # where it came from
    Field("source_file", True, "text", meaning="The file path, relative to the case-study documents folder.", source="proposal 7.3 (source document)"),
    Field("file_format", True, "one of", FORMATS, "The DocumentFormat of the file.", "proposal 7.3"),
    Field("file_sha256", True, "sha256", meaning="ContentHash of the file's bytes.", source="proposal 7.7 (file hash)"),
    Field("text_sha256", True, "sha256", meaning="ContentHash of the normalized extracted text.", source="proposal 7.7 (text normalization)"),
    Field("extraction_method", True, "one of", EXTRACTION_METHODS, "How the text was read.", "proposal 7.3"),
    Field("page_count", False, "int", meaning="Pages, when the format has pages.", source="proposal 7.4 (page number)"),
    Field("ingested_at", True, "date", meaning="When the version was registered, ISO 8601 in UTC.", source="ingestion"),
    Field("change_reason", False, "text", meaning="Why this version was added.", source="proposal 7.6 (reason for change)"),
    # optional fields the proposal lists for later phases
    Field("subfield", False, "text", meaning="A narrower subject area.", source="proposal 7.5"),
    Field("project", False, "text", meaning="The project the item belongs to.", source="proposal 7.5"),
    Field("owner", False, "text", meaning="The author or owner.", source="proposal 7.5"),
    Field("status", False, "text", meaning="Workflow status.", source="proposal 7.5"),
    Field("priority", False, "text", meaning="Priority.", source="proposal 7.5"),
    Field("tags", False, "list", meaning="Labels, separated by ';'.", source="proposal 7.5"),
    Field("source_reliability", False, "one of", ("high", "medium", "low"), "How much the source can be trusted.", "proposal 7.5"),
    Field("related_issue", False, "text", meaning="An issue id.", source="proposal 7.5"),
    Field("related_executor", False, "text", meaning="An executor id.", source="proposal 7.5"),
    Field("related_rfp", False, "text", meaning="An RFP id.", source="proposal 7.5"),
    Field("target_layer", False, "int", meaning="The layer a transfer of this item goes to.", source="proposal 7.5"),
    Field("suggested_detail_level", False, "one of", ("executive", "managerial", "technical_summary", "detailed_technical"),
          "The detail level suggested for a transfer.", "proposal 7.5"),
)
BY_NAME = {f.name: f for f in FIELDS}
DATE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})")


def _check(field, value):
    if field.rule == "one of" and value not in field.allowed:
        return f"must be one of {', '.join(field.allowed)}"
    if field.rule == "int" and not value.isdigit():
        return "must be a whole number"
    if field.rule == "sha256" and not re.fullmatch(SHA256, value):
        return "must be 64 lowercase hex characters"
    if field.rule == "date" and not DATE.fullmatch(value):
        return "must be an ISO 8601 date and time with a zone, such as 2026-11-01T10:00:00Z"
    if field.rule == "list" and any(not part.strip() for part in value.split(";")):
        return "must be labels separated by ';' with no empty label"
    return None


@dataclass(frozen=True)
class MetadataRecord:
    """Structured data about one knowledge version. Unknown fields and broken values are rejected."""
    values: MappingProxyType

    def __init__(self, values):
        clean = {}
        for name, value in dict(values).items():
            if value is None or str(value).strip() == "":
                continue  # an empty optional field is the same as a missing one
            if name not in BY_NAME:
                raise DomainError(f"unknown metadata field {name!r}; the schema is in architecture/metadata_fields.csv")
            text = str(value).strip()
            problem = _check(BY_NAME[name], text)
            if problem:
                raise DomainError(f"metadata field {name} {problem}, not {text!r}")
            clean[name] = text
        missing = [f.name for f in FIELDS if f.required and f.name not in clean]
        if missing:
            raise DomainError(f"metadata is missing the required field(s): {', '.join(missing)}")
        object.__setattr__(self, "values", MappingProxyType(dict(sorted(clean.items()))))

    def __getitem__(self, name):
        return self.values[name]

    def get(self, name, default=None):
        return self.values.get(name, default)

    def with_changes(self, **changes):
        return MetadataRecord({**self.values, **changes})

    def as_dict(self):
        return dict(self.values)
