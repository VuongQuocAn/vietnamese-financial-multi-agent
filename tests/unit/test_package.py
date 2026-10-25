"""Kiểm tra package đã cài mà không cần dịch vụ, secrets hoặc dữ liệu tài chính."""

from importlib import import_module
from importlib.metadata import metadata

import pytest


@pytest.mark.parametrize(
    "module_name",
    [
        "vietnamese_financial_multi_agent",
        "vietnamese_financial_multi_agent.core",
        "vietnamese_financial_multi_agent.document_processing",
        "vietnamese_financial_multi_agent.accounting",
        "vietnamese_financial_multi_agent.evidence",
        "vietnamese_financial_multi_agent.tools",
        "vietnamese_financial_multi_agent.agents",
        "vietnamese_financial_multi_agent.verification",
        "vietnamese_financial_multi_agent.outputs",
        "vietnamese_financial_multi_agent.api",
    ],
)
def test_installed_package_imports(module_name: str) -> None:
    """Phát hiện module bị bỏ sót hoặc ánh xạ sai khi đóng gói."""
    module = import_module(module_name)
    assert module.__file__ is not None


def test_installed_distribution_metadata() -> None:
    """Kiểm tra metadata của distribution sau khi cài môi trường."""
    project_metadata = metadata("vietnamese-financial-multi-agent")
    assert project_metadata["Name"] == "vietnamese-financial-multi-agent"
    assert project_metadata["Requires-Python"] == ">=3.11"
