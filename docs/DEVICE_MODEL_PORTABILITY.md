# 设备型号可移植性说明

> 背景：被测设备为 ONU，**型号可能更换**（如 XPON UN-769XR → 其他型号）。
> 本项目的设计保证换 DUT 时只需改设备档案，不需要改测试用例。

## 设计原则

1. **用例绑定 `device_type`，不绑定型号**
   测试用例的 `device_type` 字段取值是 `ONU`/`OLT` 等类型，而不是
   `UN-769XR` 这样的具体型号。用例步骤里引用"ONU Web""OLT CLI"等
   通用入口，具体访问方式由设备档案与环境快照提供。

2. **Run 创建时生成不可变快照**
   - `device_snapshot`：记录当时的 vendor/model/serial/软件版本
   - `case_snapshot`：记录当时的用例内容
   - `environment_snapshot`：记录环境参数（凭据以 `credential:` 引用）
   报告、证据、缺陷都指向快照，历史记录不受换机影响。

3. **凭据与型号解耦**
   OLT/ONU 登录凭据存放在 keyring（`credential_references` 表只存引用
   名和掩码），换设备时更新凭据库即可，环境模板无需改动或只需改
   引用名。

## 换 DUT 操作清单

1. 设备库：新增（或更新）设备记录，填写真实 vendor/model/SN/软件版本。
   不要留 `Model-unverified`——设备快照的可信度取决于档案完整性。
2. 环境模板：更新 DUT 相关参数（管理 IP、ONT ID、F/S/P 等）；凭据引用
   如有变化同步更新 keyring。
3. 测试项目：用例选择不变（按 device_type 自动适用）。
4. 创建 Run：系统自动固化三份快照，之后正常执行并出报告。

## 报告中的呈现

- 报告页眉只显示**版本号 + 客户代码**；被测设备一行显示快照中的
  vendor/model/SN，测试设备细节在各用例的 preconditions/description 中说明。
- 因此换型号后生成的新报告自动展示新设备信息，报告模板零改动。
