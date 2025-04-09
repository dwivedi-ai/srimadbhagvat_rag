# scripts/index_to_pinecone.py

import json
import os
import logging
import uuid
from sentence_transformers import SentenceTransformer
from tqdm import tqdm
from dotenv import load_dotenv
from pinecone import Pinecone, PodSpec # Or ServerlessSpec if using serverless index

# --- Configuration ---
load_dotenv() # Load variables from .env file

RAW_DATA_FILE = '../../data/raw/raw_data.jsonl'
# VECTOR_DB_PATH = '../../vector_db' # No longer needed
PINECONE_INDEX_NAME = os.getenv('COLLECTION_NAME', "prabhupada-purports") # Use same env var or new one
PINECONE_API_KEY = os.getenv('PINECONE_API_KEY')
PINECONE_ENVIRONMENT = os.getenv('PINECONE_HOST') # Or PINECONE_HOST
EMBEDDING_MODEL_NAME = os.getenv('EMBEDDING_MODEL_NAME', 'all-MiniLM-L6-v2')
CHUNK_SEPARATOR = "\n\n"
EMBEDDING_DIMENSION = 384 # For 'all-MiniLM-L6-v2'

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Data Loading & Processing Functions (Keep your existing functions) ---
def load_data(filepath):
    # ... (same as your original code)
    records = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    records.append(json.loads(line.strip()))
                except json.JSONDecodeError as e:
                    logging.warning(f"Invalid JSON line skipped: {e}")
    except FileNotFoundError:
        logging.error(f"Data file not found: {filepath}")
        return None
    logging.info(f"Loaded {len(records)} records")
    return records

def deduplicate_records(records):
    # ... (same as your original code)
    seen_references = set()
    deduplicated = []
    dup_count = 0
    for record in records:
        ref = record.get('reference')
        if ref:
            if record.get('page_type') == 'Verse Page':
                if ref not in seen_references:
                    seen_references.add(ref)
                    deduplicated.append(record)
                else:
                    dup_count += 1
            else:
                 # Keep non-verse pages if needed, or filter them earlier
                deduplicated.append(record)
        else:
            logging.warning(f"Missing reference: {record.get('url', 'N/A')}")
            deduplicated.append(record) # Decide if you want to keep records without refs
    if dup_count:
        logging.info(f"Removed {dup_count} duplicate verse pages")
    logging.info(f"{len(deduplicated)} records after deduplication")
    return deduplicated


def filter_records_with_purports(records):
     # ... (same as your original code)
    filtered = [
        r for r in records
        if r.get('page_type') == 'Verse Page' and
           r.get('explanation_text') and
           r['explanation_text'].strip().lower() != 'purport'
    ]
    logging.info(f"{len(filtered)} records with purports")
    return filtered

def chunk_purport(record):
    # ... (same as your original code, but prepare metadata carefully)
    purport = record.get('explanation_text', '')
    ref = record.get('reference', 'Unknown Reference')
    if purport.lower().startswith('purport\n'):
        purport = purport[len('purport\n'):].strip()

    chunks = purport.split(CHUNK_SEPARATOR)
    chunk_data = []
    for i, chunk_text in enumerate(chunks):
        chunk_text = chunk_text.strip()
        if chunk_text:
            # **Pinecone Metadata Notes:**
            # - Values should generally be strings, numbers, booleans, or lists of strings.
            # - Avoid deeply nested dictionaries if possible (especially older pod types).
            # - Very long strings (like full original_purport) might exceed limits or slow queries.
            #   Consider storing only essential lookup info.
            metadata_for_pinecone = {
                'reference': ref,
                'canto': str(record.get('canto', '')), # Ensure string
                'chapter': str(record.get('chapter', '')), # Ensure string
                'verse': str(record.get('verse', '')), # Ensure string
                'url': record.get('url', ''),
                'text_chunk': chunk_text # Store the chunk text itself in metadata for easy retrieval
                # 'original_purport': purport # Maybe omit or truncate if too long
            }
            chunk_data.append({
                'id': f"{ref}_chunk_{i}", # Unique ID for each chunk
                'text': chunk_text,       # Text to be embedded
                'metadata': metadata_for_pinecone
            })
    return chunk_data

