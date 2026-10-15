import uuid

from app.config import settings

base_dir = settings.BASE_DIR


class LogParam:
    def __init__(self):
        self.path = settings.LOG.PATH
        self.level = settings.LOG.LEVEL
        self.max_size = settings.LOG.MAX_SIZE
        self.keep_days = settings.LOG.KEEP_DAYS
        self.compress = settings.LOG.COMPRESS
        self.rotation = settings.LOG.ROTATION
        self.mod = settings.LOG.MOD
        self.autogen_logging = settings.LOG.AUTOGEN_LOGGING


class ServerParam:
    def __init__(self):
        self.host = settings.SERVER.get("HOST", "0.0.0.0")
        self.port = settings.SERVER.get("PORT", 8686)
        self.workers = settings.SERVER.get("workers", 1)


class ConsulParam:
    def __init__(self):
        self.consul_host = settings.CONSUL.HOST
        self.consul_port = settings.CONSUL.PORT
        self.consul_type = settings.CONSUL.TYPE
        self.consul_config_enabled = settings.CONSUL.CONFIG.ENABLED
        self.consul_config_prefix = settings.CONSUL.CONFIG.PREFIX
        self.consul_config_default_context = settings.CONSUL.CONFIG.DEFAULT_CONTEXT
        self.consul_config_register_timeout = settings.CONSUL.CONFIG.REGISTER_TIMEOUT
        self.consul_config_check_timeout = settings.CONSUL.CONFIG.CHECK_TIMEOUT
        self.consul_discovery_register = settings.CONSUL.DISCOVERY.REGISTER
        self.consul_discovery_instance_id = settings.CONSUL.DISCOVERY.INSTANCE_ID or str(uuid.uuid4())
        self.consul_discovery_service_name = settings.CONSUL.DISCOVERY.SERVICE_NAME
        self.consul_discovery_ip_address = settings.CONSUL.DISCOVERY.IP_ADDRESS
        self.consul_enable_service_name = settings.CONSUL.DISCOVERY.ENABLE_SERVICE_NAME


class PrivateGPTParam:
    def __init__(self):
        self.name = settings.PRIVATE_GPT.NAME
        self.api_base = settings.PRIVATE_GPT.API_BASE
        self.api_key = settings.PRIVATE_GPT.API_KEY
        self.model_name = settings.PRIVATE_GPT.MODEL_NAME


class QwQ32BGPTParam:
    def __init__(self):
        self.name = settings.ACTIVATE_GPT.NAME
        self.api_base = settings.ACTIVATE_GPT.API_BASE
        self.api_key = settings.ACTIVATE_GPT.API_KEY
        self.model_name = settings.ACTIVATE_GPT.MODEL_NAME


class MariadbParam:
    def __init__(self):
        self.mariadb_host = settings.MARIADB.HOST
        self.mariadb_port = settings.MARIADB.PORT
        self.mariadb_user = settings.MARIADB.USERNAME
        self.mariadb_passwd = settings.MARIADB.PASSWORD
        self.mariadb_database = settings.MARIADB.DATABASE


class RedisParam:
    def __init__(self):
        self.redis_host = settings.REDIS.HOST
        self.redis_port = settings.REDIS.PORT
        self.redis_db = settings.REDIS.DB
        self.redis_username = settings.REDIS.USERNAME
        self.redis_passwd = settings.REDIS.PASSWORD


class MilvusParam:
    def __init__(self):
        self.milvus_host = settings.MILVUS.HOST
        self.milvus_port = settings.MILVUS.PORT
        self.milvus_user = settings.MILVUS.USER
        self.milvus_password = settings.MILVUS.PASSWORD
        self.milvus_database = settings.MILVUS.DATABASE
        self.milvus_collection_prefix = settings.MILVUS.COLLECTION_PREFIX
        self.milvus_pool_size = settings.MILVUS.POOL_SIZE


class GrpcClientParam:
    def __init__(self):
        self.sales_embedding_service_name = settings.GRPC_CLIENT.SALES_EMBEDDING
        self.sales_rag_service_name = settings.GRPC_CLIENT.SALES_RAG


class ScheduleParam:
    def __init__(self):
        self.schedule_enable = settings.SCHEDULE.ENABLE
        self.delete_expired_memory_trigger = settings.SCHEDULE.DELETE_EXPIRED_MEMORY.TRIGGER
        self.delete_expired_memory_param = settings.SCHEDULE.DELETE_EXPIRED_MEMORY.PARAM


class TestParam:
    def __init__(self):
        self.test_enable = settings.TEST.ENABLE
        self.test_output_file = settings.TEST.OUTPUT_FILE


consul_param = ConsulParam()
server_param = ServerParam()
log_param = LogParam()
mariadb_param = MariadbParam()
redis_param = RedisParam()
milvus_param = MilvusParam()
grpc_client_param = GrpcClientParam()
schedule_param = ScheduleParam()
test_param = TestParam()

private_gpt_param = PrivateGPTParam()
qwq32b_gpt_params = QwQ32BGPTParam()

model_param_list = [private_gpt_param, qwq32b_gpt_params]
model_param_dict = {param.name: param for param in model_param_list}
