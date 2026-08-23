from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import shlex
import subprocess
from typing import Any
from urllib import error, request

from simple_flow_test_harness.commands import run_command
from simple_flow_test_harness.models import CommandResult, Phase4Config
from simple_flow_test_harness.transcript import compact_text


CODEX_BACKEND = "codex"
LOCAL_OPENAI_BACKEND = "local-openai"
SUPPORTED_AGENT_BACKENDS = (CODEX_BACKEND, LOCAL_OPENAI_BACKEND)
DEFAULT_AGENT_BACKEND = CODEX_BACKEND
DEFAULT_LOCAL_LLM_URL = "http://169.254.83.107:1234"
DEFAULT_LOCAL_LLM_MODEL = "google/gemma-4-e4b"
CODEX_NOT_USED = "not used by local-openai backend"

SKILL_ALIASES = {
    "@discussion": "discussion",
    "@documentation-curation": "documentation-curation",
    "@issue-draft": "issue-draft",
    "@start-implement": "start-implement",
    "@review-triage": "review-triage",
    "@pr-finalize": "pr-finalize",
}


@dataclass(frozen=True)
class AgentTurnResult:
    command_result: CommandResult
    session_id: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LocalToolCall:
    call_id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ToolExecution:
    content: dict[str, Any]
    exit_code: int | None = None
    finish_turn: bool = False


class LocalLLMError(RuntimeError):
    pass


