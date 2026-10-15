class AgentException(Exception):
    pass

class AgentInitializationException(AgentException):
    pass

class AgentMemoryException(AgentException):
    pass

class ModelUnavailableException(AgentException):
    pass

class ModelResponseParseException(AgentException):
    pass

class PromptException(AgentException):
    pass
