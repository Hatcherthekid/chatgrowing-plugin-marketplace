"""Governed contracts for deterministic long-image report surfaces.

These DTOs describe presentation only. They never calculate advertising metrics,
query data sources, or carry delivery credentials and recipient identifiers.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
import re
from typing import Any, Mapping, Sequence


LONG_IMAGE_PROFILE_SCHEMA_VERSION = "long_image_visual_profile_v1"
LONG_IMAGE_RENDER_SPEC_VERSION = "long_image_render_spec_v1"
LONG_IMAGE_ARTIFACT_VERSION = "long_image_artifact_v1"
LONG_IMAGE_OUTPUT_BUNDLE_VERSION = "long_image_output_bundle_v1"
FEISHU_PROJECTION_PLAN_VERSION = "feishu_projection_plan_v1"

_ALLOWED_NUMBER_FORMATS = {"text", "integer", "decimal", "currency", "percentage", "date"}
_ALLOWED_ALIGNMENTS = {"auto", "left", "center", "right"}
_ALLOWED_VERTICAL_ALIGNMENTS = {"top", "center", "bottom"}
_ALLOWED_TEXT_WRAP = {"forbidden", "controlled"}
_ALLOWED_EMPHASIS = {"normal", "muted", "bold", "warning", "critical"}
_ALLOWED_BORDERS = {"none", "grid", "bottom", "outline"}
_ALLOWED_PROFILE_STATUSES = {"draft", "published", "retired"}
_ALLOWED_AUDIENCES = {"management", "operator"}
_ALLOWED_DENSITIES = {"compact", "comfortable"}
_ALLOWED_DIRECTIONS = {"lower_is_better", "higher_is_better", "low_to_high"}
_ALLOWED_BLOCK_TYPES = {"table", "chart"}
_ALLOWED_PROJECTION_MODES = {"interactive_manual", "scheduled_profiled"}
_ALLOWED_OUTPUT_MODES = {"full", "sections", "both"}
_SAFE_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,127}$")
_SAFE_ROUTE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$")
_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
_FORBIDDEN_KEYS = {
    "access_token",
    "token",
    "secret",
    "password",
    "chat_id",
    "open_id",
    "recipient_id",
    "recipient",
    "sql",
    "html",
    "css",
    "formula",
}


class LongImageContractError(ValueError):
    """Raised when a long-image presentation contract is unsafe or invalid."""


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise LongImageContractError(f"{label}_mapping_required")
    return dict(value)


def _reject_unknown(payload: Mapping[str, Any], allowed: set[str], label: str) -> None:
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise LongImageContractError(f"{label}_unknown_fields:{','.join(unknown)}")


def _required_text(value: Any, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise LongImageContractError(f"{label}_required")
    return text


def _safe_id(value: Any, label: str) -> str:
    text = _required_text(value, label)
    if not _SAFE_ID.fullmatch(text):
        raise LongImageContractError(f"{label}_invalid")
    return text


def _positive_int(value: Any, label: str, *, maximum: int | None = None) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise LongImageContractError(f"{label}_integer_required") from exc
    if result <= 0 or (maximum is not None and result > maximum):
        raise LongImageContractError(f"{label}_out_of_range")
    return result


def _color(value: Any, label: str) -> str:
    text = str(value or "").strip()
    if not _HEX_COLOR.fullmatch(text):
        raise LongImageContractError(f"{label}_hex_color_required")
    return text.lower()


def _assert_no_sensitive_keys(value: Any, *, path: str = "root") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).strip().lower()
            if normalized in _FORBIDDEN_KEYS:
                raise LongImageContractError(f"sensitive_or_executable_field_forbidden:{path}.{key}")
            _assert_no_sensitive_keys(child, path=f"{path}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            _assert_no_sensitive_keys(child, path=f"{path}[{index}]")


@dataclass(frozen=True)
class CellFormatSpec:
    format_id: str
    number_format: str = "text"
    decimal_places: int = 2
    thousands_separator: bool = True
    currency_source: str = "artifact"
    alignment: str = "auto"
    emphasis: str = "normal"
    text_color_token: str = "text"
    fill_token: str = "cell"
    border: str = "grid"
    conditional_format_ref: str = ""
    text_wrap: str = "forbidden"
    max_width: int = 0
    line_gap: int = 0
    vertical_alignment: str = "center"

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "CellFormatSpec":
        payload = _mapping(value, "cell_format")
        _reject_unknown(
            payload,
            {
                "format_id",
                "number_format",
                "decimal_places",
                "thousands_separator",
                "currency_source",
                "alignment",
                "emphasis",
                "text_color_token",
                "fill_token",
                "border",
                "conditional_format_ref",
                "text_wrap",
                "max_width",
                "line_gap",
                "vertical_alignment",
            },
            "cell_format",
        )
        number_format = str(payload.get("number_format") or "text")
        alignment = str(payload.get("alignment") or "auto")
        emphasis = str(payload.get("emphasis") or "normal")
        border = str(payload.get("border") or "grid")
        text_wrap = str(payload.get("text_wrap") or "forbidden")
        vertical_alignment = str(payload.get("vertical_alignment") or "center")
        if number_format not in _ALLOWED_NUMBER_FORMATS:
            raise LongImageContractError("cell_format_number_format_invalid")
        if alignment not in _ALLOWED_ALIGNMENTS:
            raise LongImageContractError("cell_format_alignment_invalid")
        if emphasis not in _ALLOWED_EMPHASIS:
            raise LongImageContractError("cell_format_emphasis_invalid")
        if border not in _ALLOWED_BORDERS:
            raise LongImageContractError("cell_format_border_invalid")
        if text_wrap not in _ALLOWED_TEXT_WRAP:
            raise LongImageContractError("cell_format_text_wrap_invalid")
        if vertical_alignment not in _ALLOWED_VERTICAL_ALIGNMENTS:
            raise LongImageContractError("cell_format_vertical_alignment_invalid")
        decimal_places = int(payload.get("decimal_places", 2))
        if decimal_places < 0 or decimal_places > 6:
            raise LongImageContractError("cell_format_decimal_places_out_of_range")
        currency_source = str(payload.get("currency_source") or "artifact")
        if currency_source != "artifact":
            raise LongImageContractError("cell_format_currency_source_must_be_artifact")
        try:
            max_width = int(payload.get("max_width") or 0)
            line_gap = int(payload.get("line_gap") or 0)
        except (TypeError, ValueError) as exc:
            raise LongImageContractError("cell_format_text_layout_integer_required") from exc
        if text_wrap == "controlled":
            if number_format not in {"text", "date"}:
                raise LongImageContractError("cell_format_controlled_wrap_requires_text")
            if max_width < 160 or max_width > 1600:
                raise LongImageContractError("cell_format_controlled_wrap_max_width_out_of_range")
            if line_gap < 0 or line_gap > 32:
                raise LongImageContractError("cell_format_controlled_wrap_line_gap_out_of_range")
        elif max_width or line_gap:
            raise LongImageContractError("cell_format_text_layout_requires_controlled_wrap")
        return cls(
            format_id=_safe_id(payload.get("format_id"), "cell_format_id"),
            number_format=number_format,
            decimal_places=decimal_places,
            thousands_separator=bool(payload.get("thousands_separator", True)),
            currency_source=currency_source,
            alignment=alignment,
            emphasis=emphasis,
            text_color_token=_safe_id(payload.get("text_color_token") or "text", "text_color_token"),
            fill_token=_safe_id(payload.get("fill_token") or "cell", "fill_token"),
            border=border,
            conditional_format_ref=str(payload.get("conditional_format_ref") or "").strip(),
            text_wrap=text_wrap,
            max_width=max_width,
            line_gap=line_gap,
            vertical_alignment=vertical_alignment,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass(frozen=True)
class ConditionalFormatSpec:
    conditional_format_id: str
    palette: tuple[str, ...]
    direction_by_metric: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ConditionalFormatSpec":
        payload = _mapping(value, "conditional_format")
        _reject_unknown(payload, {"conditional_format_id", "palette", "direction_by_metric"}, "conditional_format")
        palette_values = payload.get("palette")
        if not isinstance(palette_values, Sequence) or isinstance(palette_values, (str, bytes)) or len(palette_values) != 5:
            raise LongImageContractError("conditional_format_palette_requires_five_colors")
        directions = _mapping(payload.get("direction_by_metric") or {}, "direction_by_metric")
        normalized_directions: dict[str, str] = {}
        for metric, direction in directions.items():
            metric_id = _safe_id(metric, "conditional_metric")
            direction_text = str(direction or "")
            if direction_text not in _ALLOWED_DIRECTIONS:
                raise LongImageContractError("conditional_metric_direction_invalid")
            normalized_directions[metric_id] = direction_text
        return cls(
            conditional_format_id=_safe_id(payload.get("conditional_format_id"), "conditional_format_id"),
            palette=tuple(_color(item, "conditional_format_palette") for item in palette_values),
            direction_by_metric=normalized_directions,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LongImageVisualProfile:
    profile_id: str
    version: int
    status: str
    audience: str
    density: str
    colors: dict[str, str]
    typography: dict[str, Any]
    spacing: dict[str, int]
    layout: dict[str, Any]
    cell_formats: dict[str, CellFormatSpec]
    conditional_formats: dict[str, ConditionalFormatSpec]
    image_budget: dict[str, int]
    qa_gates: tuple[str, ...] = ()
    schema_version: str = LONG_IMAGE_PROFILE_SCHEMA_VERSION

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "LongImageVisualProfile":
        payload = _mapping(value, "long_image_visual_profile")
        _assert_no_sensitive_keys(payload)
        _reject_unknown(
            payload,
            {
                "schema_version",
                "profile_id",
                "version",
                "status",
                "audience",
                "density",
                "colors",
                "typography",
                "spacing",
                "layout",
                "cell_formats",
                "conditional_formats",
                "image_budget",
                "qa_gates",
            },
            "long_image_visual_profile",
        )
        if str(payload.get("schema_version") or LONG_IMAGE_PROFILE_SCHEMA_VERSION) != LONG_IMAGE_PROFILE_SCHEMA_VERSION:
            raise LongImageContractError("long_image_profile_schema_version_invalid")
        status = str(payload.get("status") or "")
        audience = str(payload.get("audience") or "")
        density = str(payload.get("density") or "")
        if status not in _ALLOWED_PROFILE_STATUSES:
            raise LongImageContractError("long_image_profile_status_invalid")
        if audience not in _ALLOWED_AUDIENCES:
            raise LongImageContractError("long_image_profile_audience_invalid")
        if density not in _ALLOWED_DENSITIES:
            raise LongImageContractError("long_image_profile_density_invalid")
        colors = {str(key): _color(item, f"profile_color_{key}") for key, item in _mapping(payload.get("colors"), "profile_colors").items()}
        required_colors = {"page", "cell", "header", "grid", "text", "muted", "accent", "warning", "critical"}
        if not required_colors.issubset(colors):
            raise LongImageContractError("long_image_profile_required_colors_missing")
        typography = _mapping(payload.get("typography"), "profile_typography")
        _reject_unknown(typography, {"font_families", "title_size", "section_size", "header_size", "cell_size", "note_size"}, "profile_typography")
        families = typography.get("font_families")
        if not isinstance(families, list) or not families or not all(str(item).strip() for item in families):
            raise LongImageContractError("profile_font_families_required")
        normalized_typography = {
            "font_families": [str(item).strip() for item in families],
            **{
                key: _positive_int(typography.get(key), f"profile_{key}", maximum=96)
                for key in ("title_size", "section_size", "header_size", "cell_size", "note_size")
            },
        }
        spacing = {str(key): _positive_int(item, f"profile_spacing_{key}", maximum=256) for key, item in _mapping(payload.get("spacing"), "profile_spacing").items()}
        for required in ("margin", "section_gap", "cell_padding", "row_height"):
            if required not in spacing:
                raise LongImageContractError(f"profile_spacing_{required}_required")
        layout = _mapping(payload.get("layout"), "profile_layout")
        _reject_unknown(
            layout,
            {
                "min_canvas_width",
                "max_canvas_width",
                "cell_wrap",
                "cell_truncation",
                "section_scaling",
                "pagination",
                "section_split",
                "max_segment_height",
                "repeat_report_header",
            },
            "profile_layout",
        )
        cell_wrap = str(layout.get("cell_wrap") or "forbidden")
        if cell_wrap not in _ALLOWED_TEXT_WRAP:
            raise LongImageContractError("profile_cell_wrap_invalid")
        for forbidden in ("cell_truncation", "section_scaling", "pagination"):
            if str(layout.get(forbidden) or "forbidden") != "forbidden":
                raise LongImageContractError(f"profile_{forbidden}_must_be_forbidden")
        normalized_layout = {
            "min_canvas_width": _positive_int(layout.get("min_canvas_width"), "profile_min_canvas_width"),
            "max_canvas_width": _positive_int(layout.get("max_canvas_width"), "profile_max_canvas_width"),
            "cell_wrap": cell_wrap,
            "cell_truncation": "forbidden",
            "section_scaling": "forbidden",
            "pagination": "forbidden",
        }
        if "section_split" in layout:
            if str(layout.get("section_split") or "") != "section_boundary":
                raise LongImageContractError("profile_section_split_invalid")
            normalized_layout.update(
                {
                    "section_split": "section_boundary",
                    "max_segment_height": _positive_int(
                        layout.get("max_segment_height"),
                        "profile_max_segment_height",
                        maximum=60_000,
                    ),
                    "repeat_report_header": bool(layout.get("repeat_report_header", True)),
                }
            )
        elif "max_segment_height" in layout or "repeat_report_header" in layout:
            raise LongImageContractError("profile_section_split_required_for_segment_options")
        if normalized_layout["max_canvas_width"] < normalized_layout["min_canvas_width"]:
            raise LongImageContractError("profile_canvas_width_range_invalid")
        cell_formats_raw = _mapping(payload.get("cell_formats"), "profile_cell_formats")
        cell_formats = {str(key): CellFormatSpec.from_mapping(item) for key, item in cell_formats_raw.items()}
        if any(key != item.format_id for key, item in cell_formats.items()):
            raise LongImageContractError("cell_format_registry_key_mismatch")
        conditional_raw = _mapping(payload.get("conditional_formats") or {}, "profile_conditional_formats")
        conditional_formats = {str(key): ConditionalFormatSpec.from_mapping(item) for key, item in conditional_raw.items()}
        if any(key != item.conditional_format_id for key, item in conditional_formats.items()):
            raise LongImageContractError("conditional_format_registry_key_mismatch")
        for item in cell_formats.values():
            if item.text_color_token not in colors or item.fill_token not in colors:
                raise LongImageContractError("cell_format_color_token_unknown")
            if item.conditional_format_ref and item.conditional_format_ref not in conditional_formats:
                raise LongImageContractError("cell_format_conditional_format_unknown")
            if item.text_wrap == "controlled" and normalized_layout["cell_wrap"] != "controlled":
                raise LongImageContractError("cell_format_controlled_wrap_requires_profile_support")
        if normalized_layout["cell_wrap"] == "controlled" and not any(
            item.text_wrap == "controlled" for item in cell_formats.values()
        ):
            raise LongImageContractError("profile_controlled_wrap_format_required")
        image_budget_raw = _mapping(payload.get("image_budget"), "profile_image_budget")
        _reject_unknown(image_budget_raw, {"max_bytes", "max_height"}, "profile_image_budget")
        image_budget = {
            "max_bytes": _positive_int(image_budget_raw.get("max_bytes"), "profile_max_bytes"),
            "max_height": _positive_int(image_budget_raw.get("max_height"), "profile_max_height"),
        }
        return cls(
            profile_id=_safe_id(payload.get("profile_id"), "profile_id"),
            version=_positive_int(payload.get("version"), "profile_version"),
            status=status,
            audience=audience,
            density=density,
            colors=colors,
            typography=normalized_typography,
            spacing=spacing,
            layout=normalized_layout,
            cell_formats=cell_formats,
            conditional_formats=conditional_formats,
            image_budget=image_budget,
            qa_gates=tuple(_safe_id(item, "qa_gate") for item in payload.get("qa_gates") or []),
        )

    def require_renderable(self) -> None:
        if self.status == "retired":
            raise LongImageContractError("long_image_profile_retired")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def digest(self) -> str:
        canonical = json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class LongImageColumnSpec:
    key: str
    label: str
    cell_format_ref: str = "text"
    min_width: int = 80

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "LongImageColumnSpec":
        payload = _mapping(value, "long_image_column")
        _reject_unknown(payload, {"key", "label", "cell_format_ref", "min_width"}, "long_image_column")
        return cls(
            key=_safe_id(payload.get("key"), "long_image_column_key"),
            label=_required_text(payload.get("label"), "long_image_column_label"),
            cell_format_ref=_safe_id(payload.get("cell_format_ref") or "text", "cell_format_ref"),
            min_width=_positive_int(payload.get("min_width", 80), "long_image_column_min_width"),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LongImageBlockSpec:
    block_id: str
    section_id: str
    block_type: str
    title: str
    note: str = ""
    columns: tuple[LongImageColumnSpec, ...] = ()
    rows: tuple[dict[str, Any], ...] = ()
    group_keys: tuple[str, ...] = ()
    chart_path: str = ""

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "LongImageBlockSpec":
        payload = _mapping(value, "long_image_block")
        _assert_no_sensitive_keys(payload)
        _reject_unknown(payload, {"block_id", "section_id", "block_type", "title", "note", "columns", "rows", "group_keys", "chart_path"}, "long_image_block")
        block_type = str(payload.get("block_type") or "")
        if block_type not in _ALLOWED_BLOCK_TYPES:
            raise LongImageContractError("long_image_block_type_invalid")
        columns_raw = payload.get("columns") or []
        rows_raw = payload.get("rows") or []
        if (
            not isinstance(columns_raw, Sequence)
            or isinstance(columns_raw, (str, bytes, bytearray))
            or not isinstance(rows_raw, Sequence)
            or isinstance(rows_raw, (str, bytes, bytearray))
        ):
            raise LongImageContractError("long_image_block_columns_and_rows_must_be_sequences")
        if any(not isinstance(item, Mapping) for item in rows_raw):
            raise LongImageContractError("long_image_table_row_mapping_required")
        columns = tuple(LongImageColumnSpec.from_mapping(item) for item in columns_raw)
        rows = tuple(dict(item) for item in rows_raw)
        chart_path = str(payload.get("chart_path") or "").strip()
        if block_type == "table" and not columns:
            raise LongImageContractError("long_image_table_columns_required")
        if block_type == "chart" and not chart_path:
            raise LongImageContractError("long_image_chart_path_required")
        return cls(
            block_id=_safe_id(payload.get("block_id"), "long_image_block_id"),
            section_id=_safe_id(payload.get("section_id") or payload.get("block_id"), "long_image_section_id"),
            block_type=block_type,
            title=_required_text(payload.get("title"), "long_image_block_title"),
            note=str(payload.get("note") or "").strip(),
            columns=columns,
            rows=rows,
            group_keys=tuple(_safe_id(item, "long_image_group_key") for item in payload.get("group_keys") or []),
            chart_path=chart_path,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LongImageRenderSpec:
    report_artifact_ref: str
    report_run_id: str
    profile_id: str
    profile_version: int
    title: str
    subtitle: str
    currency: str
    blocks: tuple[LongImageBlockSpec, ...]
    limitations: tuple[str, ...] = ()
    schema_version: str = LONG_IMAGE_RENDER_SPEC_VERSION

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "LongImageRenderSpec":
        payload = _mapping(value, "long_image_render_spec")
        _assert_no_sensitive_keys(payload)
        _reject_unknown(payload, {"schema_version", "report_artifact_ref", "report_run_id", "profile_id", "profile_version", "title", "subtitle", "currency", "blocks", "limitations"}, "long_image_render_spec")
        if str(payload.get("schema_version") or LONG_IMAGE_RENDER_SPEC_VERSION) != LONG_IMAGE_RENDER_SPEC_VERSION:
            raise LongImageContractError("long_image_render_spec_version_invalid")
        blocks = tuple(LongImageBlockSpec.from_mapping(item) for item in payload.get("blocks") or [])
        if not blocks:
            raise LongImageContractError("long_image_render_blocks_required")
        block_ids = [item.block_id for item in blocks]
        if len(set(block_ids)) != len(block_ids):
            raise LongImageContractError("long_image_render_block_ids_duplicate")
        return cls(
            report_artifact_ref=_required_text(payload.get("report_artifact_ref"), "report_artifact_ref"),
            report_run_id=_required_text(payload.get("report_run_id"), "report_run_id"),
            profile_id=_safe_id(payload.get("profile_id"), "profile_id"),
            profile_version=_positive_int(payload.get("profile_version"), "profile_version"),
            title=_required_text(payload.get("title"), "long_image_title"),
            subtitle=str(payload.get("subtitle") or "").strip(),
            currency=_safe_id(payload.get("currency") or "USD", "currency"),
            blocks=blocks,
            limitations=tuple(str(item).strip() for item in payload.get("limitations") or [] if str(item).strip()),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LongImageArtifact:
    artifact_id: str
    report_artifact_ref: str
    report_run_id: str
    profile_id: str
    profile_version: int
    profile_digest: str
    path: str
    sha256: str
    byte_size: int
    width: int
    height: int
    section_count: int
    table_row_counts: dict[str, int]
    checks: tuple[dict[str, Any], ...]
    font_resolution: dict[str, str] = field(default_factory=dict)
    limitations: tuple[str, ...] = ()
    unscaled_stitch: bool = True
    no_cell_wrap: bool = True
    no_cell_truncation: bool = True
    schema_version: str = LONG_IMAGE_ARTIFACT_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LongImageOutputBundle:
    mode: str
    report_artifact_ref: str
    report_run_id: str
    profile_id: str
    profile_version: int
    full_image: LongImageArtifact | None = None
    section_images: tuple[LongImageArtifact, ...] = ()
    section_order: tuple[str, ...] = ()
    checks: tuple[dict[str, Any], ...] = ()
    schema_version: str = LONG_IMAGE_OUTPUT_BUNDLE_VERSION

    def __post_init__(self) -> None:
        if self.mode not in _ALLOWED_OUTPUT_MODES:
            raise LongImageContractError("long_image_output_mode_invalid")
        if self.mode in {"full", "both"} and self.full_image is None:
            raise LongImageContractError("long_image_output_full_image_required")
        if self.mode == "sections" and self.full_image is not None:
            raise LongImageContractError("long_image_output_full_image_forbidden")
        if self.mode in {"sections", "both"} and not self.section_images:
            raise LongImageContractError("long_image_output_section_images_required")
        if self.mode == "full" and self.section_images:
            raise LongImageContractError("long_image_output_section_images_forbidden")
        if len(self.section_images) != len(self.section_order):
            raise LongImageContractError("long_image_output_section_order_mismatch")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FeishuProjectionPlan:
    mode: str
    document_title: str
    image_artifact_ref: str
    caption: str
    required_image_count: int
    expected_width: int
    expected_height: int
    readback_checks: tuple[str, ...]
    route_ref: str = ""
    include_sheet: bool = False
    limitations: tuple[str, ...] = ()
    schema_version: str = FEISHU_PROJECTION_PLAN_VERSION

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "FeishuProjectionPlan":
        payload = _mapping(value, "feishu_projection_plan")
        _assert_no_sensitive_keys(payload)
        _reject_unknown(payload, {"schema_version", "mode", "document_title", "image_artifact_ref", "caption", "required_image_count", "expected_width", "expected_height", "readback_checks", "route_ref", "include_sheet", "limitations"}, "feishu_projection_plan")
        mode = str(payload.get("mode") or "")
        if mode not in _ALLOWED_PROJECTION_MODES:
            raise LongImageContractError("feishu_projection_mode_invalid")
        route_ref = str(payload.get("route_ref") or "").strip()
        if route_ref and not _SAFE_ROUTE.fullmatch(route_ref):
            raise LongImageContractError("feishu_projection_route_ref_invalid")
        required_image_count = _positive_int(payload.get("required_image_count", 1), "required_image_count")
        if required_image_count != 1:
            raise LongImageContractError("feishu_projection_requires_one_long_image")
        return cls(
            mode=mode,
            document_title=_required_text(payload.get("document_title"), "document_title"),
            image_artifact_ref=_required_text(payload.get("image_artifact_ref"), "image_artifact_ref"),
            caption=str(payload.get("caption") or "").strip(),
            required_image_count=required_image_count,
            expected_width=_positive_int(payload.get("expected_width"), "expected_width"),
            expected_height=_positive_int(payload.get("expected_height"), "expected_height"),
            readback_checks=tuple(_safe_id(item, "readback_check") for item in payload.get("readback_checks") or []),
            route_ref=route_ref,
            include_sheet=bool(payload.get("include_sheet", False)),
            limitations=tuple(str(item).strip() for item in payload.get("limitations") or [] if str(item).strip()),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


__all__ = [
    "CellFormatSpec",
    "ConditionalFormatSpec",
    "FEISHU_PROJECTION_PLAN_VERSION",
    "FeishuProjectionPlan",
    "LONG_IMAGE_ARTIFACT_VERSION",
    "LONG_IMAGE_OUTPUT_BUNDLE_VERSION",
    "LONG_IMAGE_PROFILE_SCHEMA_VERSION",
    "LONG_IMAGE_RENDER_SPEC_VERSION",
    "LongImageArtifact",
    "LongImageOutputBundle",
    "LongImageBlockSpec",
    "LongImageColumnSpec",
    "LongImageContractError",
    "LongImageRenderSpec",
    "LongImageVisualProfile",
]
