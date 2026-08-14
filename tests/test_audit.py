"""Offline unit tests for the JSONL audit trail."""

from __future__ import annotations

import json

from src.utils.audit import AuditTrail


class TestAuditTrail:
    def test_writes_jsonl(self, tmp_path) -> None:
        trail = AuditTrail(directory=str(tmp_path))
        trail.record({"event": "agent_request", "question": "VPN 登录失败怎么办"})
        trail.record({"event": "agent_response", "route": "kb"})

        files = list(tmp_path.glob("*.jsonl"))
        assert len(files) == 1
        lines = files[0].read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2
        first = json.loads(lines[0])
        assert first["event"] == "agent_request"
        assert first["question"] == "VPN 登录失败怎么办"
        assert "ts" in first

    def test_append_same_day_single_file(self, tmp_path) -> None:
        trail = AuditTrail(directory=str(tmp_path))
        trail.record({"event": "a"})
        trail.record({"event": "b"})
        files = list(tmp_path.glob("*.jsonl"))
        assert len(files) == 1
        assert len(files[0].read_text(encoding="utf-8").strip().splitlines()) == 2
