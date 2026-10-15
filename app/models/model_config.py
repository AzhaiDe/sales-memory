from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class ModelClientConfig(ABC):
    @abstractmethod
    def get_model_name(self) -> str:
        pass

    @abstractmethod
    def get_model_params(self) -> Dict[str, Any]:
        pass


class PrivateGPTConfig(ModelClientConfig):
    def __init__(self, model_name: str, api_base: str, api_key: str, model_info: Optional[Dict[str, Any]] = None):
        self.model_name = model_name
        self.api_base = api_base
        self.api_key = api_key
        self.model_info = model_info or {
            "vision": False, "function_calling": True, "json_output": True, "family": "Default",
        }

    def get_model_name(self) -> str:
        return self.model_name

    def get_model_params(self) -> Dict[str, Any]:
        return {"model": self.model_name, "base_url": self.api_base, "api_key": self.api_key,
                "model_info": self.model_info}
