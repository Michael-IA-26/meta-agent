from __future__ import annotations

import logging
from pathlib import Path

from .agent_config import AgentConfig

logger = logging.getLogger(__name__)


class AgentLoader:
    def __init__(self, base_dir: str = "."):
        self.base_dir = base_dir
        self.configs_dir = Path(base_dir) / "configs"

    def load(self, config_path: str) -> AgentConfig:
        config = AgentConfig.from_file(config_path)
        logger.info(f"Agent charge : {config.name} ({config.agent_id})")
        return config

    def load_by_id(self, agent_id: str) -> AgentConfig:
        config_path = self.configs_dir / f"{agent_id}.json"
        if not config_path.exists():
            raise FileNotFoundError(f"Config introuvable : {config_path}")
        return self.load(str(config_path))

    def list_agents(self) -> list[str]:
        if not self.configs_dir.exists():
            return []
        return [
            f.stem
            for f in self.configs_dir.glob("*.json")
            if not f.name.startswith("client_")
        ]

    def validate(self, config: AgentConfig) -> list[str]:
        errors = []
        if not config.agent_id:
            errors.append("agent_id est requis")
        if not config.name:
            errors.append("name est requis")
        if config.prompts.icp_path:
            icp_full = Path(self.base_dir) / config.prompts.icp_path
            if not icp_full.exists():
                errors.append(f"ICP introuvable : {config.prompts.icp_path}")
        for tool in config.tools:
            if not tool.name:
                errors.append("Chaque tool doit avoir un name")
        system_prompt = config.get_system_prompt(self.base_dir)
        if not system_prompt:
            errors.append("Aucun system prompt configure")
        return errors

    def save_config(self, config: AgentConfig) -> str:
        path = str(self.configs_dir / f"{config.agent_id}.json")
        config.to_file(path)
        logger.info(f"Config sauvegardee : {path}")
        return path
