"""Bounded scalar traversal, preserving literal keys and typed array indices."""

import json
import math
import re
from dataclasses import dataclass
from typing import Any

type RawPath = tuple[str | int, ...]
type Scalar = str | int | float | bool | None

MAX_ENTITIES = 4096
MAX_DEPTH = 16
MAX_ARRAY = 128
MAX_NODES = 20_000
MAX_PATH_LENGTH = 512
_KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_.\[\]-]{0,127}\Z")
_SENSITIVE = re.compile(
    r"secret|password|passwd|token|access[_.-]?key|api[_.-]?key|credential|authorization|certificate|signature|(?:^|[_.])sn(?:$|[_.])|serial|macaddress|sn$",
    re.I,
)


class QuotaLimitError(ValueError):
    """Reject an oversized snapshot without logging any paths or values."""


def identity(path: RawPath) -> str:
    """JSON string vs integer tokens make source access unambiguous."""
    return json.dumps(path, separators=(",", ":"), ensure_ascii=True)


def display_path(path: RawPath) -> str:
    """Human-readable dotted path, never used for value lookup or identity."""
    result = ""
    for part in path:
        result += f"[{part}]" if isinstance(part, int) else ("." if result else "") + part
    return result


def safe_key(key: object, sensitive_values: tuple[str, ...] = ()) -> bool:
    return (
        isinstance(key, str)
        and bool(_KEY.fullmatch(key))
        and not _SENSITIVE.search(key)
        and not any(value and value.casefold() in key.casefold() for value in sensitive_values)
    )


@dataclass(frozen=True)
class Snapshot:
    """Only the current safe leaves, without envelope metadata or history."""

    leaves: dict[RawPath, Scalar]
    excluded: int = 0


def extract_leaves(data: dict[str, Any], sensitive_values: tuple[str, ...] = ()) -> Snapshot:
    """Enumerate every safe scalar, including nulls and unknown fields.

    Empty containers have no scalar leaf. Limits reject the entire snapshot,
    rather than fabricate missing readings. Sensitive subtrees are excluded.
    Overlong/nonfinite scalar values retain their path with an unknown value.
    """
    leaves: dict[RawPath, Scalar] = {}
    nodes = 0
    excluded = 0

    def visit(value: Any, path: RawPath) -> None:
        nonlocal nodes, excluded
        nodes += 1
        if nodes > MAX_NODES or len(path) > MAX_DEPTH or len(identity(path)) > MAX_PATH_LENGTH:
            raise QuotaLimitError("Quota traversal limit exceeded")
        if isinstance(value, dict):
            if len(value) > MAX_ENTITIES:
                raise QuotaLimitError("Quota object limit exceeded")
            for key in sorted(value, key=str):
                if (
                    not safe_key(key, sensitive_values)
                    or key.startswith("_cached")
                    or key == "_has_loadCmdChCtrlInfos"
                ):
                    excluded += 1
                    continue
                visit(value[key], (*path, key))
        elif isinstance(value, list):
            if len(value) > MAX_ARRAY:
                raise QuotaLimitError("Quota array limit exceeded")
            for index, child in enumerate(value):
                visit(child, (*path, index))
        elif value is None or type(value) in (str, int, float, bool):
            if isinstance(value, str) and any(
                secret and secret.casefold() in value.casefold() for secret in sensitive_values
            ):
                excluded += 1
                return
            if isinstance(value, str) and len(value) > 255:
                value = None
            if type(value) in (int, float) and (abs(value) > 1e100 or not math.isfinite(value)):
                value = None
            leaves[path] = value
            if len(leaves) > MAX_ENTITIES:
                raise QuotaLimitError("Quota scalar limit exceeded")
        else:
            excluded += 1

    visit(data, ())
    return Snapshot(leaves, excluded)
