from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any

from app.models.runner_registry import RunnerAction, RunnerPlugin, SkillRunnerBinding
from app.models.test_case import CaseStep, TestCase
from app.models.test_intelligence import (
    SkillCase,
    SkillEvidenceRule,
    SkillExecutionRule,
    SkillParameter,
    SkillStandardBinding,
    SkillStep,
    Template,
    TemplateCase,
    TestSkill,
)
from app.models.test_standard import (
    StandardProfile,
    StandardProfileItem,
    StandardRequirement,
    TestStandard,
)
from app.skill_catalog.onu_registration_dual_wan import CATALOG
from app.skill_catalog.repository import SkillCatalogRepository


class CatalogVersionConflictError(Exception):
    pass


class SkillCatalogNotFoundError(Exception):
    pass


@dataclass(frozen=True)
class CatalogInstallResult:
    skill_id: str
    created: bool
    definition_hash: str
    evidence_codes: tuple[str, ...]


def catalog_definition_hash() -> str:
    payload = json.dumps(
        CATALOG.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class SkillCatalogService:
    HASH_TAG_PREFIX = "definition-sha256:"
    PLUGIN_CODE = "ONU_LOCAL_RUNNER"

    def __init__(self, repository: SkillCatalogRepository):
        self.repository = repository

    def install_onu_registration_dual_wan_draft(self) -> CatalogInstallResult:
        definition_hash = catalog_definition_hash()
        expected_tag = f"{self.HASH_TAG_PREFIX}{definition_hash}"
        existing = self.repository.find_skill(CATALOG.skill_code, CATALOG.version)
        if existing is not None:
            if expected_tag not in existing.tags:
                raise CatalogVersionConflictError(
                    "Catalog version exists with a different definition"
                )
            return self._install_result(existing, False, definition_hash)

        try:
            test_case = self._create_test_case()
            standard, requirements = self._create_standard()
            profile = StandardProfile(
                profile_code=CATALOG.standard_profile_code,
                version=1,
                name="ONU 双 WAN 基线标准",
                description="可由后续客户、国家和地区标准扩展的内部基线。",
                merge_policy="ALL_MANDATORY_MUST_PASS",
                status="DRAFT",
            )
            profile.items.append(
                StandardProfileItem(standard=standard, required=True, display_order=1)
            )
            template = Template(
                template_code=CATALOG.template_code,
                version=1,
                name="ONU 注册与双 WAN 验证模板",
                description="首个真实 ONU Skill 的单用例模板。",
                status="DRAFT",
            )
            template.cases.append(
                TemplateCase(test_case=test_case, display_order=1, required=True)
            )
            skill = self._create_skill(expected_tag, test_case)
            plugin = self._create_plugin(definition_hash)
            self.repository.add(profile)
            self.repository.add(template)
            self.repository.add(skill)
            self.repository.add(plugin)
            self.repository.flush()
            self._bind_standard(skill, requirements)
            self._bind_actions(skill, plugin)
            self.repository.commit()
        except Exception:
            self.repository.rollback()
            raise
        return self._install_result(skill, True, definition_hash)

    def list(self) -> list[dict[str, Any]]:
        return [self._summary(skill) for skill in self.repository.list_skills()]

    def get(self, skill_id: str) -> dict[str, Any]:
        skill = self.repository.get_skill(skill_id)
        if skill is None:
            raise SkillCatalogNotFoundError(skill_id)
        definition_hash = self._stored_hash(skill)
        standards = {
            binding.requirement.standard for binding in skill.standard_bindings
        }
        standard = next(iter(standards), None)
        profile = self.repository.get_profile(CATALOG.standard_profile_code)
        actions = [
            {
                "action_code": binding.runner_action.action_code,
                "phase": binding.phase,
                "required": binding.required,
            }
            for binding in sorted(
                skill.runner_bindings,
                key=lambda item: (item.phase, item.display_order),
            )
        ]
        runner_statuses = sorted(
            {binding.runner_action.plugin.status for binding in skill.runner_bindings}
        )
        return {
            **self._summary(skill),
            "objective": skill.objective,
            "description": skill.description,
            "definition_hash": definition_hash,
            "parameters": [
                {
                    "key": item.param_key,
                    "label": item.label,
                    "data_type": item.data_type,
                    "source": item.source,
                    "required": item.required,
                    "default": item.default_value,
                    "constraints": item.constraints_json,
                    "sensitive": item.sensitive,
                }
                for item in skill.parameters
            ],
            "steps": [
                {
                    "step_no": item.step_no,
                    "title": item.title,
                    "action": item.action,
                    "expected_observation": item.expected_observation,
                    "execution_mode": item.execution_mode,
                    "evidence_rule_refs": item.evidence_rule_refs,
                }
                for item in skill.steps
            ],
            "evidence_rules": [
                {
                    "rule_code": item.rule_code,
                    "title": item.title,
                    "description": item.description,
                    "required_for": item.required_for,
                    "min_count": item.min_count,
                    "sensitive_content": item.sensitive_content,
                }
                for item in skill.evidence_rules
            ],
            "standard": None
            if standard is None
            else {
                "standard_code": standard.standard_code,
                "version": standard.version,
                "status": standard.status,
            },
            "standard_profile": None
            if profile is None
            else {
                "profile_code": profile.profile_code,
                "version": profile.version,
                "status": profile.status,
            },
            "actions": actions,
            "runner_statuses": runner_statuses,
        }

    def _create_test_case(self) -> TestCase:
        test_case = TestCase(
            case_code=CATALOG.test_case_code,
            title=CATALOG.name,
            device_type="ONU",
            category="WAN",
            priority="P1",
            preconditions="测试环境、OLT 和 ONU 可达；参数由环境模板与执行前确认提供。",
            description=CATALOG.description,
            enabled=True,
        )
        for number, step in enumerate(CATALOG.steps, start=1):
            test_case.steps.append(
                CaseStep(
                    step_number=number,
                    action=step.action,
                    expected_result=step.expected_observation,
                )
            )
        return test_case

    def _create_standard(self) -> tuple[TestStandard, dict[str, StandardRequirement]]:
        standard = TestStandard(
            standard_code=CATALOG.standard_code,
            version=CATALOG.standard_version,
            title="ONU 注册与双 WAN 联网内部基线",
            source_type="INTERNAL",
            issuer="UNPON",
            language_code="zh-CN",
            status="DRAFT",
            source_reference="ONU Test Skill Specification V1.0",
            description="DRAFT：须经真实实验室 PASS/FAIL/BLOCKED 验证后发布。",
        )
        requirements: dict[str, StandardRequirement] = {}
        for number, item in enumerate(CATALOG.requirements, start=1):
            requirement = StandardRequirement(
                requirement_code=item.code,
                title=item.title,
                description=item.description,
                requirement_level="MANDATORY",
                applicability={"olt": list(CATALOG.supported_olts)},
                data_type=item.data_type,
                operator=item.operator,
                expected_value=item.expected,
                source_text_reference=f"Skill {CATALOG.skill_code}/{item.code}",
                display_order=number,
            )
            standard.requirements.append(requirement)
            requirements[item.code] = requirement
        return standard, requirements

    def _create_skill(self, hash_tag: str, test_case: TestCase) -> TestSkill:
        skill = TestSkill(
            skill_code=CATALOG.skill_code,
            version=CATALOG.version,
            spec_version="1.0",
            name=CATALOG.name,
            objective=CATALOG.objective,
            description=CATALOG.description,
            status="DRAFT",
            applicable_devices=[{"device_type": "ONU", "olt": item} for item in CATALOG.supported_olts],
            preconditions=[{"code": "LOCAL_LAB_READY", "required": True}],
            environment_requirements=[{"code": "OFFLINE_LOCAL_RUNNER", "required": True}],
            validation_methods=[{"code": "STANDARD_RULES_AND_EVIDENCE"}],
            outputs=[{"code": "VERDICT"}, {"code": "EVIDENCE_CHAIN"}],
            tags=["ONU", "WAN", "REGISTRATION", hash_tag],
        )
        for number, item in enumerate(CATALOG.parameters, start=1):
            skill.parameters.append(
                SkillParameter(
                    param_key=item.key,
                    label=item.label,
                    data_type=item.data_type,
                    source=item.source,
                    required=item.required,
                    default_value=item.default,
                    constraints_json=item.constraints,
                    sensitive=item.sensitive,
                    description=item.description,
                    display_order=number,
                )
            )
        for number, item in enumerate(CATALOG.steps, start=1):
            skill.steps.append(
                SkillStep(
                    step_no=number,
                    title=item.title,
                    action=item.action,
                    expected_observation=item.expected_observation,
                    execution_mode=item.execution_mode,
                    required=True,
                    evidence_rule_refs=list(item.evidence_refs),
                )
            )
        for number, item in enumerate(CATALOG.evidence, start=1):
            skill.evidence_rules.append(
                SkillEvidenceRule(
                    rule_code=item.code,
                    category="SCREENSHOT",
                    title=item.title,
                    required_for=list(item.required_for),
                    min_count=item.min_count,
                    max_count=item.max_count,
                    description=item.description,
                    sensitive_content=item.sensitive_content,
                    display_order=number,
                )
            )
        skill.case_bindings.append(SkillCase(test_case=test_case, parameter_values={}))
        return skill

    def _create_plugin(self, definition_hash: str) -> RunnerPlugin:
        plugin = RunnerPlugin(
            plugin_code=self.PLUGIN_CODE,
            version=CATALOG.version,
            status="DEVELOPMENT",
            manifest_json={
                "catalog": CATALOG.skill_code,
                "definition_hash": definition_hash,
                "platform": "windows-local",
                "allow_listed": True,
            },
            package_sha256=definition_hash,
            install_path_ref="plugins/onu-local-runner/1.0.0",
        )
        for item in CATALOG.actions:
            plugin.actions.append(
                RunnerAction(
                    action_code=item.code,
                    phase=item.phase,
                    input_schema={"type": "object", "additionalProperties": False},
                    output_schema={"observations": list(item.observation_keys)},
                    timeout_seconds=item.timeout_seconds,
                    idempotent=item.idempotent,
                    recovery_capability=item.recovery_capability,
                    adapter_selector={"olt_vendor": "Huawei", "olt_model": "MA5800-X7"},
                )
            )
        return plugin

    def _bind_standard(
        self,
        skill: TestSkill,
        requirements: dict[str, StandardRequirement],
    ) -> None:
        for priority, item in enumerate(CATALOG.requirements, start=1):
            binding = SkillStandardBinding(
                binding_code=f"BIND_{item.code}",
                requirement=requirements[item.code],
                fact_key=item.fact_key,
                on_match="PASS_CONDITION",
                on_mismatch="FAIL",
                on_missing="BLOCKED",
            )
            skill.standard_bindings.append(binding)
            self.repository.flush()
            skill.execution_rules.append(
                SkillExecutionRule(
                    rule_code=f"PASS_{item.code}",
                    result_type="PASS",
                    fact_key=item.fact_key,
                    operator=item.operator,
                    required=True,
                    priority=priority,
                    message=item.description,
                    evaluation_source="STANDARD",
                    standard_binding=binding,
                )
            )
            skill.execution_rules.append(
                SkillExecutionRule(
                    rule_code=f"BLOCKED_{item.code}",
                    result_type="BLOCKED",
                    fact_key=item.fact_key,
                    operator="NOT_EXISTS",
                    required=True,
                    priority=priority,
                    message=f"缺少判定事实：{item.title}",
                    evaluation_source="FIXED",
                )
            )

    def _bind_actions(self, skill: TestSkill, plugin: RunnerPlugin) -> None:
        step_by_code = dict(zip((item.code for item in CATALOG.steps), skill.steps))
        action_by_code = {item.action_code: item for item in plugin.actions}
        phase_order: dict[str, int] = {}
        for item in CATALOG.actions:
            phase_order[item.phase] = phase_order.get(item.phase, 0) + 1
            skill.runner_bindings.append(
                SkillRunnerBinding(
                    skill_step=step_by_code.get(item.step_code),
                    runner_action=action_by_code[item.code],
                    phase=item.phase,
                    parameter_mapping={"source": "execution_snapshot"},
                    observation_mapping={key: key for key in item.observation_keys},
                    adapter_selector={"olt_vendor": "Huawei", "olt_model": "MA5800-X7"},
                    required=True,
                    display_order=phase_order[item.phase],
                )
            )

    def _install_result(
        self, skill: TestSkill, created: bool, definition_hash: str
    ) -> CatalogInstallResult:
        return CatalogInstallResult(
            skill_id=skill.id,
            created=created,
            definition_hash=definition_hash,
            evidence_codes=tuple(item.code for item in CATALOG.evidence),
        )

    def _stored_hash(self, skill: TestSkill) -> str:
        for tag in skill.tags:
            if tag.startswith(self.HASH_TAG_PREFIX):
                return tag.removeprefix(self.HASH_TAG_PREFIX)
        return ""

    def _summary(self, skill: TestSkill) -> dict[str, Any]:
        supported = [
            item["olt"] for item in skill.applicable_devices if item.get("olt")
        ]
        return {
            "id": skill.id,
            "skill_code": skill.skill_code,
            "version": skill.version,
            "name": skill.name,
            "status": skill.status,
            "supported_olts": supported,
            "definition_hash": self._stored_hash(skill),
        }
