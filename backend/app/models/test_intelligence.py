from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TestSkill(Base):
    __tablename__ = "test_skills"
    __table_args__ = (
        UniqueConstraint("skill_code", "version", name="uq_test_skills_code_version"),
        CheckConstraint(
            "status IN ('DRAFT','PUBLISHED','RETIRED')",
            name="ck_test_skills_status",
        ),
        CheckConstraint(
            "(status = 'DRAFT' AND published_at IS NULL) OR "
            "(status IN ('PUBLISHED','RETIRED') AND published_at IS NOT NULL)",
            name="ck_test_skills_published_at",
        ),
    )
    __test__ = False

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    skill_code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(30), nullable=False)
    spec_version: Mapped[str] = mapped_column(
        String(20), nullable=False, default="1.0", server_default="1.0"
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="DRAFT", server_default="DRAFT", index=True
    )
    applicable_devices: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    preconditions: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    environment_requirements: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    validation_methods: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    outputs: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
    parameters: Mapped[list[SkillParameter]] = relationship(
        back_populates="skill",
        cascade="all, delete-orphan",
        order_by="SkillParameter.display_order",
    )
    steps: Mapped[list[SkillStep]] = relationship(
        back_populates="skill",
        cascade="all, delete-orphan",
        order_by="SkillStep.step_no",
    )
    standard_bindings: Mapped[list[SkillStandardBinding]] = relationship(
        back_populates="skill", cascade="all, delete-orphan"
    )
    execution_rules: Mapped[list[SkillExecutionRule]] = relationship(
        back_populates="skill",
        cascade="all, delete-orphan",
        order_by="SkillExecutionRule.result_type, SkillExecutionRule.priority",
    )
    evidence_rules: Mapped[list[SkillEvidenceRule]] = relationship(
        back_populates="skill",
        cascade="all, delete-orphan",
        order_by="SkillEvidenceRule.display_order",
    )
    case_bindings: Mapped[list[SkillCase]] = relationship(
        back_populates="skill", cascade="all, delete-orphan"
    )
    runner_bindings = relationship(
        "SkillRunnerBinding",
        back_populates="skill",
        cascade="all, delete-orphan",
    )


