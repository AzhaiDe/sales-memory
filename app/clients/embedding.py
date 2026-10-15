from typing import List, Optional

from app.config.logger_setup import logger


class EmbeddingClient:
    _model = None

    @classmethod
    def _get_model(cls):
        if cls._model is None:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading bge-m3 embedding model (first time may take a while)...")
            cls._model = SentenceTransformer("BAAI/bge-m3")
            logger.info("Embedding model loaded")
        return cls._model

    def get_embeddings(self, texts: List[str], model: str = "bge-m3") -> List:
        try:
            m = self._get_model()
            vectors = m.encode(texts, normalize_embeddings=True)
            logger.info(f"成功获取 {len(texts)} 条文本的嵌入向量")
            return [v.tolist() for v in vectors]
        except Exception as e:
            logger.error(f"获取嵌入向量失败: {str(e)}")
            raise
