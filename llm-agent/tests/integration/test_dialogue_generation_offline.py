import asyncio
import json
from dataclasses import dataclass

from dialogue_generation_agent import (
    CharacterContext,
    CharacterReference,
    CharacterSceneState,
    CharacterStateResult,
    CurrentSceneContext,
    Delivery,
    DialogueGeneration,
    DialogueGenerationAgent,
    DialogueGenerationRequest,
    DialogueTurn,
    GenerationMetadata,
    InformationFlow,
    SceneObjectiveResult,
    SceneResult,
    SystemContext,
)


@dataclass
class OfflineResult:
    output: DialogueGeneration


class OfflineRunner:
    def __init__(self) -> None:
        self.calls = 0

    async def run(self, user_prompt: str, *, instructions: str) -> OfflineResult:
        self.calls += 1
        envelope = json.loads(user_prompt)
        request = envelope["request"]
        character = request["system_context"]["characters"][0]
        reference = CharacterReference(
            character_id=character["character_id"],
            name=character["name"],
        )
        return OfflineResult(
            DialogueGeneration(
                scene=SceneResult(
                    scene_id=request["current_scene"]["scene_id"],
                    generation_id=envelope["generation_id"],
                    objective=request["objective"],
                    status="completed",
                    ending_reason="독백을 마쳤다.",
                ),
                dialogue=(
                    DialogueTurn(
                        turn_id="turn-1",
                        speaker=reference,
                        addressed_to=reference,
                        line="이번에는 피하지 않을 거야.",
                        delivery=Delivery(tone="단호함", emotion="결심", intensity=4),
                        action="창밖을 바라본다.",
                        subtext="두려움을 이겨 내려 한다.",
                    ),
                ),
                metadata=GenerationMetadata(
                    summary="주인공이 결심한다.",
                    scene_objective_result=SceneObjectiveResult(
                        status="achieved",
                        explanation="결심을 말로 확인했다.",
                    ),
                    character_states=(
                        CharacterStateResult(
                            character_id=character["character_id"],
                            name=character["name"],
                            emotion="결심",
                            desire_progress="행동할 준비를 마침",
                            hidden_intent_status="아직 밝히지 않음",
                        ),
                    ),
                    information_flow=InformationFlow(
                        revealed=(),
                        withheld=(),
                        forbidden_information_violations=(),
                    ),
                    unresolved_tensions=(),
                    next_scene_hooks=("주인공이 문을 연다.",),
                ),
            )
        )


def test_public_offline_flow_returns_fixed_json_contract() -> None:
    runner = OfflineRunner()
    agent = DialogueGenerationAgent(
        "offline",
        runner=runner,
        generation_id_factory=lambda: "generation-offline-1",
    )
    request = DialogueGenerationRequest(
        system_context=SystemContext(
            worldbuilding="겨울의 바닷가 마을",
            characters=(
                CharacterContext(
                    character_id="character-1",
                    name="하린",
                    gender="female",
                    age=27,
                    prose_style="담백함",
                    dialogue_style="짧은 문장",
                    relevant_previous_memories=(),
                ),
            ),
        ),
        current_scene=CurrentSceneContext(scene_id="scene-1", context="새벽의 빈 카페"),
        objective="하린이 결심을 입 밖으로 낸다.",
        character_states=(
            CharacterSceneState(
                character_id="character-1",
                current_desire="마을을 떠난다.",
                hidden_intent="작별을 미룬다.",
                known_information=(),
                unknown_information=(),
                forbidden_information=(),
            ),
        ),
    )

    result = asyncio.run(agent.generate_dialogue(request))
    payload = json.loads(result.model_dump_json())

    assert runner.calls == 1
    assert set(payload) == {"scene", "dialogue", "metadata"}
    assert set(payload["scene"]) == {
        "scene_id",
        "generation_id",
        "objective",
        "status",
        "ending_reason",
    }
    assert set(payload["dialogue"][0]) == {
        "turn_id",
        "speaker",
        "addressed_to",
        "line",
        "delivery",
        "action",
        "subtext",
    }
    assert set(payload["metadata"]) == {
        "summary",
        "scene_objective_result",
        "character_states",
        "information_flow",
        "unresolved_tensions",
        "next_scene_hooks",
    }
