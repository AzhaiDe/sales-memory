from enum import Enum
import grpc


class ErrorCode(Enum):
    UNKNOWN_ERROR = (grpc.StatusCode.INTERNAL, "未知错误")
    INVALID_ARGUMENT = (grpc.StatusCode.INVALID_ARGUMENT, "参数无效")
    NOT_FOUND = (grpc.StatusCode.NOT_FOUND, "资源未找到")
    UNAVAILABLE = (grpc.StatusCode.UNAVAILABLE, "服务不可用")

    def __init__(self, code, message):
        self.code = code
        self.message = message
