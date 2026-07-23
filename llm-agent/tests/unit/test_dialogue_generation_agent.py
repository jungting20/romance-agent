import asyncio
import json
from dataclasses import dataclass
from pathlib import Path

import pytest
from pydantic import ValidationError
from pydantic_ai.exceptions import AgentRunError

from dialogue_generation_agent import (
    CharacterContext,
    CharacterReference,
    CharacterSceneState,
    CharacterStateResult,
    CurrentSceneContext,
    Delivery,
    DialogueGeneration,
    DialogueGenerationAgent,
    DialogueGenerationError,
    DialogueGenerationRequest,
    DialogueTurn,
    ForbiddenInformation,
    ForbiddenInformationViolation,
    GenerationMetadata,
    Information,
    InformationFlow,
    RevealedInformation,
    SceneObjectiveResult,
    SceneResult,
    SystemContext,
    WithheldInformation,
    packaged_prompt_path,
)


def _request() -> DialogueGenerationRequest:
    return DialogueGenerationRequest(
        system_context=SystemContext(
            worldbuilding="기억을 사고파는 근미래 서울",
            characters=(
                CharacterContext(
                    character_id="character-seoyun",
                    name="서윤",
                    gender="female",
                    age=29,
                    prose_style="절제된 묘사",
                    dialogue_style="짧고 냉정한 문장",
                    relevant_previous_memories=("지후와 옥상에서 다퉜다.",),
                ),
                CharacterContext(
                    character_id="character-jihoo",
                    name="지후",
                    gender="male",
                    age=31,
                    prose_style="감각적인 묘사",
                    dialogue_style="농담으로 감정을 숨긴다",
                    relevant_previous_memories=("서윤의 우산을 돌려주지 못했다.",),
                ),
            ),
        ),
        current_scene=CurrentSceneContext(
            scene_id="scene-rooftop-02",
            context="비가 그친 옥상에서 두 사람이 다시 마주쳤다.",
        ),
        objective="서로의 오해를 일부 풀되 긴장을 남긴다.",
        character_states=(
            CharacterSceneState(
                character_id="character-seoyun",
                current_desire="지후의 진심을 확인한다.",
                hidden_intent="먼저 사과하고 싶다.",
                known_information=(
                    Information(
                        information_id="information-umbrella",
                        content="지후가 우산을 보관하고 있다.",
                    ),
                ),
                unknown_information=(
                    Information(
                        information_id="information-transfer",
                        content="지후가 기억 이전을 거부했다.",
                    ),
                ),
                forbidden_information=(
                    ForbiddenInformation(
                        information_id="information-diagnosis",
                        content="서윤의 기억 소실 진단",
                        revealable_when="서윤이 먼저 병원 기록을 공개한 뒤",
                    ),
                ),
            ),
            CharacterSceneState(
                character_id="character-jihoo",
                current_desire="서윤을 안심시킨다.",
                hidden_intent="진단 사실을 알고 있음을 숨긴다.",
                known_information=(
                    Information(
                        information_id="information-transfer",
                        content="지후가 기억 이전을 거부했다.",
                    ),
                    Information(
                        information_id="information-umbrella",
                        content="지후가 우산을 보관하고 있다.",
                    ),
                ),
                unknown_information=(),
                forbidden_information=(
                    ForbiddenInformation(
                        information_id="information-diagnosis",
                        content="서윤의 기억 소실 진단",
                        revealable_when="서윤이 먼저 병원 기록을 공개한 뒤",
                    ),
                ),
            ),
        ),
    )


