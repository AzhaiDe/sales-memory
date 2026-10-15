import os
from typing import Dict, Type

from autogen_core.models import ChatCompletionClient
from autogen_ext.models.openai import OpenAIChatCompletionClient
from transformers import AutoTokenizer

from app.config.setting import private_gpt_param, model_param_dict, base_dir
from app.models.model_config import ModelClientConfig, PrivateGPTConfig


class ModelClientConfigFactory:
    _instances: Dict[str, ModelClientConfig] = {}

    @classmethod
    def create_config(cls, config_name: str) -> ModelClientConfig:
        config = model_param_dict.get(config_name, None)
        if config is None:
            raise ValueError(f"不支持的模型客户端配置类型: {config_name}")
        return PrivateGPTConfig(api_key=config.api_key, api_base=config.api_base, model_name=config.model_name)

    @classmethod
    def get_config(cls, config_name: str = None) -> ModelClientConfig:
        if config_name is None:
            config_name = private_gpt_param.model_name
        if config_name in cls._instances:
            return cls._instances[config_name]
        config = cls.create_config(config_name)
        cls._instances[config_name] = config
        return config


class ModelClientFactory:
    _instances: Dict[str, ChatCompletionClient] = {}
    _tokenizer_instances: Dict[str, any] = {}
    _client_types: Dict[str, Type[ChatCompletionClient]] = {"openai": OpenAIChatCompletionClient}

    @classmethod
    def create_client(cls, config: ModelClientConfig) -> ChatCompletionClient:
        model_params = config.get_model_params()
        client_class = cls._client_types["openai"]
        return client_class(**model_params)

    @classmethod
    def get_client(cls, config: ModelClientConfig) -> ChatCompletionClient:
        model_name = config.get_model_name()
        if model_name in cls._instances:
            return cls._instances[model_name]
        client = cls.create_client(config)
        cls._instances[model_name] = client
        return client

    @classmethod
    def get_default_client(cls) -> ChatCompletionClient:
        config = PrivateGPTConfig(model_name=private_gpt_param.model_name,
                                  api_base=private_gpt_param.api_base, api_key=private_gpt_param.api_key)
        return cls.get_client(config)

    @classmethod
    def get_tokenizer(cls, config: ModelClientConfig) -> AutoTokenizer:
        model_name = config.get_model_name()
        if model_name in cls._tokenizer_instances:
            return cls._tokenizer_instances[model_name]
        os.environ['HF_HUB_OFFLINE'] = "1"
        cache_dir = os.path.join(base_dir, "resources", 'huggingface_cache')
        tokenizer = AutoTokenizer.from_pretrained(model_name, cache_dir=cache_dir)
        cls._tokenizer_instances[model_name] = tokenizer
        return tokenizer

    @classmethod
    def clear_cache(cls) -> None:
        cls._instances.clear()

    @classmethod
    def get_client_by_name(cls, model_name: str = None) -> ChatCompletionClient:
        if model_name is None:
            return cls.get_default_client()
        if model_name in cls._instances:
            return cls._instances[model_name]
        config = ModelClientConfigFactory.get_config(model_name)
        return cls.get_client(config)
