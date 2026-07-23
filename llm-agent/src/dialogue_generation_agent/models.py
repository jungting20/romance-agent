from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

NonBlankString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Gender = Literal["male", "female", "nonbinary", "unknown"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class CharacterContext(StrictModel):
    character_id: NonBlankString
    name: NonBlankString
    gender: Gender
    age: int | None = Field(ge=0)
    prose_style: NonBlankString
    dialogue_style: NonBlankString
    relevant_previous_memories: tuple[NonBlankString, ...]


class SystemContext(StrictModel):
    worldbuilding: NonBlankString
    characters: tuple[CharacterContext, ...] = Field(min_length=1)


class CurrentSceneContext(StrictModel):
    scene_id: NonBlankString
    context: NonBlankString


class Information(StrictModel):
    information_id: NonBlankString
    content: NonBlankString


class ForbiddenInformation(Information):
    revealable_when: NonBlankString


class CharacterSceneState(StrictModel):
    character_id: NonBlankString
    current_desire: NonBlankString
    hidden_intent: NonBlankString
    known_information: tuple[Information, ...]
    unknown_information: tuple[Information, ...]
    forbidden_information: tuple[ForbiddenInformation, ...]


class DialogueGenerationRequest(StrictModel):
    system_context: SystemContext
    current_scene: CurrentSceneContext
    objective: NonBlankString
    character_states: tuple[CharacterSceneState, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_context_references(self) -> "DialogueGenerationRequest":
        character_ids = [item.character_id for item in self.system_context.characters]
        if len(character_ids) != len(set(character_ids)):
            raise ValueError("character IDs must be unique")

        state_ids = [item.character_id for item in self.character_states]
        if len(state_ids) != len(set(state_ids)):
            raise ValueError("character state IDs must be unique")
        if set(state_ids) != set(character_ids):
            raise ValueError("character states must match system context characters")

        information_content: dict[str, str] = {}
        for state in self.character_states:
            known_ids = {item.information_id for item in state.known_information}
            unknown_ids = {item.information_id for item in state.unknown_information}
            if known_ids & unknown_ids:
                raise ValueError("a character cannot both know and not know the same information")
            for item in (
                *state.known_information,
                *state.unknown_information,
                *state.forbidden_information,
            ):
                previous = information_content.setdefault(item.information_id, item.content)
                if previous != item.content:
                    raise ValueError("an information ID must have stable content")
        return self


class SceneResult(StrictModel):
    scene_id: NonBlankString
    generation_id: NonBlankString
    objective: NonBlankString
    status: Literal["completed", "ended_early", "blocked"]
    ending_reason: NonBlankString


class CharacterReference(StrictModel):
    character_id: NonBlankString
    name: NonBlankString


class Delivery(StrictModel):
    tone: NonBlankString
    emotion: NonBlankString
    intensity: int = Field(ge=1, le=5)


class DialogueTurn(StrictModel):
    turn_id: NonBlankString
    speaker: CharacterReference
    addressed_to: CharacterReference
    line: NonBlankString
    delivery: Delivery
    action: str
    subtext: str


class SceneObjectiveResult(StrictModel):
    status: Literal["achieved", "partially_achieved", "not_achieved"]
    explanation: NonBlankString


class CharacterStateResult(StrictModel):
    character_id: NonBlankString
    name: NonBlankString
    emotion: NonBlankString
    desire_progress: NonBlankString
    hidden_intent_status: NonBlankString


class RevealedInformation(StrictModel):
    information_id: NonBlankString
    turn_id: NonBlankString
    character_id: NonBlankString
    description: NonBlankString


class WithheldInformation(StrictModel):
    information_id: NonBlankString
    reason: NonBlankString


class ForbiddenInformationViolation(StrictModel):
    information_id: NonBlankString
    turn_id: NonBlankString
    evidence: NonBlankString
    reason: NonBlankString


class InformationFlow(StrictModel):
    revealed: tuple[RevealedInformation, ...]
    withheld: tuple[WithheldInformation, ...]
    forbidden_information_violations: tuple[ForbiddenInformationViolation, ...]


class GenerationMetadata(StrictModel):
    summary: NonBlankString
    scene_objective_result: SceneObjectiveResult
    character_states: tuple[CharacterStateResult, ...]
    information_flow: InformationFlow
    unresolved_tensions: tuple[NonBlankString, ...]
    next_scene_hooks: tuple[NonBlankString, ...]


class DialogueGeneration(StrictModel):
    scene: SceneResult
    dialogue: tuple[DialogueTurn, ...] = Field(min_length=1)
    metadata: GenerationMetadata