def _output(
    *,
    line: str = "우산, 아직 내가 가지고 있어.",
    withheld: tuple[WithheldInformation, ...] | None = None,
    violations: tuple[ForbiddenInformationViolation, ...] = (),
) -> DialogueGeneration:
    return DialogueGeneration(
        scene=SceneResult(
            scene_id="scene-rooftop-02",
            generation_id="generation-attempt-01",
            objective="서로의 오해를 일부 풀되 긴장을 남긴다.",
            status="completed",
            ending_reason="서윤이 우산을 받으며 대화를 끝냈다.",
        ),
        dialogue=(
            DialogueTurn(
                turn_id="turn-01",
                speaker=CharacterReference(character_id="character-jihoo", name="지후"),
                addressed_to=CharacterReference(character_id="character-seoyun", name="서윤"),
                line=line,
                delivery=Delivery(tone="조심스러운 농담", emotion="미안함", intensity=2),
                action="접어 둔 우산을 내민다.",
                subtext="직접 사과할 용기가 부족하다.",
            ),
        ),
        metadata=GenerationMetadata(
            summary="지후가 우산을 돌려주며 두 사람의 오해가 일부 풀린다.",
            scene_objective_result=SceneObjectiveResult(
                status="partially_achieved",
                explanation="작은 오해는 풀렸지만 진단과 감정은 숨겨졌다.",
            ),
            character_states=(
                CharacterStateResult(
                    character_id="character-seoyun",
                    name="서윤",
                    emotion="경계가 누그러짐",
                    desire_progress="지후의 태도를 일부 확인함",
                    hidden_intent_status="사과하지 못함",
                ),
                CharacterStateResult(
                    character_id="character-jihoo",
                    name="지후",
                    emotion="안도와 죄책감",
                    desire_progress="서윤을 일부 안심시킴",
                    hidden_intent_status="진단 사실을 계속 숨김",
                ),
            ),
            information_flow=InformationFlow(
                revealed=(
                    RevealedInformation(
                        information_id="information-umbrella",
                        turn_id="turn-01",
                        character_id="character-jihoo",
                        description="지후가 우산을 보관하고 있음을 밝혔다.",
                    ),
                ),
                withheld=withheld
                if withheld is not None
                else (
                    WithheldInformation(
                        information_id="information-diagnosis",
                        reason="현재 공개 금지 정보다.",
                    ),
                    WithheldInformation(
                        information_id="information-transfer",
                        reason="지후가 아직 말하지 않았다.",
                    ),
                ),
                forbidden_information_violations=violations,
            ),
            unresolved_tensions=("지후가 진단 사실을 아는 이유",),
            next_scene_hooks=("서윤이 병원 기록을 발견한다.",),
        ),
    )


@dataclass
class FakeResult:
    output: DialogueGeneration


class RecordingRunner:
    def __init__(self, output: DialogueGeneration) -> None:
        self.output = output
        self.calls: list[tuple[str, str]] = []

    async def run(self, user_prompt: str, *, instructions: str) -> FakeResult:
        self.calls.append((user_prompt, instructions))
        return FakeResult(self.output)


class FailingRunner:
    async def run(self, user_prompt: str, *, instructions: str) -> FakeResult:
        raise AgentRunError("private provider detail")


class CancelledRunner:
    async def run(self, user_prompt: str, *, instructions: str) -> FakeResult:
        raise asyncio.CancelledError


def _agent(
    runner: RecordingRunner | FailingRunner | CancelledRunner,
    *,
    prompt_path: Path | None = None,
    generation_id: str = "generation-attempt-01",
) -> DialogueGenerationAgent:
    return DialogueGenerationAgent(
        "test",
        runner=runner,
        prompt_path=prompt_path,
        generation_id_factory=lambda: generation_id,
    )


def test_generate_dialogue_sends_complete_json_context_and_returns_structured_output() -> None:
    runner = RecordingRunner(_output())

    result = asyncio.run(_agent(runner).generate_dialogue(_request()))

    assert result.scene.generation_id == "generation-attempt-01"
    assert result.dialogue[0].turn_id == "turn-01"
    assert len(runner.calls) == 1
    prompt = json.loads(runner.calls[0][0])
    assert prompt == {
        "generation_id": "generation-attempt-01",
        "request": _request().model_dump(mode="json"),
    }
    assert runner.calls[0][1] == packaged_prompt_path().read_text(encoding="utf-8")
    assert result.model_dump_json()


