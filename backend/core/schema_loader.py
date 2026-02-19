"""
Schema loader: YAML templates as single source of truth.
Derives form schema from YAML structure; merges form data; validates required fields.
"""
import copy
import os
import re
from typing import Any, Dict, List, Tuple

import yaml

# Resolve templates dir relative to this module (backend/core/templates). Works when run
# from project root, as installed package, or in production; __file__ is always this module.
_THIS_DIR = os.path.dirname(os.path.abspath(os.path.realpath(__file__)))
TEMPLATES_DIR = os.path.join(_THIS_DIR, "templates")


def _ensure_list(val: Any) -> List[str]:
    """Convert string (newline/comma-separated) or list to list of trimmed strings."""
    if val is None:
        return []
    if isinstance(val, list):
        return [str(x).strip() for x in val if x is not None]
    s = str(val).strip()
    if not s:
        return []
    items = []
    for line in s.replace(",", "\n").split("\n"):
        item = line.strip()
        if item:
            items.append(item)
    return items


def load_yaml_template(template_name: str) -> dict:
    """Load template from core/templates/{template_name}.yaml."""
    base = template_name.replace(".yaml", "")
    path = os.path.join(TEMPLATES_DIR, f"{base}.yaml")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Template not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Template {template_name} is not a valid YAML object")
    return data


def _is_multiline_key(key: str, value: Any) -> bool:
    """Whether a string field should use a multiline (textarea) input."""
    key_lower = key.lower()
    if "\n" in str(value or ""):
        return True
    if any(part in key_lower for part in ("template", "script", "html", "description", "address", "text", "nuggets", "objections", "forbidden", "rules")):
        return True
    if isinstance(value, str) and len(value) > 100:
        return True
    return False


def _walk_yaml(
    obj: Any,
    path: str = "",
) -> List[Dict[str, Any]]:
    """Recursively walk YAML and produce flat field descriptors. All dicts are expanded (including leaf key-value maps)."""
    fields: List[Dict[str, Any]] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}" if path else k
            if isinstance(v, dict):
                fields.extend(_walk_yaml(v, p))
            elif isinstance(v, list):
                if v and isinstance(v[0], dict):
                    item_schema = _walk_yaml(v[0], "")  # fields for one item (paths relative to item, e.g. "id", "role")
                    fields.append({
                        "path": p,
                        "type": "array",
                        "itemType": "object",
                        "required": False,
                        "default": v,
                        "label": _path_to_display_label(p),
                        "group": _path_to_group(p),
                        "itemSchema": item_schema,
                    })
                else:
                    fields.append({
                        "path": p,
                        "type": "array",
                        "itemType": "string",
                        "required": False,
                        "default": v if v is not None else [],
                        "label": _path_to_display_label(p),
                        "group": _path_to_group(p),
                    })
            elif isinstance(v, bool):
                fields.append({
                    "path": p,
                    "type": "boolean",
                    "required": False,
                    "default": v,
                    "label": _path_to_display_label(p),
                    "group": _path_to_group(p),
                })
            elif isinstance(v, (int, float)):
                fields.append({
                    "path": p,
                    "type": "number",
                    "required": False,
                    "default": v,
                    "label": _path_to_display_label(p),
                    "group": _path_to_group(p),
                })
            else:
                s = str(v) if v is not None else ""
                required = s.strip() == "REQUIRED"
                multiline = _is_multiline_key(k, v)
                fields.append({
                    "path": p,
                    "type": "string",
                    "required": required,
                    "default": "" if required else s,
                    "label": _path_to_display_label(p),
                    "group": _path_to_group(p),
                    "multiline": multiline,
                })
    return fields


def _path_to_label(key: str) -> str:
    """Convert snake_case to Title Case."""
    return key.replace("_", " ").title()


def _path_to_display_label(path: str) -> str:
    """Build unambiguous label from full path so 'modules.local_seo.enabled' -> 'Local Seo › Enabled'."""
    parts = path.split(".")
    if not parts:
        return ""
    # Skip first segment (section name) so we don't repeat it; use rest for label
    segs = parts[1:] if len(parts) > 1 else parts
    return " › ".join(_path_to_label(p) for p in segs)


def _path_to_group(path: str) -> str:
    """Second path segment as humanized group name for sub-grouping in UI (e.g. 'modules.local_seo.enabled' -> 'Local Seo')."""
    parts = path.split(".")
    if len(parts) < 2:
        return ""
    return _path_to_label(parts[1])


def yaml_to_form_schema(yaml_doc: dict) -> dict:
    """Produce form schema from YAML (flat fields list + structure for sections)."""
    fields = _walk_yaml(yaml_doc)
    # Group by top-level key for sections
    sections: Dict[str, List[Dict]] = {}
    for f in fields:
        top = f["path"].split(".")[0]
        if top not in sections:
            sections[top] = []
        sections[top].append(f)
    return {"fields": fields, "sections": sections}


def _get_nested(d: dict, path: str) -> Any:
    """Get value at dot path."""
    keys = path.split(".")
    obj = d
    for k in keys:
        obj = obj.get(k) if isinstance(obj, dict) else None
        if obj is None:
            return None
    return obj


def _set_nested(d: dict, path: str, value: Any) -> None:
    """Set value at dot path, creating nested dicts as needed."""
    keys = path.split(".")
    obj = d
    for k in keys[:-1]:
        if k not in obj or not isinstance(obj[k], dict):
            obj[k] = {}
        obj = obj[k]
    obj[keys[-1]] = value


def _coerce_value(form_val: Any, template_val: Any) -> Any:
    """Coerce form value to match template type. Preserves list-of-dicts from form."""
    if form_val is None:
        return template_val
    if isinstance(template_val, bool):
        return bool(form_val)
    if isinstance(template_val, (int, float)):
        try:
            return int(form_val) if isinstance(template_val, int) else float(form_val)
        except (TypeError, ValueError):
            return template_val
    if isinstance(template_val, list):
        if isinstance(form_val, list):
            if template_val and isinstance(template_val[0], dict):
                return form_val  # keep array-of-object as-is
            return form_val
        return _ensure_list(form_val)
    return str(form_val).strip() if form_val else ""


def merge_form_into_template(template: dict, form_data: dict) -> dict:
    """
    Deep merge form_data into template. Form values override.
    Handles: string, array (from string newline-separated or list), boolean, number.
    """
    result = copy.deepcopy(template)

    def merge_recursive(target: dict, source: dict) -> None:
        for k, v in source.items():
            t_val = target.get(k)
            if isinstance(v, dict):
                if t_val is None or not isinstance(t_val, dict):
                    target[k] = {}
                    t_val = target[k]
                merge_recursive(t_val, v)
            else:
                target[k] = _coerce_value(v, t_val if t_val is not None else "")

    merge_recursive(result, form_data)
    return result


def validate_required(schema: dict, merged: dict) -> Tuple[bool, str]:
    """Check required fields. Return (True, "") or (False, error_message)."""
    for f in schema.get("fields", []):
        if not f.get("required"):
            continue
        path = f["path"]
        val = _get_nested(merged, path)
        if val is None:
            return False, f"{f.get('label', path)} is required"
        if isinstance(val, str) and not val.strip():
            return False, f"{f.get('label', path)} is required"
        if isinstance(val, list) and len(val) == 0:
            # Optional: empty list may be ok for some required arrays
            pass
    return True, ""
