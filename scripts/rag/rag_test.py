import chromadb
import logging
import os
from sentence_transformers import SentenceTransformer
import google.generativeai as genai
from dotenv import load_dotenv

VECTOR_DB_PATH = '../../vector_db'
COLLECTION_NAME = "prabhupada_purports"
EMBEDDING_MODEL_NAME = 'all-MiniLM-L6-v2'
N_RESULTS = 5
GENERATION_MODEL_NAME = 'gemini-1.5-flash'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    logging.error("GEMINI_API_KEY not set.")
    exit()

genai.configure(api_key=API_KEY)

def build_prompt(question, context_chunks):
    if not context_chunks:
        return None

    context_string = ""
    references = set()
    for i, chunk in enumerate(context_chunks):
        doc = chunk.get('document', '')
        ref = chunk.get('metadata', {}).get('reference', 'Unknown Reference')
        context_string += f"Chunk {i+1} (Ref: {ref}):\n{doc}\n\n"
        references.add(ref)

    prompt = f"""You are a chatbot answering only based on the context from Srila Prabhupada's purports.

Question: {question}

--- Context Start ---
{context_string}
--- Context End ---

Instructions:
1. Answer strictly using the context above.
2. Cite reference(s) (e.g., SB 1.2.3).
3. If no answer is possible, say so.
4. Be concise and coherent.

Refs: {', '.join(sorted(references))}

Answer:"""
    return prompt

def main():
    logging.info("Starting RAG test...")

    try:
        client = chromadb.PersistentClient(path=VECTOR_DB_PATH)
        collection = client.get_collection(name=COLLECTION_NAME)
        logging.info(f"Accessed collection with {collection.count()} items.")
    except Exception as e:
        logging.error(f"ChromaDB error: {e}")
        return

    try:
        embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        logging.info("Embedding model loaded.")
    except Exception as e:
        logging.error(f"Model load error: {e}")
        return

    try:
        generation_model = genai.GenerativeModel(GENERATION_MODEL_NAME)
        logging.info("Generation model initialized.")
    except Exception as e:
        logging.error(f"LLM init error: {e}")
        return

    sample_questions = [
        "What are the qualities of a devotee?",
        "What is the nature of the soul?",
        "Why should one chant the Hare Krishna mantra?",
        "Tell me about Lord Krishna's appearance.",
        "What is the process of creation described in Srimad Bhagavatam Canto 1?",
        "Does Srimad Bhagavatam mention airplanes?",
    ]

    for question in sample_questions:
        print(f"\n===== '{question}' =====")

        try:
            query_embedding = embedding_model.encode(question).tolist()
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=N_RESULTS,
                include=['documents', 'metadatas']
            )

            context_chunks = []
            if results and results.get('ids', [[]])[0]:
                ids = results['ids'][0]
                docs = results['documents'][0]
                metadatas = results['metadatas'][0]
                for id_val, doc, meta in zip(ids, docs, metadatas):
                    context_chunks.append({'id': id_val, 'document': doc, 'metadata': meta})
        except Exception as e:
            logging.error(f"Retrieval error: {e}")
            continue

        prompt = build_prompt(question, context_chunks)
        if prompt is None:
            print("LLM Answer: Context not found.")
            continue

        print("\n--- Prompt (truncated) ---")
        print(prompt[:300] + "...")
        print("---")

        try:
            response = generation_model.generate_content(prompt)
            print("\n--- LLM Answer ---")
            if response.parts:
                print(response.text)
            elif response.prompt_feedback:
                print(f"Blocked: {response.prompt_feedback}")
            else:
                print("Empty response.")
        except Exception as e:
            logging.error(f"LLM generation error: {e}")
            print("LLM Answer: Generation error.")

    logging.info("RAG test finished.")

if __name__ == "__main__":
    main()
