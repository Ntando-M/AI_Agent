from typing import Literal

from pydantic import BaseModel, Field


class AIResponse(BaseModel):
    """
    Defines the structure expected from the LLM.
    """

    answer: str = Field(
        description="The complete answer to the user's question"
    )

    topic: str = Field(
        description="The main topic of the user's question"
    )

    difficulty: Literal[
        "beginner",
        "intermediate",
        "advanced"
    ] = Field(
        description="The estimated difficulty of the user's question"
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "The model's confidence in the answer "
            "from 0.0 to 1.0"
        )
    )