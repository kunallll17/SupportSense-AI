import os
from elasticsearch import Elasticsearch
from dotenv import load_dotenv

load_dotenv()

es = Elasticsearch(
    os.getenv("ELASTICSEARCH_URL"),
    api_key=os.getenv("ELASTIC_API_KEY"),
)

mapping = es.indices.get_mapping(index="support_tickets")
print(mapping)