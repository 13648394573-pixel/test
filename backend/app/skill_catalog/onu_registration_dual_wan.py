from app.skill_catalog.definitions import (
    ActionDefinition,
    CatalogDefinition,
    EvidenceDefinition,
    ParameterDefinition,
    RequirementDefinition,
    StepDefinition,
)
from app.local_runner.ma5800.service_port_contracts import ServicePortProfile


def build_service_port_plan(parameters: dict, profile: ServicePortProfile | None) -> dict:
    """New sessions only: retain registration, freeze mappings, preserve isolation."""
    if not isinstance(profile, ServicePortProfile) or profile.ipoe is None or profile.pppoe is None:
        raise ValueError('Explicit mappings for both WAN consumers are required')
    concurrent = parameters.get('execution_mode') == 'CONCURRENT_DUAL_WAN'
    if parameters.get('execution_mode') not in {'SEQUENTIAL_ISOLATED', 'CONCURRENT_DUAL_WAN'}:
        raise ValueError('Unsupported WAN execution mode')
    if parameters.get('end_policy') not in {'KEEP', 'RESTORE'}:
        raise ValueError('Explicit end policy is required')
    groups = {}
    for wan in ('IPOE', 'PPPOE'):
        spec = getattr(profile, wan.lower())
        if type(parameters.get(wan.lower() + '_vlan')) is not int or spec.vlan != parameters[wan.lower() + '_vlan']:
            raise ValueError('Frozen service-port profile and WAN VLAN differ')
        mapping = spec.model_dump(mode='json')
        key = tuple(sorted(spec.model_dump(exclude={'candidate_id'}).items()))
        group = groups.setdefault(key, {'mapping': mapping, 'consumers': []})
        if group['mapping']['candidate_id'] != spec.candidate_id:
            raise ValueError('Shared mapping has conflicting explicit candidates')
        group['consumers'].append(wan)
    def action(ref, code, step, group=None, method='OLT_RENDER', wan=None):
        return dict(ref=ref, action=code, step=step, group=group, method=method, wan=wan)
    def interaction(ref, choices, step):
        return dict(ref=ref, interaction=choices, step=step)
    steps = [action('PREFLIGHT', 'preflight', 'PREFLIGHT'),
             action('VERIFY_REGISTRATION', 'verify_existing_registration', 'REGISTER', 'E1_OLT_AUTOFIND'),
             action('SNAPSHOT', 'snapshot_ont', 'REGISTER', 'E2_REGISTRATION')]
    for index, group in enumerate(groups.values(), 1):
        for suffix, code in [('INSPECT', 'inspect_service_mapping'), ('CREATE', 'create_service_port'),
                             ('VERIFY', 'verify_service_port')]:
            steps.append({**action(f'SERVICE_{index}_{suffix}', code, 'REGISTER'),
                          'mapping': dict(group['mapping']), 'consumers': list(group['consumers'])})
    steps.append(action('PROVISION_IPOE', 'provision_ipoe', 'IPOE_ADDRESS'))
    if concurrent:
        steps.append(action('PROVISION_PPPOE', 'provision_pppoe', 'PPPOE_ADDRESS'))
    for wan, address_group, ping_group in [('IPOE', 'E3_IPOE_ADDRESS', 'E4_IPOE_PING'),
                                          ('PPPOE', 'E5_PPPOE_ADDRESS', 'E6_PPPOE_PING')]:
        if wan == 'PPPOE' and not concurrent:
            steps += [interaction('ISOLATE_IPOE', ['IPOE_DISABLED', 'UNABLE', 'CANCEL'], 'PPPOE_ADDRESS'),
                      action('PROVISION_PPPOE', 'provision_pppoe', 'PPPOE_ADDRESS')]
        if concurrent:
            steps.append(interaction(f'SWITCH_{wan}', [f'{wan}_ACTIVE', 'UNABLE', 'CANCEL'], f'{wan}_PING'))
        steps += [action(f'{wan}_ADDRESS_OLT', 'read_wan_info', f'{wan}_ADDRESS', address_group, wan=wan),
                  action(f'{wan}_ADDRESS_WEB', 'capture_onu_wan', f'{wan}_ADDRESS', address_group, 'ONU_WEB', wan),
                  action(f'{wan}_PING_ONU', 'run_onu_ping', f'{wan}_PING', ping_group, 'ONU_WEB', wan),
                  action(f'{wan}_PING_PC', 'pc_connectivity_probe', f'{wan}_PING', ping_group, 'PC_PROBE', wan)]
    steps.append(interaction('END_POLICY', ['KEEP', 'CANCEL'], 'FINISH'))
    return {'version': 2, 'steps': steps}


