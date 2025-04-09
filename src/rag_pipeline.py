# src/rag_pipeline_pinecone.py

import os
import logging
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
import google.generativeai as genai
from pinecone import Pinecone

# --- Environment & Logging Setup ---
load_dotenv()
log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


# --- Config ---
PINECONE_INDEX_NAME = os.getenv('COLLECTION_NAME', "prabhupada-purports") # Use same env var or new one
PINECONE_API_KEY = os.getenv('PINECONE_API_KEY')
PINECONE_ENVIRONMENT = os.getenv('PINECONE_ENVIRONMENT') # Or PINECONE_HOST
EMBEDDING_MODEL_NAME = os.getenv('EMBEDDING_MODEL_NAME', 'all-MiniLM-L6-v2')
GENERATION_MODEL_NAME = os.getenv('GENERATION_MODEL_NAME', 'gemini-1.5-flash')
N_RESULTS = int(os.getenv('N_RESULTS', 5))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


# --- Global State / Initialization ---
embedding_model = None
pinecone_index = None
generation_model = None
IS_INITIALIZED = False

try:
    if not GEMINI_API_KEY:
        raise ValueError("Missing GEMINI_API_KEY")
    if not PINECONE_API_KEY or not (PINECONE_ENVIRONMENT): # Add PINECONE_HOST check if needed
         raise ValueError("Missing Pinecone configuration (API Key/Environment)")

    log.info("Initializing components...")
    # 1. Generative AI Model
    genai.configure(api_key=GEMINI_API_KEY)
    generation_model = genai.GenerativeModel(GENERATION_MODEL_NAME)
    log.info(f"Generation model ({GENERATION_MODEL_NAME}) loaded.")

    # 2. Embedding Model
    embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    log.info(f"Embedding model ({EMBEDDING_MODEL_NAME}) loaded.")

    # 3. Pinecone Index
    pc = Pinecone(api_key=PINECONE_API_KEY) # Env/Host might be implicit
    # Use host=... if required: pc.Index(PINECONE_INDEX_NAME, host=pc.describe_index(PINECONE_INDEX_NAME).host)
    pinecone_index = pc.Index(PINECONE_INDEX_NAME)
    log.info(f"Connected to Pinecone index '{PINECONE_INDEX_NAME}'.")
    pinecone_index.describe_index_stats() # Verify connection

    IS_INITIALIZED = True
    log.info("Initialization complete.")

except Exception as e:
    log.exception(f"Initialization failed: {e}") # Use log.exception to include traceback


# --- Prompt Builder (Adapt context extraction) ---
def build_prompt(question: str, context_chunks: list[dict]) -> str | None:
    """Builds the prompt for the LLM using retrieved context."""
    if not context_chunks:
        return None # Or return a default prompt asking LLM to state no context found

    refs = set()
    context_str_parts = []
    for i, chunk_match in enumerate(context_chunks):
        # Extract metadata and the text chunk itself
        metadata = chunk_match.get('metadata', {})
        doc_text = metadata.get('text_chunk', '') # Get text from metadata where we stored it
        ref = metadata.get('reference', 'Unknown Reference')

        if doc_text: # Only include if text exists
            refs.add(ref)
            context_str_parts.append(f"Context Chunk {i+1} (Reference: {ref}):\n{doc_text}")

    if not context_str_parts:
        log.warning("No valid text found in context chunks metadata.")
        return None

    joined_context = "\n\n".join(context_str_parts)
    ref_list = ', '.join(sorted(list(refs))) # Convert set to list before sorting

    # --- Your Original Prompt Template ---
    return f"""You are a helpful assistant answering questions based *only* on the provided context derived from Srila Prabhupada's purports on the Srimad Bhagavatam.

User Question: {question}

Context from Srimad Bhagavatam Purports:
--- Start of Context ---
{joined_context}
--- End of Context ---

Instructions:
1. Use only the context above to answer the question.
2. Do not add any external information or your own knowledge.
3. Cite specific verse references found in the context chunks used, like this: (Reference: SB C.Ch.V). Use the references listed here: {ref_list}.
4. If the context doesn't contain the answer to the question, state clearly: "Based on the provided Srimad Bhagavatam purport excerpts, the answer to your question was not found." Do not guess or infer.
5. Be concise, factual, and neutral in tone.

Answer:"""


# --- RAG Pipeline ---
def get_rag_response(question: str) -> str:
    """Handles the RAG process: embed query, search Pinecone, build prompt, call LLM."""
    log.info(f"RAG question received: '{question}'")

    if not IS_INITIALIZED:
        log.error("RAG pipeline is not initialized.")
        return "Error: The chatbot components failed to initialize. Please contact support or try again later."

    # 1. Embed the query
    try:
        query_vec = embedding_model.encode(question).tolist()
        log.info(f"Query embedded successfully.")
    except Exception as e:
        log.exception(f"Failed to embed query: {e}")
        return "Error: Could not process the query embedding."

    # 2. Query Pinecone
    try:
        results = pinecone_index.query(
            vector=query_vec,
            top_k=N_RESULTS,
            include_metadata=True # Essential to get our stored text and refs
        )
        log.info(f"Pinecone query returned {len(results.get('matches', []))} results.")
    except Exception as e:
        log.exception(f"Pinecone retrieval error: {e}")
        return "Error: Could not retrieve information from the knowledge base due to a database error."

    # 3. Process Results and Build Prompt
    context_chunks = results.get('matches', [])
    if not context_chunks:
        log.warning("No relevant context found in Pinecone for the query.")
        # Return the specific "not found" message directly, as the LLM won't have context.
        return "Based on the provided Srimad Bhagavatam purport excerpts, the answer to your question was not found."

    # Extract relevant info for the prompt builder
    # The build_prompt function now expects the structure from Pinecone results
    prompt = build_prompt(question, context_chunks)

    if not prompt:
        log.error("Failed to build prompt from retrieved context.")
        # This might happen if context_chunks exist but don't contain 'text_chunk' metadata
        return "Error: Could not construct a valid prompt from the retrieved context."


    # 4. Call the LLM
    try:
        log.info("Generating response with LLM...")
        response = generation_model.generate_content(prompt)

        # Handle potential safety blocks or empty responses
        if response.parts:
            answer = response.text.strip()
            log.info(f"LLM generated answer successfully.")
            return answer
        elif response.prompt_feedback and response.prompt_feedback.block_reason:
             block_reason = response.prompt_feedback.block_reason
             log.warning(f"LLM response blocked due to: {block_reason}")
             return f"Error: The response generation was blocked (Reason: {block_reason}). Please try rephrasing your question."
        else:
             log.warning("LLM returned an empty response.")
             return "Error: Received an empty or unexpected response from the language model."

    except Exception as e:
        log.exception(f"LLM generation error: {e}")
        return "Error: Failed to generate an answer from the language model."