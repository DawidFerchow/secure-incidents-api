from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    app_name: str = "Secure Incidents API"
    app_version: str = "1.0.0"
    log_level: str = "INFO"
    seed_records: int = 2_500
    allowed_hosts: tuple[str, ...] = ("localhost", "127.0.0.1", "testserver", "app")

    @classmethod
    def from_env(cls) -> Settings:
        requested_seed_count = int(os.getenv("SEED_RECORDS", "2500"))
        allowed_hosts = tuple(
            host.strip()
            for host in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver,app").split(",")
            if host.strip()
        )
        return cls(
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            seed_records=max(2_000, requested_seed_count),
            allowed_hosts=allowed_hosts,
        )
