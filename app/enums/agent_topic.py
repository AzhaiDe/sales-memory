from enum import Enum


class TopicType(Enum):
    EXTRACT_FACT_AGENT = "extract_fact_agent"
    RESOLVE_CONFLICT_AGENT = "resolve_conflict_agent"
    RETRIEVE_MEMORY_AGENT = "retrieve_memory_agent"
    CLOSURE_AGENT = "closure_agent"
    ACTIVATE_MEM_AGENT = "activate_mem_agent"
    ACTIVATE_MEM_STORE = "activate_mem_store"
