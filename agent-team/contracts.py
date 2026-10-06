"""Structured role outputs and local validation of the supported schema subset."""
import math


def obj(**properties):
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


def array(items, minimum=0):
    return {"type": "array", "items": items, "minItems": minimum}


TEXT = {"type": "string"}
NONEMPTY = {"type": "string", "minLength": 1}
BOOL = {"type": "boolean"}
STRINGS = array(NONEMPTY)
CRITERIA = array(obj(id=NONEMPTY, description=NONEMPTY), 1)
FACTS = array(obj(fact=NONEMPTY, source=NONEMPTY))
BRIEF = obj(question=NONEMPTY, scope=NONEMPTY, acceptance_criteria=CRITERIA,
            constraints=STRINGS, architecture_facts=FACTS, allowed_commands=STRINGS)
SCHEMAS = {
    "analysis": obj(report=NONEMPTY, question=NONEMPTY, scope=NONEMPTY,
                    acceptance_criteria=CRITERIA, architecture_facts=FACTS),
    "checklist": obj(report=NONEMPTY, cases=array(obj(criterion_id=NONEMPTY,
                     test=NONEMPTY, evidence_required=NONEMPTY), 1)),
    "experiment": obj(report=NONEMPTY, recommendation={"type": "string", "enum": ["adopt", "eliminate", "unknown"]},
                      evidence=array(obj(criterion_id=NONEMPTY, observation=NONEMPTY, source=NONEMPTY, reproduce=NONEMPTY)),
                      unknowns=STRINGS, needs_human=BOOL, human_request=TEXT),
    "review": obj(report=NONEMPTY, evidence_sufficient=BOOL,
                  decision_supported={"type": "string", "enum": ["adopt", "eliminate", "unknown"]},
                  acceptance_checks=array(obj(id=NONEMPTY, sufficient=BOOL, evidence=TEXT), 1),
                  blockers=STRINGS, corrections=obj(A=STRINGS, B=STRINGS),
                  needs_human=BOOL, human_request=TEXT, major_rework=BOOL),
    "correction": obj(report=NONEMPTY, needs_human=BOOL, human_request=TEXT),
    "final": obj(report=NONEMPTY),
    "escalation": obj(report=NONEMPTY),
}


def validate(value, schema, path="output"):
    kind = schema["type"]
    valid = {"object": isinstance(value, dict), "array": isinstance(value, list),
             "string": isinstance(value, str), "boolean": type(value) is bool}[kind]
    if not valid:
        raise ValueError(f"{path}: expected {kind}")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{path}: invalid choice")
    if kind == "object":
        if set(value) != set(schema["required"]):
            raise ValueError(f"{path}: missing or unexpected fields")
        for key, spec in schema["properties"].items():
            validate(value[key], spec, f"{path}.{key}")
    elif kind == "array":
        if len(value) < schema.get("minItems", 0):
            raise ValueError(f"{path}: insufficient entries")
        for index, item in enumerate(value):
            validate(item, schema["items"], f"{path}[{index}]")
    elif kind == "string" and len(value.strip()) < schema.get("minLength", 0):
        raise ValueError(f"{path}: empty value")


def validate_brief(brief):
    validate(brief, BRIEF, "brief")
    ids = [c["id"] for c in brief["acceptance_criteria"]]
    if len(set(ids)) != len(ids):
        raise ValueError("brief: criterion IDs must be unique")
    if any(not (c.startswith("Bash(") and c.endswith(")")) for c in brief["allowed_commands"]):
        raise ValueError("brief: commands must be explicit Bash(...) permission patterns")


def seconds(value):
    if not math.isfinite(value) or value < 0:
        raise ValueError("Time must be finite and nonnegative")
    return value
