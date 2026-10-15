from typing import Optional
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from app.config.setting import mariadb_param
from app.clients.base import BaseClient


class MariaDBClient(BaseClient):
    _instance: Optional['MariaDBClient'] = None

    def __init__(self):
        super().__init__()
        self._engine: Optional[Engine] = None
        self._session_factory: Optional[sessionmaker] = None

    @classmethod
    def get_instance(cls) -> 'MariaDBClient':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def connect(self) -> None:
        if not self._engine:
            connection_url = (
                f"mysql+mysqlconnector://{mariadb_param.mariadb_user}:{mariadb_param.mariadb_passwd}"
                f"@{mariadb_param.mariadb_host}:{mariadb_param.mariadb_port}"
                f"/{mariadb_param.mariadb_database}"
            )
            self._engine = create_engine(
                connection_url, pool_size=30, max_overflow=10,
                pool_timeout=30, pool_recycle=3600, pool_pre_ping=True
            )
            self._session_factory = sessionmaker(bind=self._engine)
            self._client = self._session_factory()

    def close(self) -> None:
        if self._client:
            self._client.close()
            self._client = None
        if self._engine:
            self._engine.dispose()
            self._engine = None

    def is_connected(self) -> bool:
        return self._client is not None and self._engine is not None and not self._client.is_active

    @property
    def session(self) -> Session:
        return self.client
