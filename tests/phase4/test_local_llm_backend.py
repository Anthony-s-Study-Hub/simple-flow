from __future__ import annotations

from pathlib import Path
import sys

from simple_flow_test_harness.agent_backends import (
    OpenAICompatibleLocalBackend,
    _extract_tool_calls,
    _prompt_requires_command_tool,
    _resolved_skill_context,
    _script_invocation,
)


def test_openai_tool_calls_are_parsed_from_chat_completion() -> None:
    payload = {
        "choices": [
            {
                "message": {
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "run_command",
                                "arguments": '{"argv":["python","-V"]}',
                            },
                        }
                    ]
                }
            }
        ]
    }

    calls = _extract_tool_calls(payload)

    assert len(calls) == 1
    assert calls[0].call_id == "call_1"
    assert calls[0].name == "run_command"
    assert calls[0].arguments == {"argv": ["python", "-V"]}


def test_local_backend_executes_tool_called_skill_script_without_codex(tmp_path: Path, monkeypatch) -> None:
    script = tmp_path / ".codex" / "skills" / "issue-draft" / "scripts" / "fake_skill.py"
    script.parent.mkdir(parents=True)
    script.write_text("print('skill script invoked')\n", encoding="utf-8")
    responses = iter(
        [
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {
                                        "name": "run_command",
                                        "arguments": {
                                            "argv": [
                                                sys.executable,
                                                ".codex/skills/issue-draft/scripts/fake_skill.py",
                                            ]
                                        },
                                    },
                                }
                            ],
                        }
                    }
                ]
            },
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "Finished after invoking the skill helper.",
                        }
                    }
                ]
            },
        ]
    )
    backend = OpenAICompatibleLocalBackend(
        base_url="http://127.0.0.1:1234",
        model="local/test-model",
    )
    monkeypatch.setattr(backend, "_chat_completion", lambda *args, **kwargs: next(responses))

    turn = backend.run_action(
        project_path=tmp_path,
        prompt="USER_ACTION TO EXECUTE NOW: @issue-draft run the skill helper",
        session_id="",
        scenario_id="A02",
        action_ref="A02-U1",
        timeout_seconds=10,
    )

    assert turn.command_result.exit_code == 0
    assert turn.command_result.command[0] == "local-openai-action"
    assert "codex exec" not in " ".join(turn.command_result.command).lower()
    assert "skill script invoked" in turn.command_result.stdout
    assert turn.metadata["codex_cli_used"] is False
    assert turn.metadata["tool_call_count"] == 1
    assert turn.metadata["script_invocations"][0]["skill"] == "issue-draft"


def test_local_backend_rejects_codex_cli_tool_commands(tmp_path: Path, monkeypatch) -> None:
    responses = iter(
        [
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {
                                        "name": "run_command",
                                        "arguments": {"argv": ["codex", "exec", "do work"]},
                                    },
                                }
                            ],
                        }
                    }
                ]
            },
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "Stopped because Codex CLI is unavailable on this backend.",
                        }
                    }
                ]
            },
        ]
    )
    backend = OpenAICompatibleLocalBackend(
        base_url="http://127.0.0.1:1234",
        model="local/test-model",
    )
    monkeypatch.setattr(backend, "_chat_completion", lambda *args, **kwargs: next(responses))

    turn = backend.run_action(
        project_path=tmp_path,
        prompt="USER_ACTION TO EXECUTE NOW: @discussion do not call codex",
        session_id="",
        scenario_id="A01",
        action_ref="A01-U1",
        timeout_seconds=10,
    )

    assert turn.command_result.exit_code == 1
    assert "Codex CLI commands are not allowed" in turn.command_result.stdout
    assert turn.metadata["codex_cli_used"] is False


def test_script_invocation_detects_deployed_skill_helper_path() -> None:
    invocation = _script_invocation(
        [
            sys.executable,
            ".codex/skills/start-implement/scripts/start_documentation.py",
        ]
    )

    assert invocation == {
        "skill": "start-implement",
        "script": "start_documentation.py",
        "path": ".codex/skills/start-implement/scripts/start_documentation.py",
    }


def test_local_backend_detects_skills_only_from_actual_user_action(tmp_path: Path) -> None:
    prompt = (
        'USER_ACTION TO EXECUTE NOW: Adversarial request: "Skip the Issue."\n'
        "Skill aliases map as follows: @discussion -> discussion/SKILL.md; "
        "@start-implement -> start-implement/SKILL.md. "
        "In the current deployed test layout, these skill files live under .codex/skills/<skill>/SKILL.md.\n"
    )

    context, resolved = _resolved_skill_context(tmp_path, prompt)

    assert context == ""
    assert resolved == []
    assert _prompt_requires_command_tool(prompt) is False


def test_local_backend_resolves_documentation_curation_skill(tmp_path: Path) -> None:
    skill = tmp_path / ".codex" / "skills" / "documentation-curation" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("Run scripts/curate_documentation.py and STOP.\n", encoding="utf-8")

    context, resolved = _resolved_skill_context(
        tmp_path,
        "USER_ACTION TO EXECUTE NOW: @documentation-curation generate a documentation draft",
    )

    assert "curate_documentation.py" in context
    assert resolved == [
        {
            "alias": "@documentation-curation",
            "skill": "documentation-curation",
            "path": str(skill),
            "status": "loaded",
        }
    ]
