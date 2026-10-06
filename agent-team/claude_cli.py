"""Claude CLI process boundary; subscriptions and existing permissions are retained."""
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent


def invoke(state, role, phase, payload, schema, log_path):
    model = state["models"][role]
    tools = ["Read", "Glob", "Grep", "WebSearch", "WebFetch", "Bash"]
    allowed = ["Read", "Glob", "Grep", "WebSearch", "WebFetch"]
    allowed += state["approved_brief"]["allowed_commands"]
    if role == "B":
        tools += ["Edit", "Write"]
        # A double leading slash is Claude's absolute-path permission syntax.
        allowed += [f"Edit(/{state['workspace']}/**)", f"Write(/{state['workspace']}/**)"]
    agent = "poc-" + role.lower()
    prompt = (ROOT / "roles" / f"{role.lower()}.md").read_text(encoding="utf-8")
    definition = {agent: {"description": f"Technical PoC role {role}", "prompt": prompt,
                          "model": model, "tools": tools}}
    argv = [state["claude_bin"], "-p", "--agent", agent, "--agents", json.dumps(definition),
            "--model", model, "--tools", ",".join(tools), "--allowedTools", ",".join(allowed),
            "--permission-mode", "dontAsk", "--settings", '{"autoMemoryEnabled":false}',
            "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
            "--output-format", "stream-json", "--verbose", "--json-schema", json.dumps(schema)]
    session = state["sessions"].get(role)
    if session:
        argv += ["--resume", session]
    request = {"role": role, "phase": phase, "input": payload,
               "resume_session": session}
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.with_suffix(".input.json").write_text(json.dumps(request, ensure_ascii=False, indent=2), encoding="utf-8")
    env = dict(os.environ)
    env.pop("CLAUDECODE", None)  # Separate child sessions when launched inside Claude Code.
    env["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] = "1"
    print(f"[{role}/{phase}] {model}", flush=True)
    result = subprocess.run(argv, input=json.dumps(request, ensure_ascii=False), text=True,
                            capture_output=True, cwd=state["workspace"], env=env)
    log_path.with_suffix(".stdout.jsonl").write_text(result.stdout, encoding="utf-8")
    log_path.with_suffix(".stderr.txt").write_text(result.stderr, encoding="utf-8")
    try:
        messages = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
    except json.JSONDecodeError as error:
        raise ValueError(f"{role}/{phase}: invalid Claude JSON; see {log_path}.stdout.jsonl") from error
    if not all(isinstance(message, dict) for message in messages):
        raise ValueError(f"{role}/{phase}: invalid Claude stream; see {log_path}.stdout.jsonl")
    results = [message for message in messages if message.get("type") == "result"]
    if result.returncode or len(results) != 1 or results[0].get("is_error") or results[0].get("subtype") != "success":
        raise ValueError(f"{role}/{phase}: Claude call failed; see {log_path}.stdout.jsonl")
    response = results[0]
    if response.get("permission_denials"):
        raise ValueError(f"{role}/{phase}: tool permission denied; approve a brief change before retrying")
    models = []
    for message in messages:
        if message.get("type") == "assistant" and message.get("parent_tool_use_id") is None:
            body = message.get("message")
            model_id = body.get("model") if isinstance(body, dict) else None
            if not isinstance(model_id, str) or not model_id.strip():
                raise ValueError(f"{role}/{phase}: actual role model identity unavailable")
            models.append(model_id)
    if not models:
        raise ValueError(f"{role}/{phase}: actual model identity unavailable")
    session_id = response.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        raise ValueError(f"{role}/{phase}: session ID unavailable")
    return {"output": response.get("structured_output"), "session_id": session_id, "models": sorted(set(models))}
