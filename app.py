"""Minimal Streamlit demo for the knowledge-ops-agent support flow."""

from __future__ import annotations

from typing import Any

import streamlit as st

from src.agents.main_agent import (
    _extract_ticket_id,
    _looks_like_escalation_query,
    _looks_like_ticket_query,
    run_agent,
)


st.set_page_config(page_title="knowledge-ops-agent", page_icon="KB", layout="centered")

st.title("knowledge-ops-agent")
st.caption("一个最小可用的 Agent 问答演示页：知识库问答、工单查询、升级建议。")

with st.expander("UI 手动验收 / Smoke Test", expanded=False):
    st.code("streamlit run app.py", language="bash")
    st.markdown(
        """
1. 知识库问答
   推荐输入：`VPN 登录失败提示 token 过期怎么办`
   预期表现：页面展示最终回答；证据区出现知识库命中，至少包含 `source_title` 和 `passage` 摘要；工具调用记录里出现 `search_kb`。

2. 工单查询
   推荐输入：`帮我看 TKT-1004 工单现在状态`
   预期表现：页面展示工单状态结论；证据区出现 `ticket_id`、`status`、`priority`、`owner`、`last_update` 等关键信息；工具调用记录里出现 `get_ticket_status`。

3. 升级建议
   推荐输入：`客户连续两天无法登录，是否应该升级处理`
   预期表现：页面展示升级建议结论；证据区出现升级草稿的 `severity`、`suggested_team`、`recommended_next_step`；工具调用记录里出现 `create_escalation_draft`。

补充检查
- 输入 `帮我查一下工单状态` 时，应先看到澄清问题，例如“请提供 ticket_id”。
- 输入 `帮我看 TKT-9999 工单现在状态` 时，应显示未找到工单的合理提示，而不是页面报错。
        """
    )


def _summarize_passage(text: str, limit: int = 180) -> str:
    """Return a short passage preview for UI display."""
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit].rstrip()}..."



def _find_tool_call(tool_calls: list[dict[str, Any]], tool_name: str) -> dict[str, Any] | None:
    """Return the first tool call record matching the tool name."""
    for record in tool_calls:
        if record.get("tool") == tool_name:
            return record
    return None



def _render_evidence_area(answer_data: dict[str, Any]) -> None:
    """Render evidence blocks directly from the agent's unified output."""
    st.subheader("证据")

    tool_calls = answer_data.get("tool_calls", [])
    route = answer_data.get("route", "kb")
    rendered = False

    kb_call = _find_tool_call(tool_calls, "search_kb")
    if kb_call and kb_call.get("results"):
        rendered = True
        st.caption("知识库命中")
        for item in kb_call["results"]:
            source_title = item.get("source_title", "unknown")
            passage = _summarize_passage(str(item.get("passage", "")))
            score = item.get("score")
            score_text = f"{float(score):.2f}" if isinstance(score, (int, float)) else "n/a"
            st.markdown(f"**{source_title}**  `score={score_text}`")
            st.write(passage or "无摘要")

    ticket_call = _find_tool_call(tool_calls, "get_ticket_status")
    if route == "ticket" and ticket_call:
        rendered = True
        st.caption("工单信息")
        if ticket_call.get("found") and ticket_call.get("ticket"):
            ticket = ticket_call["ticket"]
            st.json(
                {
                    "ticket_id": ticket.get("ticket_id"),
                    "status": ticket.get("status"),
                    "priority": ticket.get("priority"),
                    "owner": ticket.get("owner"),
                    "last_update": ticket.get("last_update"),
                    "category": ticket.get("category"),
                    "summary": ticket.get("summary"),
                }
            )
        else:
            st.warning(ticket_call.get("error", "未找到工单信息。"))

    escalation_call = _find_tool_call(tool_calls, "create_escalation_draft")
    if route == "escalation" and escalation_call:
        rendered = True
        draft = escalation_call.get("output", {})
        st.caption("升级建议草稿")
        st.json(
            {
                "severity": draft.get("severity"),
                "suggested_team": draft.get("suggested_team"),
                "escalation_summary": draft.get("escalation_summary"),
                "recommended_next_step": draft.get("recommended_next_step"),
            }
        )

    if not rendered:
        if answer_data.get("evidence"):
            for item in answer_data["evidence"]:
                st.write(f"- {item}")
        else:
            st.write("无")



def _render_tool_area(tool_records: list[dict[str, Any]]) -> None:
    """Render tool/debug records in a compact way."""
    st.subheader("工具调用记录")
    if not tool_records:
        st.write("本次未触发可展示的工具记录。")
        return

    for record in tool_records:
        st.markdown(f"**{record.get('tool', 'unknown')}**")
        st.json(record)


question = st.text_area(
    "请输入问题",
    placeholder="例如：VPN 登录失败提示 token 过期怎么办",
    height=120,
)

submitted = st.button("提交", type="primary")

if submitted:
    if not question.strip():
        st.error("请输入一个问题后再提交。")
    else:
        normalized_question = question.strip()
        route_debug = {
            "user_input": normalized_question,
            "is_ticket_query": _looks_like_ticket_query(normalized_question),
            "is_escalation_query": _looks_like_escalation_query(normalized_question),
            "ticket_id": _extract_ticket_id(normalized_question),
        }

        with st.spinner("Agent 正在处理..."):
            try:
                answer = run_agent(normalized_question)
            except Exception as exc:
                st.error(f"Agent 运行失败: {exc}")
                st.subheader("调试信息")
                st.json(route_debug)
            else:
                answer_data = answer.model_dump()

                st.subheader("最终回答")
                st.write(answer_data.get("answer") or answer_data.get("conclusion") or "无")

                _render_evidence_area(answer_data)

                st.subheader("下一步动作")
                next_actions = answer_data.get("next_action") or answer_data.get("next_actions") or []
                if next_actions:
                    for item in next_actions:
                        st.write(f"- {item}")
                else:
                    st.write("无")

                col1, col2, col3, col4 = st.columns(4)
                col1.metric("路由", str(answer_data.get("route", "unknown")))
                col2.metric("建议人工接管", "是" if answer_data.get("human_handoff") else "否")
                col3.metric("置信度", f"{float(answer_data.get('confidence', 0.0)):.2f}")
                col4.metric("需要澄清", "是" if answer_data.get("needs_clarification") else "否")

                if answer_data.get("clarification_question"):
                    st.subheader("澄清问题")
                    st.write(answer_data["clarification_question"])

                _render_tool_area(answer_data.get("tool_calls", []))

                st.subheader("调试信息")
                st.json({**route_debug, "answer": answer_data})
