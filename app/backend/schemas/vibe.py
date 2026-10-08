"""Request and response models for the VibeCoding app generator."""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class VibeTurn(BaseModel):
    """One conversation turn kept as short-term context for the generator."""

    role: Literal["user", "assistant"] = Field(..., description="Message role.")
    content: str = Field(..., description="Plain text content of the turn.")


class GenerateAppRequest(BaseModel):
    """Ask the model to create or update a single-file H5 application."""

    prompt: str = Field(..., description="User requirement or refinement instruction.")
    mode: Literal["create", "edit"] = Field(default="create", description="create or edit the current app.")
    app_name: Optional[str] = Field(default=None, description="Current app title, if any.")
    current_code: Optional[str] = Field(default=None, description="Current HTML source when editing.")
    history: List[VibeTurn] = Field(default_factory=list, description="Recent conversation turns.")


class GenerateAppResponse(BaseModel):
    """Generated application source plus short metadata."""

    code: str = Field(..., description="Complete single-file HTML source of the app.")
    title: str = Field(..., description="Short title of the app.")
    summary: str = Field(..., description="One sentence describing what changed.")
    model: str = Field(..., description="Model used for generation.")
