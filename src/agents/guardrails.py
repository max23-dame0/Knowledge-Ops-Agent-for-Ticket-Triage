"""Guardrails and validation helpers for agents.

Contains prompt-injection / exfiltration detection helpers used by the
refusal precheck. The keyword list is a cheap first line of defense; the
offline eval set keeps adversarial variants covered so regressions surface
quickly.
"""

from __future__ import annotations

import re

# Phrasing that tries to extract internal system context.
SYSTEM_EXFILTRATION_PATTERNS = (
    re.compile(r"(system|system prompt|系统).{0,12}(prompt|提示词|指令|规则)", re.IGNORECASE),
    re.compile(r"(prompt|提示词|指令|规则).{0,12}(泄露|导出|输出|复制|打印|展示)", re.IGNORECASE),
    re.compile(r"(api\s*key|密钥|令牌|token).{0,12}(泄露|导出|全部|所有)", re.IGNORECASE),
    re.compile(r"(隐藏|内部|未公开).{0,6}(指令|规则|配置)", re.IGNORECASE),
)

# Phrasing that tries to bypass policy through encoding / roleplay / injection.
BYPASS_PATTERNS = (
    re.compile(r"(base64|rot13|编码|解码|加密|十六进制|hex)\s*(输出|回复|形式|方式)", re.IGNORECASE),
    re.compile(r"(忽略|无视|跳过|忘记).{0,8}(之前|先前|上面|以上|设定|指令)", re.IGNORECASE),
    re.compile(r"(现在|接下来)\s*(你是|扮演|假装)\s*(一个|一名)?\s*(不受限制|没有约束|自由)", re.IGNORECASE),
    re.compile(r"(do not follow|ignore (all )?(previous|prior)|disregard).{0,20}(instructions|rules|prompt)", re.IGNORECASE),
    re.compile(r"(jailbreak|越狱|越权|绕过|突破).{0,8}(限制|规则|审核)", re.IGNORECASE),
)

# Bulk-sensitive-data requests.
BULK_DATA_PATTERNS = (
    re.compile(r"(所有|全部|每个).{0,10}(用户|客户|账号).{0,10}(账单|邮箱|密码|手机号|地址)", re.IGNORECASE),
    re.compile(r"(导出|下载|拉取).{0,12}(所有|全部).{0,8}(数据|记录|信息)", re.IGNORECASE),
)


def looks_like_injection_attack(user_input: str) -> bool:
    """Return True when the input resembles a prompt-injection / exfiltration attempt."""
    lowered = user_input.lower()
    return any(pattern.search(lowered) for pattern in SYSTEM_EXFILTRATION_PATTERNS) or any(
        pattern.search(lowered) for pattern in BYPASS_PATTERNS
    ) or any(pattern.search(lowered) for pattern in BULK_DATA_PATTERNS)
