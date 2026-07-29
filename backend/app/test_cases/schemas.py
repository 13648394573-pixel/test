from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CaseStepWrite(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    action: str = Field(min_length=1)
    expected_result: str = Field(min_length=1)


class CaseStepRead(CaseStepWrite):
    model_config = ConfigDict(from_attributes=True)

    id: str
    test_case_id: str
    step_number: int
    created_at: datetime
    updated_at: datetime


class TestCaseBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    case_code: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    device_type: str | None = Field(default=None, max_length=50)
    category: str = Field(min_length=1, max_length=100)
    priority: Literal["P0", "P1", "P2", "P3"] = "P2"
    preconditions: str | None = None
    description: str | None = None
    enabled: bool = True


class TestCaseWrite(TestCaseBase):
    steps: list[CaseStepWrite] = Field(min_length=1)


class TestCaseRead(TestCaseBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime
    steps: list[CaseStepRead]
