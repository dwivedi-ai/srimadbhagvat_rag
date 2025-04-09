import os
import logging
import chromadb
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
import google.generativeai as genai

# --- Environment & Logging Setup ---
load_dotenv()
log = logging.getLogger(__name__)

# --- Config ---
VECTOR_DB_PATH = os.getenv('VECTOR_DB_PATH', 'vector_db')
COLLECTION_NAME = os.getenv('COLLECTION_NAME', "prabhupada_purports")
EMBEDDING_MODEL_NAME = os.getenv('EMBEDDING_MODEL_NAME', 'all-MiniLM-L6-v2')
GENERATION_MODEL_NAME = os.getenv('GENERATION_MODEL_NAME', 'gemini-1.5-flash')
N_RESULTS = int(os.getenv('N_RESULTS', 5))
API_KEY = os.getenv("GEMINI_API_KEY")

# --- Global State ---
embedding_model = None
chroma_collection = None
generation_model = None
IS_INITIALIZED = False

# --- Initialization ---
try:
    if not API_KEY:
        raise ValueError("Missing GEMINI_API_KEY")

    genai.configure(api_key=API_KEY)
    embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)

    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', VECTOR_DB_PATH))
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Vector DB path not found: {db_path}")

    chroma_client = chromadb.PersistentClient(path=db_path)
    chroma_collection = chroma_client.get_collection(name=COLLECTION_NAME)

    generation_model = genai.GenerativeModel(GENERATION_MODEL_NAME)
    IS_INITIALIZED = True

except Exception as e:
    log.exception(f"Initialization failed: {e}")

# --- Prompt Builder ---
def build_prompt(question: str, context_chunks: list[dict]) -> str | None:
    if not context_chunks:
        return None

    refs = set()
    context = []
    for i, chunk in enumerate(context_chunks):
        doc = chunk.get('document', '')
        ref = chunk.get('metadata', {}).get('reference', 'Unknown Reference')
        refs.add(ref)
        context.append(f"Context Chunk {i+1} (Reference: {ref}):\n{doc}")

    joined_context = "\n\n".join(context)
    ref_list = ', '.join(sorted(refs))

    return f"""You are a helpful assistant answering questions based *only* on the provided context derived from Srila Prabhupada's purports on the Srimad Bhagavatam.

User Question: {question}

Context from Srimad Bhagavatam Purports:
--- Start of Context ---
{joined_context}
--- End of Context ---

Instructions:
1. Use only the context above to answer the question.
2. Do not add any external information.
3. Cite specific verse references from: {ref_list}.
4. If the context doesn't address the question, say: "The Srimad Bhagavatam purports queried do not specifically address that question."
5. Be concise, factual, and neutral.

Answer:"""

# --- RAG Pipeline ---
def get_rag_response(question: str) -> str:
    log.info(f"RAG question: {question}")

    if not IS_INITIALIZED:
        return "Error: The chatbot components failed to initialize. Please try again later."

    try:
        query_vec = embedding_model.encode(question).tolist()
        results = chroma_collection.query(
            query_embeddings=[query_vec],
            n_results=N_RESULTS,
            include=['documents', 'metadatas']
        )
    except Exception as e:
        log.exception(f"Retrieval error: {e}")
        return "Error: Could not retrieve information from the knowledge base."

    context_chunks = []
    if results and results.get('ids', [[]])[0]:
        for id_, doc, meta in zip(results['ids'][0], results['documents'][0], results['metadatas'][0]):
            context_chunks.append({'id': id_, 'document': doc, 'metadata': meta})
    else:
        return "The Srimad Bhagavatam purports queried do not specifically address that question."

    prompt = build_prompt(question, context_chunks)
    if not prompt:
        return "The Srimad Bhagavatam purports queried do not specifically address that question."

    try:
        response = generation_model.generate_content(prompt)
        if response.parts:
            return response.text.strip()
        if response.prompt_feedback:
            return f"Error: Response blocked ({response.prompt_feedback}). Try rephrasing."
        return "Error: Received an empty response from the language model."
    except Exception as e:
        log.exception(f"LLM generation error: {e}")
        return "Error: Failed to generate an answer from the language model."
