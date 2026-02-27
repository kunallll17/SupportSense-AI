from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    google_api_key: str
    elasticsearch_url: str
    elastic_api_key: str

    # Gemini models
    embedding_model: str = "gemini-embedding-001"   # only embedContent-capable model
    llm_model: str = "gemini-2.5-flash"              # best available reasoning model

    # Elasticsearch
    index_name: str = "support_tickets"
    embedding_dims: int = 3072              # gemini-embedding-001 output dimension

    class Config:
        env_file = ".env"


settings = Settings()
