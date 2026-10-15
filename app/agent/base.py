from functools import lru_cache, wraps
from time import time
from typing import Callable, Any, TypeVar, cast

from autogen_core import RoutedAgent, DefaultTopicId, MessageContext
from autogen_core.models import ChatCompletionClient, CreateResult, UserMessage
from redis import Redis
from sqlalchemy.orm import Session

from app.clients.factory import ClientFactory
from app.config.logger_setup import logger
from app.exceptions.custom import AgentException, PromptException, ModelUnavailableException
from app.exceptions.error_codes import ErrorCode
from app.grpc.proto.internal.salesmemory_pb2 import AddMemoryRequest, SearchMemoryRequest
from app.models.prompt_manager import PromptManager
from app.schemas.body import AddMemoryAgent, AddMemoryResult

T = TypeVar('T')


class BaseAgent(RoutedAgent):
    def __init__(self, description: str):
        super().__init__(description)
        self._milvus_client = None

    def get_prompt(self, tenant_id: str, prompt_name: str, synopsis: dict = {}) -> str:
        try:
            prompt_manager = self._get_prompt_manager(tenant_id)
            prompt = prompt_manager.load_prompt(prompt_name, synopsis)
        except Exception as e:
            logger.error(f"Failed to load prompt: {e}")
            raise PromptException(message="Failed to load prompt")
        return prompt

    @staticmethod
    def get_mariadb_client() -> Session:
        return ClientFactory.get_mariadb_client()

    @staticmethod
    def get_redis_client() -> Redis:
        return ClientFactory.get_redis_client()

    async def get_milvus_client(self):
        if self._milvus_client is None:
            self._milvus_client = await ClientFactory.get_milvus_client()
        return self

    @staticmethod
    @lru_cache(maxsize=10)
    def _get_prompt_manager(tenant_id: str) -> PromptManager:
        return PromptManager(tenant_id)

    @staticmethod
    def trace_performance(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(self: 'BaseAgent', *args: Any, **kwargs: Any) -> Any:
            start_time = time()
            message = None
            for arg in args:
                if isinstance(arg, AddMemoryRequest) or isinstance(arg, AddMemoryAgent) \
                        or isinstance(arg, SearchMemoryRequest):
                    message = arg
                    break
            result = await func(self, *args, **kwargs)
            if message:
                end_time = time()
                agent_name = self.__class__.__name__
                logger.info(f"[PERF_METRICS][AGENT_DURATION] "
                            f"agent={agent_name}  "
                            f"tenant_id={message.tenant_id} "
                            f"account_id={message.account_id} "
                            f"contact_id={message.contact_id} "
                            f"duration={end_time - start_time:.2f}s")
            return result
        return cast(Callable[..., T], wrapper)

    @staticmethod
    def handle_exceptions(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(self: 'BaseAgent', *args: Any, **kwargs: Any) -> Any:
            try:
                return await func(self, *args, **kwargs)
            except AgentException as e:
                logger.exception(f"Agent exception: {e}")
                error_result = AddMemoryResult(error_msg=f"[{e.error_code.code}] {e.message}",
                                               status_code=e.error_code.code)
                await self.publish_message(error_result, DefaultTopicId())
            except Exception as e:
                logger.exception(f"Unknown exception: {e}")
                error_result = AddMemoryResult(error_msg=str(e),
                                               status_code=ErrorCode.UNKNOWN_ERROR.code)
                await self.publish_message(error_result, DefaultTopicId())
        return cast(Callable[..., T], wrapper)

    async def create(self, model: ChatCompletionClient, prompt: str, ctx: MessageContext, json_output=None) -> CreateResult:
        try:
            start_time = time()
            llm_result = await model.create(
                messages=[UserMessage(content=prompt, source=self.id.key)],
                cancellation_token=ctx.cancellation_token, json_output=json_output
            )
            end_time = time()
            logger.info(f"[PERF_METRICS][PROMPT_DURATION] duration={end_time - start_time:.2f}s")
        except Exception as e:
            raise ModelUnavailableException(message="Failed to create llm result")
        return llm_result
