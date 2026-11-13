"""The reader's fixed JSON shape: {"flags": [{"code", "text"}], "summary"}. Nothing else gets through."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

FlagCode = Literal["addresses_agents", "gives_instruction", "mentions_claim"]


class Flag(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    code: FlagCode
    text: str = Field(max_length=200)  # the words in the supplier text that raised the flag


class ReaderResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    flags: list[Flag] = Field(max_length=20)
    summary: str = Field(max_length=400)


JSON_SCHEMA = ReaderResult.model_json_schema()
