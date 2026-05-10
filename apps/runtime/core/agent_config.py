from __future__ import annotations

import json
import os
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class AgentType(str, Enum):
    SIMPLE = "simple"
    ORCHESTRATOR = "orchestrator"
    PIPELINE = "pipeline"


class ToolConfig(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class PromptConfig(BaseModel):
    system: str = ""
    icp_path: str | None = None
    components: list[str] = Field(default_factory=list)

    def load_icp(self, base_dir: str = ".") -> str:
        if not self.icp_path:
            return ""
        full_path = Path(base_dir) / self.icp_path
        try:
            return full_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return ""

    def build_system_prompt(self, base_dir: str = ".") -> str:
        parts = []
        if self.system:
            parts.append(self.system)
        icp = self.load_icp(base_dir)
        if icp:
            parts.append(f"\nCONTEXTE METIER:\n{icp}")
        for component_path in self.components:
            full_path = Path(base_dir) / component_path
            try:
                parts.append(full_path.read_text(encoding="utf-8"))
            except FileNotFoundError:
                pass
        return "\n\n".join(parts)


class ScheduleConfig(BaseModel):
    enabled: bool = False
    cron: str = "0 8 * * *"
    timezone: str = "Europe/Paris"


class NotificationConfig(BaseModel):
    email: str | None = None
    telegram_chat_id: str | None = None


class KPIConfig(BaseModel):
    temps_theorique_min: int = 45
    hourly_rate: float = 80.0


class AgentConfig(BaseModel):
    agent_id: str
    name: str
    description: str = ""
    version: str = "0.1.0"
    agent_type: AgentType = AgentType.SIMPLE
    model: str = "claude-sonnet-4-6"
    max_tokens: int = 1024
    tools: list[ToolConfig] = Field(default_factory=list)
    prompts: PromptConfig = Field(default_factory=PromptConfig)
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)
    notifications: NotificationConfig = Field(default_factory=NotificationConfig)
    kpis: KPIConfig = Field(default_factory=KPIConfig)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_file(cls, path: str) -> AgentConfig:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return cls(**data)

    def to_file(self, path: str) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.model_dump(), f, indent=2, ensure_ascii=False)

    def get_system_prompt(self, base_dir: str = ".") -> str:
        return self.prompts.build_system_prompt(base_dir)


def email_agent_config() -> AgentConfig:
    return AgentConfig(
        agent_id="email_agent",
        name="Email Agent",
        description="Analyse les emails non lus et genere un rapport quotidien",
        agent_type=AgentType.SIMPLE,
        model="claude-sonnet-4-6",
        max_tokens=500,
        prompts=PromptConfig(
            system="Tu es un assistant qui analyse des emails professionnels.",
            icp_path="packages/prompts/icps/agence_conseil.md",
        ),
        schedule=ScheduleConfig(enabled=True, cron="45 8 * * *"),
        notifications=NotificationConfig(
            email="michael@myvesper.fr",
            telegram_chat_id="5505521057",
        ),
        kpis=KPIConfig(temps_theorique_min=45, hourly_rate=80.0),
    )


def leadcommercial_agent_config() -> AgentConfig:
    return AgentConfig(
        agent_id="leadcommercial_signal",
        name="LeadCommercial Signal Agent",
        description="Detecte les nouveaux leads via API Sirene et signaux intention",
        agent_type=AgentType.PIPELINE,
        model="claude-sonnet-4-6",
        max_tokens=1024,
        tools=[
            ToolConfig(name="http_call", description="Requete HTTP externe"),
            ToolConfig(name="supabase_query", description="Lecture/ecriture Supabase"),
            ToolConfig(name="telegram_notify", description="Notification Telegram"),
        ],
        prompts=PromptConfig(
            system="Tu es un agent de detection de leads B2B pour cabinets comptables.",
        ),
        schedule=ScheduleConfig(enabled=True, cron="0 7 * * *"),
        notifications=NotificationConfig(telegram_chat_id="5505521057"),
        kpis=KPIConfig(temps_theorique_min=120, hourly_rate=100.0),
        metadata={
            "client": "JM Partners",
            "zone": "Ile-de-France",
            "signaux": ["creation", "rattrapage", "fiscal"],
        },
    )