class CodexCliBackend:
    name = CODEX_BACKEND
    codex_cli_used = True

    def __init__(self, config: Phase4Config):
        self.config = config
        self.model = config.codex_model
        self.endpoint = _codex_endpoint_label(config)

    def run_action(
        self,
        *,
        project_path: Path,
        prompt: str,
        session_id: str,
        scenario_id: str,
        action_ref: str,
        timeout_seconds: int,
    ) -> AgentTurnResult:
        command = self._codex_command(project_path, prompt, session_id)
        try:
            result = run_command(
                command,
                cwd=project_path,
                timeout_seconds=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            result = _timeout_result(project_path, scenario_id, action_ref, exc, backend_label="Codex")
        return AgentTurnResult(
            command_result=result,
            session_id=session_id or _extract_thread_id(result.stdout),
            metadata={
                "backend": self.name,
                "model": self.model,
                "endpoint": self.endpoint,
                "codex_cli_used": self.codex_cli_used,
                "tool_call_count": 0,
                "script_invocations": [],
            },
        )

    def prerequisite_evidence(self, *, source_root: Path, timeout_seconds: int) -> tuple[list[str], dict[str, Any]]:
        try:
            result = run_command([self.config.codex_command, "--version"], cwd=source_root, timeout_seconds=30)
        except (OSError, TimeoutError) as exc:
            return [f"codex command unavailable: {exc}"], {}
        evidence = {"codex_version_command": result.to_json_data()}
        if result.exit_code != 0:
            return [f"codex command failed: {result.stderr or result.stdout}"], evidence
        return [], evidence

    def version_label(self, *, source_root: Path) -> str:
        try:
            result = run_command([self.config.codex_command, "--version"], cwd=source_root, timeout_seconds=30)
        except OSError as exc:
            return f"unavailable: {exc}"
        return (result.stdout or result.stderr).strip()

    def _codex_command(self, project_path: Path, prompt: str, session_id: str) -> list[str]:
        if session_id:
            command = [self.config.codex_command, "exec", "resume", "--json"]
        else:
            command = [
                self.config.codex_command,
                "exec",
                "--json",
                "-C",
                str(project_path),
            ]
        if self.config.codex_bypass_sandbox:
            command.append("--dangerously-bypass-approvals-and-sandbox")
        else:
            command.append("--full-auto")
        if self.config.codex_oss:
            provider = _codex_local_provider(self.config)
            command.extend(["-c", f'model_provider="{provider}"'])
        if self.config.codex_oss and not session_id:
            command.append("--oss")
            command.extend(["--local-provider", _codex_local_provider(self.config)])
        if self.config.codex_model:
            command.extend(["--model", self.config.codex_model])
        if session_id:
            command.append(session_id)
        command.append(prompt)
        return command


class OpenAICompatibleLocalBackend:
    name = LOCAL_OPENAI_BACKEND
    codex_cli_used = False

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        max_tool_calls: int = 8,
    ):
        self.base_url = base_url.rstrip("/")
        self.endpoint = self.base_url
        self.model = model
        self.max_tool_calls = max_tool_calls
        self._sessions: dict[str, list[dict[str, Any]]] = {}

    def prerequisite_evidence(self, *, source_root: Path, timeout_seconds: int) -> tuple[list[str], dict[str, Any]]:
        del source_root
        evidence: dict[str, Any] = {
            "agent_backend": self.name,
            "agent_endpoint": self.endpoint,
            "agent_model": self.model,
            "codex_cli_used": False,
            "codex_version_command": {"skipped": CODEX_NOT_USED},
        }
        try:
            models = self._get_models(timeout_seconds=min(timeout_seconds, 30))
        except LocalLLMError as exc:
            return [f"local OpenAI-compatible backend unavailable: {exc}"], evidence
        evidence["local_models"] = models
        available = _model_ids(models)
        if self.model and available and self.model not in available:
            return [f"local model {self.model} not listed by {self.endpoint}/v1/models"], evidence
        return [], evidence

    def version_label(self, *, source_root: Path) -> str:
        del source_root
        return CODEX_NOT_USED

    def run_action(
        self,
        *,
        project_path: Path,
        prompt: str,
        session_id: str,
        scenario_id: str,
        action_ref: str,
        timeout_seconds: int,
    ) -> AgentTurnResult:
        session_id = session_id or f"local-openai-{scenario_id}"
        messages = self._sessions.setdefault(
            session_id,
            [{"role": "system", "content": _local_system_prompt(project_path)}],
        )
        skill_context, resolved_skills = _resolved_skill_context(project_path, prompt)
        user_prompt = prompt
        if skill_context:
            user_prompt = f"{prompt}\n\nResolved Skill Context:\n{skill_context}"
        messages.append({"role": "user", "content": user_prompt})

        events: list[dict[str, Any]] = []
        metadata: dict[str, Any] = {
            "backend": self.name,
            "model": self.model,
            "endpoint": self.endpoint,
            "codex_cli_used": False,
            "resolved_skills": resolved_skills,
            "tool_call_count": 0,
            "script_invocations": [],
        }
        exit_code = 0
        stderr = ""

        try:
            for turn_index in range(self.max_tool_calls + 1):
                force_tool = turn_index == 0 and _prompt_requires_command_tool(prompt)
                response = self._chat_completion(
                    messages=messages,
                    timeout_seconds=timeout_seconds,
                    tool_choice="required" if force_tool else "auto",
                    tools=_local_tools(include_finish=not force_tool),
                )
                message = _assistant_message(response)
                if not message:
                    raise LocalLLMError("chat completion response did not contain an assistant message")

                tool_calls = _extract_tool_calls(response)
                if tool_calls:
                    messages.append(_assistant_message_for_history(message))
                    for tool_call in tool_calls:
                        execution = self._execute_tool_call(
                            tool_call,
                            project_path=project_path,
                            timeout_seconds=timeout_seconds,
                        )
                        metadata["tool_call_count"] += 1
                        if invocation := execution.content.get("script_invocation"):
                            metadata["script_invocations"].append(invocation)
                        if execution.exit_code not in (None, 0):
                            exit_code = 124 if execution.exit_code == 124 else 1
                        events.append(_tool_event(tool_call, execution))
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_call.call_id,
                                "name": tool_call.name,
                                "content": json.dumps(execution.content, ensure_ascii=True),
                            }
                        )
                        if execution.finish_turn:
                            return _local_turn_result(
                                project_path=project_path,
                                scenario_id=scenario_id,
                                action_ref=action_ref,
                                session_id=session_id,
                                exit_code=exit_code,
                                events=events,
                                stderr=stderr,
                                metadata=metadata,
                            )
                    continue

                content = _message_content(message)
                command_events, command_exit_code = self._run_command_protocol(
                    content,
                    project_path=project_path,
                    timeout_seconds=timeout_seconds,
                )
                if command_events:
                    events.extend(command_events)
                    metadata["tool_call_count"] += len(command_events)
                    for event in command_events:
                        if invocation := event.get("script_invocation"):
                            metadata["script_invocations"].append(invocation)
                    if command_exit_code != 0:
                        exit_code = command_exit_code
                    break

                events.append(
                    {
                        "type": "local_llm.message",
                        "message": content or "Local model returned no content.",
                    }
                )
                break
            else:
                exit_code = 1
                stderr = "Local OpenAI backend stopped: maximum tool call count exceeded."
                events.append({"type": "local_llm.stopped", "message": stderr})
        except LocalLLMError as exc:
            exit_code = 1
            stderr = f"Local OpenAI backend error: {exc}"
            events.append({"type": "local_llm.error", "message": stderr})

        return _local_turn_result(
            project_path=project_path,
            scenario_id=scenario_id,
            action_ref=action_ref,
            session_id=session_id,
            exit_code=exit_code,
            events=events,
            stderr=stderr,
            metadata=metadata,
        )

    def _run_command_protocol(
        self,
        content: str,
        *,
        project_path: Path,
        timeout_seconds: int,
    ) -> tuple[list[dict[str, Any]], int]:
        commands = _command_protocol_lines(content)
        events: list[dict[str, Any]] = []
        exit_code = 0
        for command in commands:
            execution = self._execute_run_command(
                {"command": command},
                project_path=project_path,
                timeout_seconds=timeout_seconds,
            )
            if execution.exit_code not in (None, 0):
                exit_code = 124 if execution.exit_code == 124 else 1
            events.append(_tool_event(LocalToolCall("text-command", "run_command", {"command": command}), execution))
        return events, exit_code

    def _execute_tool_call(
        self,
        tool_call: LocalToolCall,
        *,
        project_path: Path,
        timeout_seconds: int,
    ) -> ToolExecution:
        if tool_call.name == "run_command":
            return self._execute_run_command(
                tool_call.arguments,
                project_path=project_path,
                timeout_seconds=timeout_seconds,
            )
        if tool_call.name == "read_file":
            return self._execute_read_file(tool_call.arguments, project_path=project_path)
        if tool_call.name == "list_files":
            return self._execute_list_files(tool_call.arguments, project_path=project_path)
        if tool_call.name == "finish":
            return ToolExecution(
                content={"summary": str(tool_call.arguments.get("summary", "")), "exit_code": 0},
                exit_code=0,
                finish_turn=True,
            )
        return ToolExecution(
            content={"error": f"Unknown local tool: {tool_call.name}", "exit_code": 1},
            exit_code=1,
        )

    def _execute_run_command(
        self,
        arguments: dict[str, Any],
        *,
        project_path: Path,
        timeout_seconds: int,
    ) -> ToolExecution:
        try:
            argv = _coerce_argv(arguments)
            _validate_agent_argv(argv)
        except ValueError as exc:
            return ToolExecution(
                content={"error": str(exc), "exit_code": 1},
                exit_code=1,
            )

        try:
            result = run_command(
                argv,
                cwd=project_path,
                timeout_seconds=min(timeout_seconds, int(arguments.get("timeout_seconds", timeout_seconds) or timeout_seconds)),
            )
        except subprocess.TimeoutExpired as exc:
            result = _timeout_result(project_path, "local", "tool", exc, backend_label="Local OpenAI")
        except OSError as exc:
            return ToolExecution(
                content={"argv": argv, "error": str(exc), "exit_code": 1},
                exit_code=1,
            )

        content: dict[str, Any] = {
            "argv": list(result.command),
            "exit_code": result.exit_code,
            "stdout": compact_text(result.stdout, 1600),
            "stderr": compact_text(result.stderr, 1200),
        }
        if invocation := _script_invocation(list(result.command)):
            content["script_invocation"] = invocation
        return ToolExecution(content=content, exit_code=result.exit_code)

    def _execute_read_file(self, arguments: dict[str, Any], *, project_path: Path) -> ToolExecution:
        try:
            path = _safe_project_path(project_path, str(arguments["relative_path"]))
        except (KeyError, ValueError) as exc:
            return ToolExecution(content={"error": str(exc), "exit_code": 1}, exit_code=1)
        if not path.exists() or not path.is_file():
            return ToolExecution(content={"error": f"file not found: {path}", "exit_code": 1}, exit_code=1)
        return ToolExecution(
            content={
                "relative_path": str(path.relative_to(project_path)).replace("\\", "/"),
                "content": compact_text(path.read_text(encoding="utf-8", errors="replace"), 5000),
                "exit_code": 0,
            },
            exit_code=0,
        )

    def _execute_list_files(self, arguments: dict[str, Any], *, project_path: Path) -> ToolExecution:
        root_value = str(arguments.get("relative_path", "."))
        try:
            root = _safe_project_path(project_path, root_value)
        except ValueError as exc:
            return ToolExecution(content={"error": str(exc), "exit_code": 1}, exit_code=1)
        max_files = int(arguments.get("max_files", 80) or 80)
        files: list[str] = []
        if root.exists():
            for path in sorted(root.rglob("*")):
                if ".git" in path.parts or not path.is_file():
                    continue
                files.append(str(path.relative_to(project_path)).replace("\\", "/"))
                if len(files) >= max_files:
                    break
        return ToolExecution(content={"files": files, "exit_code": 0}, exit_code=0)

    def _get_models(self, *, timeout_seconds: int) -> dict[str, Any]:
        return self._request_json("GET", "/v1/models", None, timeout_seconds=timeout_seconds)

    def _chat_completion(
        self,
        *,
        messages: list[dict[str, Any]],
        timeout_seconds: int,
        tool_choice: str,
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "tool_choice": tool_choice,
            "temperature": 0,
            "stream": False,
        }
        return self._request_json("POST", "/v1/chat/completions", payload, timeout_seconds=timeout_seconds)

    def _request_json(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None,
        *,
        timeout_seconds: int,
    ) -> dict[str, Any]:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = request.Request(
            self.base_url + path,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with request.urlopen(req, timeout=timeout_seconds) as response:
                response_text = response.read().decode("utf-8", errors="replace")
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise LocalLLMError(f"HTTP {exc.code} from {path}: {compact_text(body, 500)}") from exc
        except OSError as exc:
            raise LocalLLMError(str(exc)) from exc
        try:
            parsed = json.loads(response_text)
        except json.JSONDecodeError as exc:
            raise LocalLLMError(f"non-JSON response from {path}: {compact_text(response_text, 500)}") from exc
        if not isinstance(parsed, dict):
            raise LocalLLMError(f"unexpected JSON response from {path}")
        return parsed


def create_agent_backend(config: Phase4Config) -> CodexCliBackend | OpenAICompatibleLocalBackend:
    if config.agent_backend == CODEX_BACKEND:
        return CodexCliBackend(config)
    if config.agent_backend == LOCAL_OPENAI_BACKEND:
        return OpenAICompatibleLocalBackend(
            base_url=config.local_llm_url,
            model=config.local_llm_model,
            max_tool_calls=config.local_llm_max_tool_calls,
        )
    raise ValueError(f"Unsupported agent backend: {config.agent_backend}")


def _codex_endpoint_label(config: Phase4Config) -> str:
    if not config.codex_oss:
        return ""
    return f"codex-oss:{_codex_local_provider(config)}"


def _codex_local_provider(config: Phase4Config) -> str:
    return config.codex_local_provider or "lmstudio"


def _codex_provider_config_args(local_provider: str) -> list[str]:
    return ["-c", f'model_provider="{local_provider}"']


def probe_local_openai_backend(
    *,
    base_url: str,
    model: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    backend = OpenAICompatibleLocalBackend(base_url=base_url, model=model)
    models = backend._get_models(timeout_seconds=timeout_seconds)
    messages = [
        {
            "role": "user",
            "content": "Call the echo_probe tool with message set to ok.",
        }
    ]
    response = backend._chat_completion(
        messages=messages,
        timeout_seconds=timeout_seconds,
        tool_choice="required",
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "echo_probe",
                    "description": "Echo a short probe message.",
                    "parameters": {
                        "type": "object",
                        "properties": {"message": {"type": "string"}},
                        "required": ["message"],
                    },
                },
            }
        ],
    )
    tool_calls = _extract_tool_calls(response)
    return {
        "base_url": base_url.rstrip("/"),
        "model": model,
        "models_ok": bool(_model_ids(models)),
        "available_models": _model_ids(models),
        "chat_completions_ok": bool(response.get("choices")),
        "tool_calls_ok": any(call.name == "echo_probe" for call in tool_calls),
        "tool_calls": [
            {
                "id": call.call_id,
                "name": call.name,
                "arguments": call.arguments,
            }
            for call in tool_calls
        ],
    }