@pytest.mark.parametrize(
    ("output", "reason"),
    [
        (
            _output(line="나는 서윤의 기억 소실 진단을 알고 있어."),
            "exact forbidden content",
        ),
        (
            _output(
                violations=(
                    ForbiddenInformationViolation(
                        information_id="information-diagnosis",
                        turn_id="turn-01",
                        evidence="진단",
                        reason="금지 정보가 암시됨",
                    ),
                )
            ),
            "reported violation",
        ),
        (
            _output(
                withheld=(
                    WithheldInformation(
                        information_id="information-transfer",
                        reason="아직 말하지 않았다.",
                    ),
                )
            ),
            "missing forbidden withheld record",
        ),
    ],
)
def test_generate_dialogue_rejects_forbidden_information_failures(
    output: DialogueGeneration,
    reason: str,
) -> None:
    with pytest.raises(DialogueGenerationError, match="dialogue generation failed"):
        asyncio.run(_agent(RecordingRunner(output)).generate_dialogue(_request()))


def test_generate_dialogue_rejects_mismatched_character_reference() -> None:
    output = _output()
    invalid_turn = output.dialogue[0].model_copy(
        update={"speaker": CharacterReference(character_id="character-jihoo", name="서윤")}
    )
    output = output.model_copy(update={"dialogue": (invalid_turn,)})

    with pytest.raises(DialogueGenerationError, match="dialogue generation failed"):
        asyncio.run(_agent(RecordingRunner(output)).generate_dialogue(_request()))


def test_generate_dialogue_rejects_information_revealed_by_character_who_does_not_know_it() -> None:
    output = _output()
    invalid_flow = output.metadata.information_flow.model_copy(
        update={
            "revealed": (
                RevealedInformation(
                    information_id="information-transfer",
                    turn_id="turn-01",
                    character_id="character-jihoo",
                    description="지후가 기억 이전 거부를 밝혔다.",
                ),
            )
        }
    )
    output = output.model_copy(
        update={"metadata": output.metadata.model_copy(update={"information_flow": invalid_flow})}
    )
    request = _request()
    jihoo_state = request.character_states[1].model_copy(update={"known_information": ()})
    request = request.model_copy(
        update={"character_states": (request.character_states[0], jihoo_state)}
    )

    with pytest.raises(DialogueGenerationError, match="dialogue generation failed"):
        asyncio.run(_agent(RecordingRunner(output)).generate_dialogue(request))


def test_generate_dialogue_sanitizes_provider_failure() -> None:
    with pytest.raises(DialogueGenerationError, match="dialogue generation failed") as captured:
        asyncio.run(_agent(FailingRunner()).generate_dialogue(_request()))

    assert captured.value.__cause__ is None
    assert "provider" not in str(captured.value)


def test_generate_dialogue_propagates_cancellation() -> None:
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(_agent(CancelledRunner()).generate_dialogue(_request()))


def test_generate_dialogue_sanitizes_prompt_loading_failure(tmp_path: Path) -> None:
    missing_prompt = tmp_path / "missing.md"

    with pytest.raises(
        DialogueGenerationError,
        match="unable to load dialogue generation prompt",
    ):
        asyncio.run(
            _agent(RecordingRunner(_output()), prompt_path=missing_prompt).generate_dialogue(
                _request()
            )
        )


def test_request_rejects_unstable_information_content() -> None:
    request = _request()
    second_state = request.character_states[1]
    conflicting = second_state.model_copy(
        update={
            "known_information": (
                Information(
                    information_id="information-umbrella",
                    content="우산은 이미 버려졌다.",
                ),
            ),
            "unknown_information": (),
        }
    )

    with pytest.raises(ValidationError, match="stable content"):
        DialogueGenerationRequest(
            system_context=request.system_context,
            current_scene=request.current_scene,
            objective=request.objective,
            character_states=(request.character_states[0], conflicting),
        )


def test_public_models_are_strict_and_immutable() -> None:
    request = _request()

    with pytest.raises(ValidationError):
        DialogueGenerationRequest.model_validate(
            {**request.model_dump(mode="python"), "unexpected": True}
        )
    with pytest.raises(ValidationError):
        SystemContext.model_validate(
            {
                "worldbuilding": "세계관",
                "characters": [request.system_context.characters[0]],
            }
        )
    with pytest.raises(ValidationError):
        request.objective = "변경"
