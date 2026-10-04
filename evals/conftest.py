"""
Shared pytest fixtures for the eval suite.

Fixtures
--------
recorder       Fresh TraceRecorder, wired into mock tools, reset after each test.
live_agent     Strands Agent with mock tools and real Bedrock. Skipped if no AWS creds.
"""

from __future__ import annotations

import os
import pytest

from evals.mocks.tools import TraceRecorder, set_recorder


@pytest.fixture()
def recorder() -> TraceRecorder:
    """Fresh TraceRecorder active for the duration of one test."""
    rec = TraceRecorder()
    set_recorder(rec)
    yield rec
    set_recorder(None)
    rec.reset()


@pytest.fixture(scope="session")
def _aws_available() -> bool:
    """True when AWS credentials are present in the environment."""
    return bool(
        os.environ.get("AWS_ACCESS_KEY_ID")
        or os.environ.get("AWS_PROFILE")
        or os.environ.get("AWS_DEFAULT_REGION")
        # also covers IAM role / ECS / EC2 instance metadata
        or os.path.exists(os.path.expanduser("~/.aws/credentials"))
    )


@pytest.fixture()
def live_agent(_aws_available):
    """
    Strands Agent wired to mock tools and real Bedrock LLM.
    Skipped automatically when AWS credentials are absent.
    """
    if not _aws_available:
        pytest.skip("AWS credentials not found — skipping live agent test")

    from evals.runner.agent import build_eval_agent
    return build_eval_agent()