def probe_codex_local_llm_backend(
    *,
    base_url: str,
    model: str,
    codex_command: str,
    local_provider: str,
    source_root: Path,
    timeout_seconds: int,
) -> dict[str, Any]:
    backend = OpenAICompatibleLocalBackend(base_url=base_url, model=model)
    result: dict[str, Any] = {
        "base_url": base_url.rstrip("/"),
        "model": model,
        "codex_command": codex_command,
        "codex_local_provider": local_provider,
        "python_sdk_package_available": _python_codex_sdk_available(),
        "models_ok": False,
        "responses_ok": False,
        "responses_tool_calls_ok": False,
        "codex_exec_ok": False,
    }
    try:
        models = backend._get_models(timeout_seconds=min(timeout_seconds, 30))
        result["models_ok"] = bool(_model_ids(models))
        result["available_models"] = _model_ids(models)
    except LocalLLMError as exc:
        result["models_error"] = str(exc)

    try:
        response = _responses_create(
            backend,
            {
                "model": model,
                "input": "Reply with exactly ok.",
                "max_output_tokens": 16,
            },
            timeout_seconds=min(timeout_seconds, 30),
        )
        result["responses_ok"] = response.get("status") == "completed" or bool(response.get("output"))
        result["responses_preview"] = compact_text(_responses_text(response), 200)
    except LocalLLMError as exc:
        result["responses_error"] = str(exc)

    try:
        tool_response = _responses_create(
            backend,
            {
                "model": model,
                "input": "Use the selected tool with message ok.",
                "max_output_tokens": 256,
                "tool_choice": "required",
                "tools": [
                    {
                        "type": "function",
                        "name": "echo_probe",
                        "description": "Echo a short probe message.",
                        "parameters": {
                            "type": "object",
                            "properties": {"message": {"type": "string"}},
                            "required": ["message"],
                            "additionalProperties": False,
                        },
                    }
                ],
            },
            timeout_seconds=min(timeout_seconds, 30),
        )
        tool_calls = _responses_tool_calls(tool_response)
        result["responses_tool_calls_ok"] = any(call.get("name") == "echo_probe" for call in tool_calls)
        result["responses_tool_calls"] = tool_calls
    except LocalLLMError as exc:
        result["responses_tool_calls_error"] = str(exc)

    command = [
        codex_command,
        "exec",
        "--oss",
        "--local-provider",
        local_provider,
        *_codex_provider_config_args(local_provider),
        "--model",
        model,
        "--json",
        "--ephemeral",
        "--skip-git-repo-check",
        "--sandbox",
        "read-only",
        "-C",
        str(source_root),
        "Reply with exactly CODEX_LOCAL_OK and do not run shell commands.",
    ]
    try:
        codex_result = run_command(command, cwd=source_root, timeout_seconds=min(timeout_seconds, 60))
        result["codex_exec_ok"] = codex_result.exit_code == 0 and "CODEX_LOCAL_OK" in codex_result.stdout
        result["codex_exec"] = {
            "exit_code": codex_result.exit_code,
            "stdout": compact_text(codex_result.stdout, 1200),
            "stderr": compact_text(codex_result.stderr, 1200),
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        result["codex_exec_error"] = str(exc)
    return result


def _responses_create(
    backend: OpenAICompatibleLocalBackend,
    payload: dict[str, Any],
    *,
    timeout_seconds: int,
) -> dict[str, Any]:
    return backend._request_json("POST", "/v1/responses", payload, timeout_seconds=timeout_seconds)


def _responses_text(payload: dict[str, Any]) -> str:
    texts: list[str] = []
    output = payload.get("output", [])
    if not isinstance(output, list):
        return ""
    for item in output:
        if not isinstance(item, dict):
            continue
        content = item.get("content", [])
        if not isinstance(content, list):
            continue
        for part in content:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                texts.append(part["text"])
    return "\n".join(texts)


def _responses_tool_calls(payload: dict[str, Any]) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    output = payload.get("output", [])
    if not isinstance(output, list):
        return calls
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "function_call":
            continue
        calls.append(
            {
                "name": item.get("name"),
                "arguments": _parse_tool_arguments(item.get("arguments")),
                "call_id": item.get("call_id"),
            }
        )
    return calls


def _python_codex_sdk_available() -> bool:
    try:
        import importlib.util

        return importlib.util.find_spec("openai_codex") is not None
    except (ImportError, ValueError):
        return False


def _extract_tool_calls(payload: dict[str, Any]) -> list[LocalToolCall]:
    message = _assistant_message(payload)
    raw_calls = message.get("tool_calls", []) if message else []
    if not isinstance(raw_calls, list):
        return []
    calls: list[LocalToolCall] = []
    for index, raw_call in enumerate(raw_calls, 1):
        if not isinstance(raw_call, dict):
            continue
        function = raw_call.get("function", {})
        if not isinstance(function, dict):
            continue
        name = str(function.get("name", "")).strip()
        if not name:
            continue
        calls.append(
            LocalToolCall(
                call_id=str(raw_call.get("id") or f"call_{index}"),
                name=name,
                arguments=_parse_tool_arguments(function.get("arguments")),
            )
        )
    return calls


def _script_invocation(argv: list[str]) -> dict[str, str] | None:
    for part in argv:
        normalized = part.replace("\\", "/")
        marker = ".codex/skills/"
        if marker not in normalized or "/scripts/" not in normalized:
            continue
        after_marker = normalized.split(marker, 1)[1]
        skill, script_path = after_marker.split("/scripts/", 1)
        return {
            "skill": skill,
            "script": Path(script_path).name,
            "path": normalized,
        }
    return None


def _parse_tool_arguments(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if value is None:
        return {}
    if not isinstance(value, str):
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {"command": value}
    return parsed if isinstance(parsed, dict) else {}


def _assistant_message(payload: dict[str, Any]) -> dict[str, Any]:
    choices = payload.get("choices", [])
    if not isinstance(choices, list) or not choices:
        return {}
    first = choices[0]
    if not isinstance(first, dict):
        return {}
    message = first.get("message", {})
    return message if isinstance(message, dict) else {}


def _assistant_message_for_history(message: dict[str, Any]) -> dict[str, Any]:
    history = {"role": "assistant", "content": message.get("content")}
    if "tool_calls" in message:
        history["tool_calls"] = message["tool_calls"]
    return history


def _message_content(message: dict[str, Any]) -> str:
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts)
    return ""


def _local_turn_result(
    *,
    project_path: Path,
    scenario_id: str,
    action_ref: str,
    session_id: str,
    exit_code: int,
    events: list[dict[str, Any]],
    stderr: str,
    metadata: dict[str, Any],
) -> AgentTurnResult:
    stdout = "\n".join(json.dumps(event, ensure_ascii=True) for event in events)
    if stdout:
        stdout += "\n"
    return AgentTurnResult(
        command_result=CommandResult(
            command=("local-openai-action", scenario_id, action_ref),
            cwd=str(project_path),
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
        ),
        session_id=session_id,
        metadata=metadata,
    )


def _tool_event(tool_call: LocalToolCall, execution: ToolExecution) -> dict[str, Any]:
    message_parts = [f"{tool_call.name}"]
    if tool_call.name == "run_command":
        argv = execution.content.get("argv") or tool_call.arguments.get("argv") or tool_call.arguments.get("command")
        message_parts.append(f"argv={argv}")
    if execution.exit_code is not None:
        message_parts.append(f"exit={execution.exit_code}")
    if execution.content.get("stdout"):
        message_parts.append(f"stdout={compact_text(str(execution.content['stdout']), 300)}")
    if execution.content.get("stderr"):
        message_parts.append(f"stderr={compact_text(str(execution.content['stderr']), 300)}")
    if execution.content.get("error"):
        message_parts.append(f"error={compact_text(str(execution.content['error']), 300)}")
    event = {
        "type": "local_llm.tool_call",
        "tool_name": tool_call.name,
        "message": "; ".join(message_parts),
        "result": execution.content,
    }
    if invocation := execution.content.get("script_invocation"):
        event["script_invocation"] = invocation
    return event


def _local_tools(*, include_finish: bool) -> list[dict[str, Any]]:
    tools = [
        {
            "type": "function",
            "function": {
                "name": "run_command",
                "description": (
                    "Run an argv-style command in the isolated project workspace. "
                    "Use this for skill helper scripts, git, Python, tests, and GitHub CLI operations."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "argv": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Command and arguments as an array. Prefer this over command text.",
                        },
                        "command": {
                            "type": "string",
                            "description": "Fallback command text when argv is not possible.",
                        },
                        "timeout_seconds": {"type": "integer"},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read a file from the isolated project workspace by relative path.",
                "parameters": {
                    "type": "object",
                    "properties": {"relative_path": {"type": "string"}},
                    "required": ["relative_path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_files",
                "description": "List files below a relative path in the isolated project workspace.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "relative_path": {"type": "string"},
                        "max_files": {"type": "integer"},
                    },
                },
            },
        },
    ]
    if include_finish:
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": "finish",
                    "description": "Finish the current user action with a concise summary.",
                    "parameters": {
                        "type": "object",
                        "properties": {"summary": {"type": "string"}},
                        "required": ["summary"],
                    },
                },
            }
        )
    return tools


