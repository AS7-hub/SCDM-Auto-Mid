import json
from enum import Enum
from typing import Dict
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppMode(str, Enum):
    MOCK = "MOCK"
    DEMO = "DEMO"
    LIVE = "LIVE"


class Settings(BaseSettings):
    app_mode: AppMode = AppMode.MOCK

    # Gemini Configuration
    gemini_model: str = "gemini-3.7-flash"
    gemini_api_key: str = ""
    gemini_call_budget: int = 100

    # Neo4j Configuration
    neo4j_uri: str = "bolt://127.0.0.1:7687"
    neo4j_database: str = "neo4j"
    neo4j_username: str = "neo4j"
    neo4j_password: str = ""

    # Directories
    raw_data_dir: str = "../SCDM AUTO data/datasets btp1"
    canonical_data_dir: str = "../SCDM AUTO data/LSEG_CLEANED_OUTPUT/03_GRAPH_READY"
    cache_dir: str = "./cache"
    report_dir: str = "./reports"

    # Domain Logic Limits
    max_graph_traversal_depth: int = 3

    # These can be loaded as JSON strings from environment
    risk_thresholds: Dict[str, float] = {
        "high": 0.8, "medium": 0.5, "low": 0.2}
    risk_model_weights: Dict[str, float] = {
        "supply_chain": 0.5, "geopolitical": 0.3, "financial": 0.2}

    retrieval_limit: int = 10
    retrieval_timeout: int = 30

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_parse_none_str="null"
    )

    @classmethod
    def load(cls) -> "Settings":
        # Additional custom parsing for complex types like dict if passed as JSON string in env
        # pydantic_settings handles basic JSON dict parsing from env vars natively if configured properly.
        return cls()


# Global config instance
config = Settings.load()
