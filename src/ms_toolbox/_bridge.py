"""Run by a selected app's Python; it does not need ms_toolbox installed."""
from __future__ import annotations

import contextlib
import enum
import importlib
import importlib.metadata
import importlib.util
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import get_origin


def json_value(value):
    if isinstance(value, enum.Enum):
        return value.value
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, (set, tuple)):
        return list(value)
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Cannot transfer configuration value {type(value).__name__}")


def snapshot(provider):
    entries = []
    values, sources = {}, {}
    for entry in provider.entries():
        data = asdict(entry)
        annotation = get_origin(entry.annotation) or entry.annotation
        kind = next((name for name, cls in {"bool": bool, "int": int, "float": float, "path": Path, "list": list, "dict": dict, "tuple": tuple, "set": set}.items() if annotation is cls), "str")
        if isinstance(annotation, type) and issubclass(annotation, enum.Enum):
            data["choices"] = [member.value for member in annotation]
        data["annotation"] = kind
        entries.append(data)
        values[entry.path] = provider.get_value(entry.path)
        sources[entry.path] = provider.get_source(entry.path)
    return {
        "config_id": provider.config_id, "display_name": provider.display_name,
        "description": getattr(provider, "description", ""), "entries": entries,
        "global_path": str(provider.global_path),
        "default_path": str(provider.default_path or ""),
        "values": values, "sources": sources,
    }


def handle(request):
    if request["action"] == "probe":
        try:
            version = importlib.metadata.version(request["distribution"])
        except importlib.metadata.PackageNotFoundError:
            return {"version": "", "error": ""}
        available = importlib.util.find_spec(request["package"]) is not None
        return {"version": version, "error": "" if available else "Installed metadata exists, but the application module is missing."}
    module, name = request["factory"].split(":")
    provider = getattr(importlib.import_module(module), name)()
    action = request["action"]
    if action == "set":
        provider.set_global_value(request["path"], request["value"])
    elif action == "reset":
        if request["target"] != "default":
            raise ValueError("Toolbox edits global settings; only reset to default is available.")
        provider.reset_value(request["path"], "default")
    elif action != "snapshot":
        raise ValueError(f"Unknown configuration action: {action}")
    return snapshot(provider)


if __name__ == "__main__":
    try:
        # Provider notices belong on stderr; stdout is only the JSON response.
        with contextlib.redirect_stdout(sys.stderr):
            response = handle(json.load(sys.stdin))
        print(json.dumps(response, default=json_value))
    except Exception as exc:
        print(json.dumps({"error": str(exc)}))
        raise SystemExit(1)