CATALOG = CatalogDefinition(
    skill_code="ONU_REGISTRATION_DUAL_WAN_CONNECTIVITY",
    version="1.0.0",
    status="DRAFT",
    name="ONU 注册与双 WAN 联网验证",
    objective="验证 ONU 上报、注册、IPoE/PPPoE 地址获取及两侧联网能力。",
    description="默认逐条隔离验证两条 WAN，并保留 OLT、ONU Web 与电脑侧证据链。",
    standard_code="UNPON_ONU_REGISTRATION_DUAL_WAN",
    standard_version="1.0.0",
    standard_profile_code="UNPON_DUAL_WAN_BASELINE",
    test_case_code="ONU-REG-DUAL-WAN-001",
    template_code="ONU-REG-DUAL-WAN-TEMPLATE",
    supported_olts=("Huawei MA5800-X7",),
    parameters=(
        ParameterDefinition("olt_target_ref", "OLT 目标引用", "STRING", "ENVIRONMENT", True, None, {}),
        ParameterDefinition("olt_access_ref", "OLT 访问引用", "STRING", "ENVIRONMENT", True, None, {}, True),
        ParameterDefinition("onu_web_target_ref", "ONU Web 目标引用", "STRING", "ENVIRONMENT", True, None, {}),
        ParameterDefinition("onu_web_access_ref", "ONU Web 访问引用", "STRING", "ENVIRONMENT", True, None, {}, True),
        ParameterDefinition("pppoe_access_ref", "PPPoE 接入引用", "STRING", "ENVIRONMENT", True, None, {}, True),
        ParameterDefinition("onu_serial_number", "ONU 序列号", "STRING", "DEVICE", True, None, {}),
        ParameterDefinition("frame", "机框", "INTEGER", "ENVIRONMENT", True, None, {"minimum": 0}),
        ParameterDefinition("slot", "槽位", "INTEGER", "ENVIRONMENT", True, None, {"minimum": 0}),
        ParameterDefinition("pon_port", "PON 端口", "INTEGER", "ENVIRONMENT", True, None, {"minimum": 0}),
        ParameterDefinition("ont_id", "ONT ID", "INTEGER", "RUN", True, None, {"minimum": 0}),
        ParameterDefinition("line_profile_id", "线路模板 ID", "INTEGER", "ENVIRONMENT", True, None, {"minimum": 0}),
        ParameterDefinition("service_profile_id", "业务模板 ID", "INTEGER", "ENVIRONMENT", True, None, {"minimum": 0}),
        ParameterDefinition("ipoe_vlan", "IPoE VLAN", "INTEGER", "ENVIRONMENT", True, None, {"minimum": 1, "maximum": 4094}),
        ParameterDefinition("pppoe_vlan", "PPPoE VLAN", "INTEGER", "ENVIRONMENT", True, None, {"minimum": 1, "maximum": 4094}),
        ParameterDefinition("ping_target", "Ping 目标", "STRING", "ENVIRONMENT", True, None, {}),
        ParameterDefinition("execution_mode", "双 WAN 执行模式", "ENUM", "RUN", True, "SEQUENTIAL_ISOLATED", {"choices": ["SEQUENTIAL_ISOLATED", "CONCURRENT_DUAL_WAN"]}),
        ParameterDefinition("evaluation_policy", "判定策略", "ENUM", "RUN", True, "STRICT_PER_WAN", {"choices": ["STRICT_PER_WAN", "CUSTOMER_SIMPLIFIED"]}),
        ParameterDefinition("end_policy", "结束处理", "ENUM", "RUN", True, "RESTORE", {"choices": ["RESTORE", "KEEP"]}),
    ),
    steps=(
        StepDefinition("PREFLIGHT", "执行前检查", "检查本机、OLT、ONU Web 和测试参数。", "所有必要条件满足。", "HYBRID"),
        StepDefinition("AUTOFIND", "确认 ONU 上报", "读取 OLT 自动发现结果并保存截图。", "目标 ONU 信息可识别。", "RUNNER", ("E1_OLT_AUTOFIND",)),
        StepDefinition("REGISTER", "注册 ONU", "经确认后注册或替换现有注册。", "ONU 注册成功并处于可验证状态。", "HYBRID", ("E2_REGISTRATION",)),
        StepDefinition("IPOE_ADDRESS", "验证 IPoE 地址", "下发 IPoE 并从 OLT 与 ONU Web 双侧取证。", "IPoE 获取符合标准的地址。", "RUNNER", ("E3_IPOE_ADDRESS",)),
        StepDefinition("IPOE_PING", "验证 IPoE 联网", "执行 ONU 诊断与电脑侧探测。", "IPoE 联网符合所选标准。", "HYBRID", ("E4_IPOE_PING",)),
        StepDefinition("PPPOE_ADDRESS", "验证 PPPoE 地址", "下发 PPPoE 并从 OLT 与 ONU Web 双侧取证。", "PPPoE 拨号成功并获取地址。", "RUNNER", ("E5_PPPOE_ADDRESS",)),
        StepDefinition("PPPOE_PING", "验证 PPPoE 联网", "执行 ONU 诊断与电脑侧探测。", "PPPoE 联网符合所选标准。", "HYBRID", ("E6_PPPOE_PING",)),
        StepDefinition("FINISH", "结束与恢复", "确认恢复原配置或保留当前配置。", "选择被记录，必要恢复已验证。", "HYBRID"),
    ),
    requirements=(
        RequirementDefinition("ONU_REPORTED", "ONU 正常上报", "OLT 可识别目标 ONU 上报信息。", "olt.autofind.matched"),
        RequirementDefinition("ONU_REGISTERED", "ONU 注册成功", "ONU 注册状态满足基线。", "olt.registration.ready"),
        RequirementDefinition("IPOE_HAS_ADDRESS", "IPoE 获取地址", "OLT 与 ONU Web 均显示有效 IPoE 地址。", "ipoe.address.valid"),
        RequirementDefinition("IPOE_INTERNET", "IPoE 可联网", "ONU 与电脑侧 IPoE 联网结果满足策略。", "ipoe.internet.pass"),
        RequirementDefinition("PPPOE_HAS_ADDRESS", "PPPoE 获取地址", "OLT 与 ONU Web 均显示有效 PPPoE 地址。", "pppoe.address.valid"),
        RequirementDefinition("PPPOE_INTERNET", "PPPoE 可联网", "ONU 与电脑侧 PPPoE 联网结果满足策略。", "pppoe.internet.pass"),
    ),
    evidence=(
        EvidenceDefinition("E1_OLT_AUTOFIND", "OLT 上报 ONU 信息", "保存目标 ONU 自动发现信息截图。", "REDACT", ("OLT_RENDER",)),
        EvidenceDefinition("E2_REGISTRATION", "ONU 注册成功", "保存 ONU 注册和在线状态截图。", "REDACT", ("OLT_RENDER",)),
        EvidenceDefinition("E3_IPOE_ADDRESS", "IPoE 地址", "保存 OLT WAN 信息与 ONU Web WAN 页面截图。", "REDACT", ("OLT_RENDER", "ONU_WEB"), min_count=2),
        EvidenceDefinition("E4_IPOE_PING", "IPoE 联网", "保存 ONU Ping 与电脑侧联网证据。", "REDACT", ("ONU_WEB", "PC_PROBE", "OPERATOR"), min_count=2),
        EvidenceDefinition("E5_PPPOE_ADDRESS", "PPPoE 地址", "保存 OLT WAN 信息与 ONU Web WAN 页面截图。", "REDACT", ("OLT_RENDER", "ONU_WEB"), min_count=2),
        EvidenceDefinition("E6_PPPOE_PING", "PPPoE 联网", "保存 ONU Ping 与电脑侧联网证据。", "REDACT", ("ONU_WEB", "PC_PROBE", "OPERATOR"), min_count=2),
    ),
    actions=(
        ActionDefinition("preflight", "PREFLIGHT", "PREFLIGHT", 30, True, "NONE"),
        ActionDefinition("discover_onts", "VERIFY", "AUTOFIND", 60, True, "NONE", ("olt.autofind.matched",)),
        ActionDefinition("snapshot_ont", "SNAPSHOT", "REGISTER", 90, True, "RESTORE"),
        ActionDefinition("find_free_ont_id", "PREFLIGHT", "REGISTER", 60, True, "NONE"),
        ActionDefinition("delete_ont", "EXECUTE", "REGISTER", 120, False, "RESTORE_VERIFY"),
        ActionDefinition("register_ont", "EXECUTE", "REGISTER", 120, False, "RESTORE_VERIFY"),
        ActionDefinition("provision_ipoe", "EXECUTE", "IPOE_ADDRESS", 120, False, "RESTORE_VERIFY"),
        ActionDefinition("read_wan_info", "VERIFY", "IPOE_ADDRESS", 90, True, "NONE", ("ipoe.address.valid", "pppoe.address.valid")),
        ActionDefinition("pc_connectivity_probe", "VERIFY", "IPOE_PING", 60, True, "NONE", ("ipoe.internet.pass", "pppoe.internet.pass")),
        ActionDefinition("remove_test_services", "RESTORE", "PPPOE_ADDRESS", 120, False, "RESTORE_VERIFY"),
        ActionDefinition("provision_pppoe", "EXECUTE", "PPPOE_ADDRESS", 120, False, "RESTORE_VERIFY"),
        ActionDefinition("restore_snapshot", "RESTORE", "FINISH", 180, False, "RESTORE_VERIFY"),
        ActionDefinition("verify_restore", "RESTORE_VERIFY", "FINISH", 90, True, "NONE"),
    ),
)