def _coerce_argv(arguments: dict[str, Any]) -> list[str]:
    argv = arguments.get("argv")
    if isinstance(argv, list):
        values = [str(part) for part in argv if str(part)]
        if values:
            return values
    command = arguments.get("command")
    if isinstance(command, str) and command.strip():
        return [part.strip('"') for part in shlex.split(command, posix=True)]
    raise ValueError("run_command requires argv or command")


def _validate_agent_argv(argv: list[str]) -> None:
    if not argv:
        raise ValueError("run_command argv cannot be empty")
    executable = Path(argv[0]).name.lower()
    if executable in {"codex", "codex.cmd", "codex.exe"}:
        raise ValueError("Codex CLI commands are not allowed through the local-openai backend")


def _safe_project_path(project_path: Path, relative_path: str) -> Path:
    requested = Path(relative_path)
    if requested.is_absolute() or ".." in requested.parts:
        raise ValueError(f"unsafe relative path: {relative_path}")
    resolved_project = project_path.resolve()
    resolved_path = (project_path / requested).resolve()
    if resolved_path != resolved_project and resolved_project not in resolved_path.parents:
        raise ValueError(f"path escapes project workspace: {relative_path}")
    return resolved_path


def _resolved_skill_context(project_path: Path, prompt: str) -> tuple[str, list[dict[str, str]]]:
    action_text = _user_action_text(prompt)
    contexts: list[str] = []
    resolved: list[dict[str, str]] = []
    for alias, skill_name in SKILL_ALIASES.items():
        if alias not in action_text:
            continue
        path = project_path / ".codex" / "skills" / skill_name / "SKILL.md"
        if not path.exists():
            resolved.append({"alias": alias, "skill": skill_name, "path": str(path), "status": "missing"})
            continue
        skill_text = path.read_text(encoding="utf-8", errors="replace")
        contexts.append(f"{alias} ({skill_name}) from {path.relative_to(project_path)}:\n{compact_text(skill_text, 6000)}")
        resolved.append({"alias": alias, "skill": skill_name, "path": str(path), "status": "loaded"})
    return "\n\n".join(contexts), resolved


