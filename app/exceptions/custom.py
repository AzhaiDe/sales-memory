class AgentException(Exception):
    def __init__(self, message: str = "", error_code=None):
        super().__init__(message)
        from app.exceptions.error_codes import ErrorCode
        self.message = message
        self.error_code = error_code or ErrorCode.UNKNOWN_ERROR

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
