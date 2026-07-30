from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EnvironmentParameterWrite(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    section: str = Field(min_length=1, max_length=100)
    param_key: str = Field(min_length=1, max_length=100)
    param_value: str = Field(max_length=4000)
    display_order: int = Field(ge=1)


class EnvironmentProfileWrite(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    enabled: bool = True
    parameters: list[EnvironmentParameterWrite] = Field(default_factory=list)


class EnvironmentParameterRead(EnvironmentParameterWrite):
    model_config = ConfigDict(from_attributes=True)

    id: str
    profile_id: str
    created_at: datetime
    updated_at: datetime


class EnvironmentProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None
    enabled: bool
    created_at: datetime
    updated_at: datetime
    parameters: list[EnvironmentParameterRead]