def main():
    logging.info("Starting indexing to Pinecone")

    if not PINECONE_API_KEY or not (PINECONE_ENVIRONMENT): # Add PINECONE_HOST check if needed
        logging.error("Pinecone API Key/Environment not configured in .env file.")
        return

    # --- Load and Process Data ---
    all_records = load_data(RAW_DATA_FILE)
    if all_records is None: return
    deduplicated = deduplicate_records(all_records)
    filtered = filter_records_with_purports(deduplicated)
    if not filtered:
        logging.warning("No purports found")
        return

    all_chunks_data = []
    logging.info("Chunking purports...")
    for record in tqdm(filtered, desc="Chunking"):
        all_chunks_data.extend(chunk_purport(record))

    if not all_chunks_data:
        logging.warning("No valid chunks")
        return

    logging.info(f"{len(all_chunks_data)} chunks generated")

    # --- Initialize Embedding Model ---
    logging.info(f"Loading embedding model: {EMBEDDING_MODEL_NAME}")
    model = SentenceTransformer(EMBEDDING_MODEL_NAME)

    # --- Initialize Pinecone ---
    logging.info(f"Initializing Pinecone connection to index '{PINECONE_INDEX_NAME}'...")
    try:
        pc = Pinecone(api_key=PINECONE_API_KEY) # Environment may be implicitly handled or use host
        # Check if index exists, create if necessary (optional, safer to create via UI first)
        # if PINECONE_INDEX_NAME not in pc.list_indexes().names:
        #     logging.info(f"Creating Pinecone index '{PINECONE_INDEX_NAME}'...")
        #     pc.create_index(
        #         name=PINECONE_INDEX_NAME,
        #         dimension=EMBEDDING_DIMENSION,
        #         metric="cosine",
        #         spec=PodSpec(environment=PINECONE_ENVIRONMENT, pod_type="p1.x1") # Adjust pod_type/spec as needed
        #         # For serverless: spec=ServerlessSpec(cloud='aws', region='us-west-2')
        #     )
        #     logging.info("Index created. Waiting for initialization...")
        #     import time
        #     while not pc.describe_index(PINECONE_INDEX_NAME).status['ready']:
        #         time.sleep(1)

        index = pc.Index(PINECONE_INDEX_NAME) # Use host=... if required by client version
        logging.info("Pinecone connection successful.")
        index.describe_index_stats() # Print stats before upserting

    except Exception as e:
        logging.error(f"Pinecone initialization failed: {e}")
        return

    # --- Embed and Upload in Batches ---
    batch_size = 100 # Pinecone recommends batches of 100 or fewer for upsert
    logging.info(f"Embedding and uploading chunks in batches of {batch_size}")

    for i in tqdm(range(0, len(all_chunks_data), batch_size), desc="Embedding/Uploading"):
        batch_chunks = all_chunks_data[i:i+batch_size]

        ids = [c['id'] for c in batch_chunks]
        texts_to_embed = [c['text'] for c in batch_chunks]
        metadatas = [c['metadata'] for c in batch_chunks]

        # Generate embeddings
        try:
            embeds = model.encode(texts_to_embed).tolist()
        except Exception as e:
            logging.error(f"Failed to embed batch starting at index {i}: {e}")
            continue # Skip this batch

        # Prepare vectors for upsert (list of tuples or vector objects)
        vectors_to_upsert = list(zip(ids, embeds, metadatas))
        # Alternatively, as objects:
        # vectors_to_upsert = [Vector(id=id, values=emb, metadata=meta) for id, emb, meta in zip(ids, embeds, metadatas)]

        # Upsert batch to Pinecone
        try:
            index.upsert(vectors=vectors_to_upsert)
        except Exception as e:
            logging.error(f"Pinecone upsert failed for batch starting at index {i}: {e}")
            # Consider adding retry logic here if needed

    logging.info("Finished uploading.")
    final_stats = index.describe_index_stats()
    logging.info(f"Pinecone index '{PINECONE_INDEX_NAME}' now has {final_stats.total_vector_count} vectors.")
    logging.info("Indexing complete")

if __name__ == "__main__":
    main()