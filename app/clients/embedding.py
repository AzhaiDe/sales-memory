from typing import List

from openai import OpenAI

from app.config.logger_setup import logger
from app.config.setting import embedding_param, private_gpt_param


class EmbeddingClient:
    def __init__(self):
        self._client = None

    def _get_client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(
                api_key=private_gpt_param.api_key,
                base_url=private_gpt_param.api_base,
                timeout=60,
                max_retries=1,
            )
        return self._client

    def get_embeddings(self, texts: List[str], model: str = None) -> List:
        if not texts:
            return []
        model_name = model or embedding_param.model_name
        dimensions = int(embedding_param.dimensions)
        vectors: list = [None] * len(texts)
        try:
            client = self._get_client()
            for start in range(0, len(texts), 10):
                batch = texts[start:start + 10]
                response = client.embeddings.create(
                    model=model_name,
                    input=batch,
                    dimensions=dimensions,
                    encoding_format="float",
                )
                records = sorted(response.data, key=lambda item: item.index)
                if [record.index for record in records] != list(range(len(batch))):
                    raise ValueError("Embedding response indices do not match input")
                for offset, record in enumerate(records):
                    vector = list(record.embedding)
                    if len(vector) != dimensions:
                        raise ValueError(f"Embedding dimension {len(vector)} != {dimensions}")
                    vectors[start + offset] = vector
            logger.info(f"成功获取 {len(texts)} 条文本的嵌入向量, model={model_name}")
            return vectors
        except Exception as e:
            logger.error(f"获取嵌入向量失败: {str(e)}")
            raise
