"""Tests Runtime v0 — AgentConfig + AgentLoader"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from apps.runtime.core.agent_config import (
    AgentConfig,
    AgentType,
    PromptConfig,
    email_agent_config,
    leadcommercial_agent_config,
)
from apps.runtime.core.agent_loader import AgentLoader


def test_create_agent_config():
    config = AgentConfig(
        agent_id="test_agent",
        name="Test Agent",
        description="Un agent de test",
    )
    assert config.agent_id == "test_agent"
    assert config.agent_type == AgentType.SIMPLE
    assert config.model == "claude-sonnet-4-6"
    assert config.max_tokens == 1024
    print("OK: test_create_agent_config")


def test_email_agent_preset():
    config = email_agent_config()
    assert config.agent_id == "email_agent"
    assert config.schedule.enabled is True
    assert config.kpis.temps_theorique_min == 45
    assert config.notifications.telegram_chat_id == "5505521057"
    print("OK: test_email_agent_preset")


def test_leadcommercial_preset():
    config = leadcommercial_agent_config()
    assert config.agent_id == "leadcommercial_signal"
    assert config.agent_type == AgentType.PIPELINE
    assert len(config.tools) == 3
    assert config.metadata["client"] == "JM Partners"
    print("OK: test_leadcommercial_preset")


def test_save_and_load():
    config = email_agent_config()
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "test.json")
        config.to_file(path)
        loaded = AgentConfig.from_file(path)
        assert loaded.agent_id == config.agent_id
        assert loaded.name == config.name
        assert loaded.kpis.hourly_rate == config.kpis.hourly_rate
    print("OK: test_save_and_load")


def test_system_prompt_build():
    with tempfile.TemporaryDirectory() as tmp:
        icp_path = os.path.join(tmp, "test_icp.md")
        with open(icp_path, "w") as f:
            f.write("# ICP Test\nCabinet comptable IDF")
        config = AgentConfig(
            agent_id="test",
            name="Test",
            prompts=PromptConfig(
                system="Tu es un assistant pro.",
                icp_path="test_icp.md",
            ),
        )
        prompt = config.get_system_prompt(tmp)
        assert "assistant pro" in prompt
        assert "Cabinet comptable IDF" in prompt
    print("OK: test_system_prompt_build")


def test_loader_validate():
    loader = AgentLoader(base_dir=".")
    config = AgentConfig(
        agent_id="test",
        name="Test",
        prompts=PromptConfig(
            system="System prompt ok",
            icp_path="inexistant.md",
        ),
    )
    errors = loader.validate(config)
    assert any("ICP introuvable" in e for e in errors)
    print("OK: test_loader_validate")


def test_loader_validate_no_errors():
    loader = AgentLoader(base_dir=".")
    config = AgentConfig(
        agent_id="test",
        name="Test",
        prompts=PromptConfig(system="Un prompt valide"),
    )
    errors = loader.validate(config)
    assert len(errors) == 0
    print("OK: test_loader_validate_no_errors")


if __name__ == "__main__":
    test_create_agent_config()
    test_email_agent_preset()
    test_leadcommercial_preset()
    test_save_and_load()
    test_system_prompt_build()
    test_loader_validate()
    test_loader_validate_no_errors()
    print("\n7/7 tests passes !")
