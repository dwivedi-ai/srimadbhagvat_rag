import chromadb
import logging
from sentence_transformers import SentenceTransformer

VECTOR_DB_PATH = '../../vector_db'
COLLECTION_NAME = "prabhupada_purports"
EMBEDDING_MODEL_NAME = 'all-MiniLM-L6-v2'
N_RESULTS = 5

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    logging.info("Starting retrieval test...")

    try:
        client = chromadb.PersistentClient(path=VECTOR_DB_PATH)
        collection = client.get_collection(name=COLLECTION_NAME)
        logging.info(f"Connected to collection '{COLLECTION_NAME}' with {collection.count()} items.")
    except Exception as e:
        logging.error(f"ChromaDB connection error: {e}")
        return

    try:
        model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        logging.info("Embedding model loaded.")
    except Exception as e:
        logging.error(f"Embedding model load error: {e}")
        return

    sample_questions = [
        "What are the qualities of a devotee?",
        "What is the nature of the soul?",
        "Why should one chant the Hare Krishna mantra?",
        "Tell me about Lord Krishna's appearance.",
    ]

    for question in sample_questions:
        print(f"\n--- Query: '{question}' ---")

        try:
            query_embedding = model.encode(question).tolist()
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=N_RESULTS,
                include=['documents', 'metadatas', 'distances']
            )

            if results and results.get('ids', [[]])[0]:
                ids = results['ids'][0]
                docs = results['documents'][0]
                metas = results['metadatas'][0]
                dists = results['distances'][0]

                print(f"Top {len(ids)} results:")
                for i in range(len(ids)):
                    ref = metas[i].get('reference', 'N/A')
                    dist = dists[i]
                    doc = docs[i][:200].replace('\n', ' ')  # Clean chunk preview
                    print(f"  {i+1}. Ref: {ref} (Dist: {dist:.4f})")
                    print(f"     Chunk: \"{doc}...\"")
            else:
                print("  No relevant documents found.")
        except Exception as e:
            logging.error(f"Query error for '{question}': {e}")

    logging.info("Retrieval test finished.")

if __name__ == "__main__":
    main()
