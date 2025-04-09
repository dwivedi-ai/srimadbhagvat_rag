import json
import os
import logging
import uuid
import chromadb
from sentence_transformers import SentenceTransformer
from tqdm import tqdm 

# --- Configuration ---
RAW_DATA_FILE = '../../data/raw/raw_data.jsonl'
VECTOR_DB_PATH = '../../vector_db' 
COLLECTION_NAME = "prabhupada_purports"
EMBEDDING_MODEL_NAME = 'all-MiniLM-L6-v2'
CHUNK_SEPARATOR = "\n\n"

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_data(filepath):
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
                deduplicated.append(record)
        else:
            logging.warning(f"Missing reference: {record.get('url', 'N/A')}")
            deduplicated.append(record)
    if dup_count:
        logging.info(f"Removed {dup_count} duplicates")
    logging.info(f"{len(deduplicated)} records after deduplication")
    return deduplicated

def filter_records_with_purports(records):
    filtered = [
        r for r in records
        if r.get('page_type') == 'Verse Page' and 
           r.get('explanation_text') and          
           r['explanation_text'].strip().lower() != 'purport' 
    ]
    logging.info(f"{len(filtered)} records with purports")
    return filtered

def chunk_purport(record):
    purport = record.get('explanation_text', '')
    ref = record.get('reference', 'Unknown Reference')
    if purport.lower().startswith('purport\n'):
        purport = purport[len('purport\n'):].strip()
    chunks = purport.split(CHUNK_SEPARATOR)
    chunk_data = []
    for i, chunk_text in enumerate(chunks):
        chunk_text = chunk_text.strip()
        if chunk_text: 
            chunk_data.append({
                'id': f"{ref}_chunk_{i}",
                'text': chunk_text,
                'metadata': {
                    'reference': ref,
                    'canto': record.get('canto'),
                    'chapter': record.get('chapter'),
                    'verse': record.get('verse'),
                    'url': record.get('url'),
                    'original_purport': purport 
                }
            })
    return chunk_data

def main():
    logging.info("Starting indexing")

    all_records = load_data(RAW_DATA_FILE)
    if all_records is None:
        return

    deduplicated = deduplicate_records(all_records)
    filtered = filter_records_with_purports(deduplicated)
    if not filtered:
        logging.warning("No purports found")
        return

    all_chunks = []
    logging.info("Chunking purports...")
    for record in tqdm(filtered, desc="Chunking"):
        all_chunks.extend(chunk_purport(record))

    if not all_chunks:
        logging.warning("No valid chunks")
        return

    logging.info(f"{len(all_chunks)} chunks generated")

    chunk_ids = [c['id'] for c in all_chunks]
    chunk_texts = [c['text'] for c in all_chunks]
    chunk_metadatas = [c['metadata'] for c in all_chunks]

    logging.info(f"Using model: {EMBEDDING_MODEL_NAME}")
    logging.info(f"Setting up DB at: {VECTOR_DB_PATH}")

    try:
        client = chromadb.PersistentClient(path=VECTOR_DB_PATH)
        embedding_fn = chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBEDDING_MODEL_NAME
        )
        collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=embedding_fn,
            metadata={"hnsw:space": "cosine"}
        )

        batch_size = 100
        logging.info(f"Adding chunks in batches of {batch_size}")
        for i in tqdm(range(0, len(chunk_ids), batch_size), desc="Adding to DB"):
            collection.add(
                ids=chunk_ids[i:i+batch_size],
                documents=chunk_texts[i:i+batch_size],
                metadatas=chunk_metadatas[i:i+batch_size]
            )

        logging.info(f"DB collection '{COLLECTION_NAME}' now has {collection.count()} items")
    except Exception as e:
        logging.error(f"ChromaDB error: {e}")

    logging.info("Indexing complete")


def build_vector_db():
    os.makedirs(VECTOR_DB_PATH, exist_ok=True)
    main()

if __name__ == "__main__":
    os.makedirs(VECTOR_DB_PATH, exist_ok=True) 
    main()