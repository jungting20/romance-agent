import asyncio
import json
from collections.abc import Callable
from pathlib import Path
from typing import Protocol, cast
from uuid import uuid4

from pydantic import ValidationError
from pydantic_ai import Agent
from pydantic_ai.exceptions import AgentRunError
from pydantic_ai.models import Model

from dialogue_generation_agent.models import (
    DialogueGeneration,
    DialogueGenerationRequest,
    ForbiddenInformation,
)
from llm_agent_audit import (
    AgentAuditSink,
    AgentAuditWriteError,
    AuditedAgentRunner,
    PromptIdentity,
)

_AGENT_NAME = "dialogue-generation"
_PROMPT_ID = "dialogue-generation.system"
_PROMPT_VERSION = 1


class DialogueGenerationError(RuntimeError):
    pass


class AgentResult(Protocol):
    output: DialogueGeneration


class AgentRunner(Protocol):
    async def run(self, user_prompt: str, *, instructions: str) -> AgentResult: ...


def packaged_prompt_path() -> Path:
    return Path(__file__).parent / "prompts" / "dialogue-generation" / "system.md"


def _new_generation_id() -> str:
    return f"generation-{uuid4()}"


class DialogueGenerationAgent:
    def __init__(
        self,
        model: Model | str,
        *,
        prompt_path: Path | None = None,
        runner: AgentRunner | None = None,
        generation_id_factory: Callable[[], str] | None = None,
        audit_sink: AgentAuditSink | None = None,
        audit_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self.prompt_path = prompt_path or packaged_prompt_path()
        raw_runner = runner or cast(
            AgentRunner,
            Agent(
                model,
                output_type=DialogueGeneration,
                retries=0,
                defer_model_check=True,
            ),
        )
        self._runner = AuditedAgentRunner(
            raw_runner,
            agent_name=_AGENT_NAME,
            model=model,
            sink=audit_sink,
            id_factory=audit_id_factory,
        )
        self._generation_id_factory = generation_id_factory or _new_generation_id

    async def generate_dialogue(
        self,
        request: DialogueGenerationRequest,
    ) -> DialogueGeneration:
        # 대화 생성에 적용할 시스템 지침을 불러온다.
        instructions = self._load_instructions()

        # 이번 모델 호출을 식별하는 생성 시도 ID를 할당한다.
        generation_id = self._create_generation_id()

        # 이번 대화 생성 호출의 감사 실행 ID를 할당한다.
        audit_run_id = self._runner.new_run_id()

        # 전체 장면 문맥을 한 번 전달하고 검증된 구조화된 대화 결과를 생성한다.
        output = await self._generate(request, generation_id, instructions, audit_run_id)

        return output

    def _load_instructions(self) -> str:
        try:
            return self.prompt_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            raise DialogueGenerationError(
                "unable to load dialogue generation prompt"
            ) from None

    def _create_generation_id(self) -> str:
        try:
            generation_id = self._generation_id_factory()
        except Exception:
            raise DialogueGenerationError(
                "unable to create dialogue generation ID"
            ) from None
        if not generation_id or not generation_id.strip():
            raise DialogueGenerationError("unable to create dialogue generation ID")
        return generation_id

    async def _generate(
        self,
        request: DialogueGenerationRequest,
        generation_id: str,
        instructions: str,
        audit_run_id: str,
    ) -> DialogueGeneration:
        try:
            result = await self._runner.run(
                _render_user_prompt(request, generation_id),
                instructions=instructions,
                run_id=audit_run_id,
                prompt=PromptIdentity.from_text(_PROMPT_ID, _PROMPT_VERSION, instructions),
                validate=lambda output: _validate_output(output, request, generation_id),
            )
            return result.output
        except asyncio.CancelledError:
            raise
        except (AgentAuditWriteError, AgentRunError, ValidationError, ValueError):
            raise DialogueGenerationError("dialogue generation failed") from None


def _render_user_prompt(request: DialogueGenerationRequest, generation_id: str) -> str:
    envelope = {
        "generation_id": generation_id,
        "request": request.model_dump(mode="json"),
    }
    return json.dumps(envelope, ensure_ascii=False, separators=(",", ":"))


def _validate_output(
    output: DialogueGeneration,
    request: DialogueGenerationRequest,
    generation_id: str,
) -> None:
    if output.scene.scene_id != request.current_scene.scene_id:
        raise ValueError("scene ID does not match the request")
    if output.scene.generation_id != generation_id:
        raise ValueError("generation ID does not match the attempt")
    if output.scene.objective != request.objective:
        raise ValueError("scene objective does not match the request")

    characters = {
        character.character_id: character.name
        for character in request.system_context.characters
    }
    turn_ids = [turn.turn_id for turn in output.dialogue]
    if len(turn_ids) != len(set(turn_ids)):
        raise ValueError("turn IDs must be unique")
    turns = {turn.turn_id: turn for turn in output.dialogue}
    for turn in output.dialogue:
        _validate_character_reference(
            turn.speaker.character_id,
            turn.speaker.name,
            characters,
        )
        _validate_character_reference(
            turn.addressed_to.character_id,
            turn.addressed_to.name,
            characters,
        )

    state_ids = [state.character_id for state in output.metadata.character_states]
    if len(state_ids) != len(set(state_ids)) or set(state_ids) != set(characters):
        raise ValueError("metadata character states must match request characters")
    for state in output.metadata.character_states:
        _validate_character_reference(state.character_id, state.name, characters)

    information, forbidden = _information_catalog(request)
    known_by_character = {
        state.character_id: {item.information_id for item in state.known_information}
        | {item.information_id for item in state.forbidden_information}
        for state in request.character_states
    }
    revealed = output.metadata.information_flow.revealed
    withheld = output.metadata.information_flow.withheld
    violations = output.metadata.information_flow.forbidden_information_violations
    if violations:
        raise ValueError("forbidden information violation was reported")
    for item in revealed:
        if item.information_id not in information:
            raise ValueError("revealed information is unknown")
        if item.information_id in forbidden:
            raise ValueError("forbidden information was marked as revealed")
        if item.turn_id not in turns:
            raise ValueError("revealed information references an unknown turn")
        if item.character_id not in characters:
            raise ValueError("revealed information references an unknown character")
        if turns[item.turn_id].speaker.character_id != item.character_id:
            raise ValueError(
                "revealed information character does not match the turn speaker"
            )
        if item.information_id not in known_by_character[item.character_id]:
            raise ValueError("a character revealed information they do not know")
    if any(item.information_id not in information for item in withheld):
        raise ValueError("withheld information is unknown")
    withheld_ids = {item.information_id for item in withheld}
    if not set(forbidden) <= withheld_ids:
        raise ValueError("every forbidden information item must be marked as withheld")

    for turn in output.dialogue:
        normalized_line = turn.line.casefold()
        for item in forbidden.values():
            if item.content.casefold() in normalized_line:
                raise ValueError("forbidden information appears in dialogue")


def _validate_character_reference(
    character_id: str,
    name: str,
    characters: dict[str, str],
) -> None:
    if characters.get(character_id) != name:
        raise ValueError("character reference does not match the request")


def _information_catalog(
    request: DialogueGenerationRequest,
) -> tuple[dict[str, str], dict[str, ForbiddenInformation]]:
    information: dict[str, str] = {}
    forbidden: dict[str, ForbiddenInformation] = {}
    for state in request.character_states:
        for item in (*state.known_information, *state.unknown_information):
            information[item.information_id] = item.content
        for item in state.forbidden_information:
            information[item.information_id] = item.content
            forbidden[item.information_id] = item
    return information, forbidden