class SkillParameter(Base):
    __tablename__ = "skill_parameters"
    __table_args__ = (
        UniqueConstraint("skill_id", "param_key", name="uq_skill_parameters_key"),
        UniqueConstraint("skill_id", "display_order", name="uq_skill_parameters_order"),
        CheckConstraint(
            "source IN ('CASE','RUN','ENVIRONMENT','DEVICE')",
            name="ck_skill_parameters_source",
        ),
        CheckConstraint("display_order >= 1", name="ck_skill_parameters_order"),
        CheckConstraint(
            "sensitive = 0 OR default_value IS NULL",
            name="ck_skill_parameters_sensitive_default",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    skill_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("test_skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    param_key: Mapped[str] = mapped_column(String(100), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    data_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    default_value: Mapped[Any | None] = mapped_column(JSON(none_as_null=True))
    constraints_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(30))
    sensitive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    description: Mapped[str | None] = mapped_column(Text)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    skill: Mapped[TestSkill] = relationship(back_populates="parameters")


class SkillStep(Base):
    __tablename__ = "skill_steps"
    __table_args__ = (
        UniqueConstraint("skill_id", "step_no", name="uq_skill_steps_number"),
        CheckConstraint("step_no >= 1", name="ck_skill_steps_number"),
        CheckConstraint(
            "execution_mode IN ('RUNNER','OPERATOR','HYBRID')",
            name="ck_skill_steps_execution_mode",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    skill_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("test_skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_no: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    expected_observation: Mapped[str] = mapped_column(Text, nullable=False)
    execution_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    evidence_rule_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    skill: Mapped[TestSkill] = relationship(back_populates="steps")


class SkillStandardBinding(Base):
    __tablename__ = "skill_standard_bindings"
    __table_args__ = (
        UniqueConstraint("skill_id", "binding_code", name="uq_skill_standard_bindings_code"),
        UniqueConstraint(
            "skill_id", "standard_requirement_id", "fact_key",
            name="uq_skill_standard_bindings_fact",
        ),
        CheckConstraint("on_match = 'PASS_CONDITION'", name="ck_skill_standard_bindings_match"),
        CheckConstraint("on_mismatch = 'FAIL'", name="ck_skill_standard_bindings_mismatch"),
        CheckConstraint("on_missing IN ('BLOCKED','DRAFT')", name="ck_skill_standard_bindings_missing"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    skill_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("test_skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    standard_requirement_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("standard_requirements.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    binding_code: Mapped[str] = mapped_column(String(120), nullable=False)
    fact_key: Mapped[str] = mapped_column(String(100), nullable=False)
    on_match: Mapped[str] = mapped_column(String(30), nullable=False, default="PASS_CONDITION", server_default="PASS_CONDITION")
    on_mismatch: Mapped[str] = mapped_column(String(20), nullable=False, default="FAIL", server_default="FAIL")
    on_missing: Mapped[str] = mapped_column(String(20), nullable=False, default="BLOCKED", server_default="BLOCKED")
    unit_conversion: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())
    skill: Mapped[TestSkill] = relationship(back_populates="standard_bindings")
    requirement = relationship("StandardRequirement")


class SkillExecutionRule(Base):
    __tablename__ = "skill_execution_rules"
    __table_args__ = (
        UniqueConstraint("skill_id", "rule_code", name="uq_skill_execution_rules_code"),
        UniqueConstraint("skill_id", "result_type", "priority", name="uq_skill_execution_rules_priority"),
        CheckConstraint("result_type IN ('PASS','FAIL','BLOCKED')", name="ck_skill_execution_rules_result"),
        CheckConstraint(
            "operator IN ('EQ','NE','GT','GTE','LT','LTE','IN','NOT_IN','EXISTS','NOT_EXISTS','MATCHES','CIDR_CONTAINS')",
            name="ck_skill_execution_rules_operator",
        ),
        CheckConstraint("priority >= 1", name="ck_skill_execution_rules_priority"),
        CheckConstraint("evaluation_source IN ('FIXED','STANDARD')", name="ck_skill_execution_rules_source"),
        CheckConstraint(
            "NOT (expected_value IS NOT NULL AND expected_parameter_key IS NOT NULL)",
            name="ck_skill_execution_rules_one_expectation",
        ),
        CheckConstraint(
            "operator NOT IN ('EXISTS','NOT_EXISTS') OR (expected_value IS NULL AND expected_parameter_key IS NULL)",
            name="ck_skill_execution_rules_exists_expectation",
        ),
        CheckConstraint(
            "(evaluation_source = 'STANDARD' AND standard_binding_id IS NOT NULL AND expected_value IS NULL AND expected_parameter_key IS NULL) OR "
            "(evaluation_source = 'FIXED' AND standard_binding_id IS NULL)",
            name="ck_skill_execution_rules_standard_binding",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    skill_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("test_skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rule_code: Mapped[str] = mapped_column(String(100), nullable=False)
    result_type: Mapped[str] = mapped_column(String(20), nullable=False)
    fact_key: Mapped[str] = mapped_column(String(100), nullable=False)
    operator: Mapped[str] = mapped_column(String(30), nullable=False)
    expected_value: Mapped[Any | None] = mapped_column(JSON(none_as_null=True))
    expected_parameter_key: Mapped[str | None] = mapped_column(String(100))
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    evaluation_source: Mapped[str] = mapped_column(String(20), nullable=False)
    standard_binding_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("skill_standard_bindings.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())
    skill: Mapped[TestSkill] = relationship(back_populates="execution_rules")
    standard_binding: Mapped[SkillStandardBinding | None] = relationship()


class SkillEvidenceRule(Base):
    __tablename__ = "skill_evidence_rules"
    __table_args__ = (
        UniqueConstraint("skill_id", "rule_code", name="uq_skill_evidence_rules_code"),
        UniqueConstraint("skill_id", "display_order", name="uq_skill_evidence_rules_order"),
        CheckConstraint("category IN ('SCREENSHOT','LOG','CONFIG','OTHER')", name="ck_skill_evidence_rules_category"),
        CheckConstraint("min_count >= 0", name="ck_skill_evidence_rules_min_count"),
        CheckConstraint("max_count IS NULL OR max_count >= min_count", name="ck_skill_evidence_rules_max_count"),
        CheckConstraint("display_order >= 1", name="ck_skill_evidence_rules_order"),
        CheckConstraint("sensitive_content IN ('NONE','REDACT','PROHIBITED')", name="ck_skill_evidence_rules_sensitive"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    skill_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("test_skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rule_code: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    required_for: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    min_count: Mapped[int] = mapped_column(Integer, nullable=False)
    max_count: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    sensitive_content: Mapped[str] = mapped_column(String(20), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    skill: Mapped[TestSkill] = relationship(back_populates="evidence_rules")


class SkillCase(Base):
    __tablename__ = "skill_cases"
    __table_args__ = (
        CheckConstraint("binding_version >= 1", name="ck_skill_cases_binding_version"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    skill_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("test_skills.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    test_case_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("test_cases.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    parameter_values: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    binding_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    skill: Mapped[TestSkill] = relationship(back_populates="case_bindings")
    test_case = relationship("TestCase")


class Template(Base):
    __tablename__ = "templates"
    __table_args__ = (
        UniqueConstraint("template_code", "version", name="uq_templates_code_version"),
        CheckConstraint("status IN ('DRAFT','ACTIVE','RETIRED')", name="ck_templates_status"),
        CheckConstraint("version >= 1", name="ck_templates_version"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    template_code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT", server_default="DRAFT", index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    cases: Mapped[list[TemplateCase]] = relationship(
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="TemplateCase.display_order",
    )


class TemplateCase(Base):
    __tablename__ = "template_cases"
    __table_args__ = (
        UniqueConstraint("template_id", "display_order", name="uq_template_cases_order"),
        CheckConstraint("display_order >= 1", name="ck_template_cases_order"),
    )

    template_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("templates.id", ondelete="CASCADE"), primary_key=True
    )
    test_case_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("test_cases.id", ondelete="RESTRICT"), primary_key=True
    )
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())
    template: Mapped[Template] = relationship(back_populates="cases")
    test_case = relationship("TestCase")