def _local_system_prompt(project_path: Path) -> str:
    return (
        "You are the Agent Under Test for the Simple Flow harness. "
        f"Work only inside this project workspace: {project_path}. "
        "Use tool calls for file inspection and commands. "
        "Do not call the Codex CLI; this backend replaces Codex execution with local OpenAI-compatible tool calls. "
        "When a USER_ACTION names a skill alias, follow the supplied SKILL.md context and invoke any required "
        "skill-owned helper scripts through run_command. "
        "Use argv arrays for run_command whenever possible. "
        "Stop when the skill stage says STOP and keep the response concise."
    )


def _prompt_requires_command_tool(prompt: str) -> bool:
    lowered = _user_action_text(prompt).lower()
    return " run:" in lowered or "by running:" in lowered or ".codex/skills/" in lowered


def _user_action_text(prompt: str) -> str:
    for line in prompt.splitlines():
        stripped = line.strip()
        if stripped.startswith("USER_ACTION TO EXECUTE NOW:"):
            return stripped.split(":", 1)[1].strip()
    return prompt


def _command_protocol_lines(content: str) -> list[str]:
    commands: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("COMMAND:"):
            command = stripped.split(":", 1)[1].strip()
            if command:
                commands.append(command)
    return commands


def _extract_thread_id(stdout: str) -> str:
    for line in stdout.splitlines():
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "thread.started" and event.get("thread_id"):
            return str(event["thread_id"])
    return ""


def _timeout_result(
    cwd: Path,
    scenario_id: str,
    action_ref: str,
    exc: subprocess.TimeoutExpired,
    *,
    backend_label: str,
) -> CommandResult:
    stdout = _timeout_stream(exc.stdout)
    stderr = _timeout_stream(exc.stderr)
    timeout = exc.timeout if exc.timeout is not None else "configured"
    timeout_message = f"{backend_label} action {action_ref} timed out after {timeout} seconds; raw command omitted."
    if stderr:
        stderr = timeout_message + "\n" + stderr
    else:
        stderr = timeout_message
    return CommandResult(
        command=(f"{backend_label.lower().replace(' ', '-')}-action", scenario_id, action_ref),
        cwd=str(cwd),
        exit_code=124,
        stdout=stdout,
        stderr=stderr,
    )


def _timeout_stream(value: bytes | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _model_ids(models: dict[str, Any]) -> list[str]:
    data = models.get("data", [])
    if not isinstance(data, list):
        return []
    ids: list[str] = []
    for item in data:
        if isinstance(item, dict) and item.get("id"):
            ids.append(str(item["id"]))
    return ids
