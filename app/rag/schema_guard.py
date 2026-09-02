"""Provider-independent enforcement of the structured-output contract (BR-79).

BR-79 says the answer is *forced* into a schema. Anthropic and Gemini both offer
that server-side, but the guarantee then belongs to whichever provider is
configured - and BR-79 is not a convenience. It is what makes citation checking
deterministic (DD-8) and it is the outermost injection defence: an instruction
that hijacks the model still cannot produce anything outside this shape (SP §1.4).

So the schema is validated here as well, on our side, for every provider. When
the provider enforces it too this pass never fails and costs nothing. When a
provider's enforcement is partial - or a future one has none - the contract
still holds, and the caller retries once before giving up (BR-80).

A focused validator rather than `jsonschema`: the two schemas in this system are
small and fixed, and the u1 image budget (743MB) is worth more than the
generality.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.ok


def validate(payload: object, schema: dict, path: str = "$") -> ValidationResult:
    errors: list[str] = []
    _check(payload, schema, path, errors)
    return ValidationResult(ok=not errors, errors=errors)


def _check(value: object, schema: dict, path: str, errors: list[str]) -> None:
    expected = schema.get("type")
    types = expected if isinstance(expected, list) else [expected] if expected else []

    if types and not _type_matches(value, types):
        names = "|".join(str(t) for t in types)
        errors.append(f"{path}: expected {names}, got {type(value).__name__}")
        return

    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: {value!r} not in {schema['enum']}")
        return

    if isinstance(value, dict) and "object" in types:
        _check_object(value, schema, path, errors)
    elif isinstance(value, list) and "array" in types:
        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(value):
                _check(item, item_schema, f"{path}[{index}]", errors)


def _check_object(value: dict, schema: dict, path: str, errors: list[str]) -> None:
    properties = schema.get("properties") or {}
    for name in schema.get("required") or []:
        if name not in value:
            errors.append(f"{path}: missing required property {name!r}")
    if schema.get("additionalProperties") is False:
        for name in value:
            if name not in properties:
                # Not pedantry: an extra key is the visible edge of a model that
                # ignored the contract, and the rest of the payload is suspect.
                errors.append(f"{path}: unexpected property {name!r}")
    for name, sub_schema in properties.items():
        if name in value:
            _check(value[name], sub_schema, f"{path}.{name}", errors)


def _type_matches(value: object, types: list) -> bool:
    for expected in types:
        if expected is None or expected == "null":
            if value is None:
                return True
        elif expected == "object" and isinstance(value, dict):
            return True
        elif expected == "array" and isinstance(value, list):
            return True
        elif expected == "string" and isinstance(value, str):
            return True
        elif expected == "integer" and isinstance(value, int):
            if not isinstance(value, bool):
                return True
        elif expected == "number" and isinstance(value, int | float):
            if not isinstance(value, bool):
                return True
        elif expected == "boolean" and isinstance(value, bool):
            return True
    return False


def to_gemini_schema(schema: dict) -> dict:
    """Translate the canonical JSON Schema into Gemini's OpenAPI 3.0 subset.

    Gemini rejects `additionalProperties`, so it is dropped here - which is
    exactly why `validate()` above is not optional. The key the provider will no
    longer reject is the key we now have to check ourselves.

    `propertyOrdering` is set from the declaration order: Gemini honours it, and
    a stable field order keeps prompt-cache prefixes stable too (BR-94).
    """
    out: dict = {}
    for key, value in schema.items():
        if key == "additionalProperties":
            continue
        if key == "properties" and isinstance(value, dict):
            out["properties"] = {k: to_gemini_schema(v) for k, v in value.items()}
            out["propertyOrdering"] = list(value.keys())
        elif key == "items" and isinstance(value, dict):
            out["items"] = to_gemini_schema(value)
        elif key == "type" and isinstance(value, list):
            # Gemini has no union types; take the non-null branch and mark it
            # nullable instead.
            concrete = [t for t in value if t not in (None, "null")]
            out["type"] = concrete[0] if concrete else "string"
            if len(concrete) != len(value):
                out["nullable"] = True
        elif key == "enum" and isinstance(value, list):
            # `null` cannot appear in a Gemini enum; nullability carries it.
            cleaned = [v for v in value if v is not None]
            out["enum"] = cleaned
            if len(cleaned) != len(value):
                out["nullable"] = True
        else:
            out[key] = value
    return out
