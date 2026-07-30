from typing import Any

from app.models.device import Device
from app.models.test_case import TestCase


def build_device_snapshot(device: Device) -> dict[str, Any]:
    return {
        "device_type": device.device_type,
        "vendor": device.vendor,
        "model": device.model,
        "serial_number": device.serial_number,
        "mac_address": device.mac_address,
        "hardware_version": device.hardware_version,
        "software_version": device.software_version,
    }


def build_case_snapshot(test_case: TestCase) -> dict[str, Any]:
    return {
        "case_code": test_case.case_code,
        "title": test_case.title,
        "device_type": test_case.device_type,
        "category": test_case.category,
        "priority": test_case.priority,
        "preconditions": test_case.preconditions,
        "description": test_case.description,
        "enabled": test_case.enabled,
        "steps": [
            {
                "step_number": step.step_number,
                "action": step.action,
                "expected_result": step.expected_result,
            }
            for step in sorted(
                test_case.steps,
                key=lambda item: item.step_number,
            )
        ],
    }
