"""
Verify vectors exist by running a real kNN search.
If results come back, vectors are indexed and working.
"""
import os
from elasticsearch import Elasticsearch
from dotenv import load_dotenv
from google import genai

load_dotenv()

es = Elasticsearch(
    os.getenv("ELASTICSEARCH_URL"),
    api_key=os.getenv("ELASTIC_API_KEY"),
)
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

# 1. Doc count
count = es.count(index="support_tickets")["count"]
print(f"Total docs: {count}")

# 2. Check a raw doc — dense_vector is NOT in _source with bbq_hnsw (expected)
resp = es.search(index="support_tickets", size=1, query={"match_all": {}})
doc = resp["hits"]["hits"][0]["_source"]
print(f"_source fields: {sorted(doc.keys())}")
print(f"'description_vector' in _source: {'description_vector' in doc}")
print("(This is EXPECTED with ES 9.x bbq_hnsw — vectors live in the HNSW graph, not _source)")

# 3. REAL PROOF: Run a kNN search — only works if vectors are indexed
print("\n--- kNN search test ---")
result = client.models.embed_content(
    model="models/gemini-embedding-001",
    contents="login authentication failure password reset",
)
query_vector = result.embeddings[0].values
print(f"Query vector dims: {len(query_vector)}")

knn_resp = es.search(
    index="support_tickets",
    knn={
        "field": "description_vector",
        "query_vector": query_vector,
        "k": 3,
        "num_candidates": 20,
    },
    source=["title", "issue_type", "severity"],
)
hits = knn_resp["hits"]["hits"]
print(f"kNN returned {len(hits)} results (vectors ARE indexed if this is > 0):")
for h in hits:
    print(f"  [{h['_source']['severity']}] {h['_source']['title']}")