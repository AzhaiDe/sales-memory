from typing import Dict, List, Any
from pydantic import constr, BaseModel


class FinalResult(BaseModel):
    error_msg: str = ""
    status_code: int = 0


class MemoryAgent(BaseModel):
    tenant_id: constr(min_length=3, strip_whitespace=True)
    contact_id: constr(strip_whitespace=True)
    account_id: constr(strip_whitespace=True)
    type: str = ""


class AddMemoryAgent(MemoryAgent):
    contexts: List[Any]
    context: str = ""
    fact: List[Dict[str, Any]] = {}
    old_memory: List[Any] = []
    new_memory: List[Any] = []


class AddMemoryResult(FinalResult):
    memory: List[Any] = []


class SearchMemoryResult(FinalResult):
    memory: List[Any] = []
