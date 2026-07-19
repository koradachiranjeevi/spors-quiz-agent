import json
from loguru import logger
import chromadb
from openai import OpenAI
from src import config

# Cache OpenAI client and SentenceTransformer model
_openai_client = None
_local_embedding_model = None

def get_openai_client():
    """Returns a singleton OpenAI client."""
    global _openai_client
    if _openai_client is None:
        if not config.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is not set in environment.")
        _openai_client = OpenAI(api_key=config.OPENAI_API_KEY)
    return _openai_client

def get_openai_embedding(text: str) -> list[float]:
    """Generates embeddings using OpenAI text-embedding-3-small."""
    client = get_openai_client()
    response = client.embeddings.create(
        input=[text],
        model="text-embedding-3-small"
    )
    return response.data[0].embedding

def get_local_embedding(text: str) -> list[float]:
    """Generates embeddings locally using sentence-transformers (all-MiniLM-L6-v2) as a fallback."""
    global _local_embedding_model
    if _local_embedding_model is None:
        logger.info("Loading sentence-transformers all-MiniLM-L6-v2 model locally...")
        from sentence_transformers import SentenceTransformer
        _local_embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    
    embeddings = _local_embedding_model.encode([text])
    return embeddings[0].tolist()

def get_embedding(text: str) -> list[float]:
    """Unified embedding getter. Tries OpenAI first if configured, else falls back to local sentence-transformers."""
    provider = config.EMBEDDING_PROVIDER
    
    # Try OpenAI if configured
    if provider == "openai":
        try:
            return get_openai_embedding(text)
        except Exception as e:
            logger.warning(f"OpenAI embedding generation failed, falling back to local model: {e}")
            # Switch provider to local for this session
            config.EMBEDDING_PROVIDER = "local"
    
    # Fallback/Default to local embedding
    try:
        return get_local_embedding(text)
    except Exception as e:
        logger.error(f"Local embedding generation failed: {e}")
        raise RuntimeError("No embedding provider is available. Set a valid OPENAI_API_KEY or install sentence-transformers.") from e

def initialize_database():
    """Initializes and returns a persistent ChromaDB client."""
    db_path = config.get_db_path()
    logger.info(f"Initializing persistent ChromaDB client at '{db_path}'...")
    try:
        client = chromadb.PersistentClient(path=db_path)
        return client
    except Exception as e:
        logger.critical(f"ChromaDB initialization failed: {e}")
        raise e

def populate_database(client, force_repopulate: bool = False):
    """
    Seeds ChromaDB with facts from sports_facts.json. 
    Avoids duplicate entries unless force_repopulate is True.
    """
    facts_path = config.get_data_facts_path()
    logger.info(f"Starting ChromaDB population check from '{facts_path}'...")
    
    try:
        with open(facts_path, "r", encoding="utf-8") as f:
            facts_data = json.load(f)
            
        collection = client.get_or_create_collection(name="sports_facts")
        
        existing_count = collection.count()
        if existing_count > 0 and not force_repopulate:
            logger.info(f"Database already contains {existing_count} records. Skipping population.")
            return collection
            
        if force_repopulate and existing_count > 0:
            logger.info("Force repopulation requested. Deleting existing 'sports_facts' collection...")
            client.delete_collection(name="sports_facts")
            collection = client.get_or_create_collection(name="sports_facts")
            
        ids = []
        documents = []
        embeddings = []
        metadatas = []
        
        counter = 0
        for sport, facts in facts_data.items():
            logger.debug(f"Processing {len(facts)} facts for sport: '{sport}'")
            for item in facts:
                fact_text = item["fact"]
                raw_metadata = item.get("metadata", {})
                
                # Convert list values to strings, as ChromaDB doesn't support lists in metadata values
                cleaned_metadata = {}
                for k, v in raw_metadata.items():
                    if isinstance(v, list):
                        cleaned_metadata[k] = ", ".join(v) if v else "None"
                    else:
                        cleaned_metadata[k] = v
                cleaned_metadata["sport"] = sport # enforce correct sport label
                
                doc_id = f"{sport.lower().replace(' ', '_')}_{counter}"
                
                # Compute embedding
                embedding = get_embedding(fact_text)
                
                ids.append(doc_id)
                documents.append(fact_text)
                embeddings.append(embedding)
                metadatas.append(cleaned_metadata)
                counter += 1
                
        if documents:
            logger.info(f"Adding {len(documents)} records to 'sports_facts' collection...")
            collection.add(
                ids=ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas
            )
            logger.info("ChromaDB population completed successfully.")
        return collection
        
    except Exception as e:
        logger.error(f"Failed to populate database: {e}")
        raise e

def semantic_search(client, query: str, sport: str, limit: int = 5) -> list[dict]:
    """
    Performs semantic vector search on ChromaDB, filtered by sport.
    Returns a list of matching records with similarity distance score.
    """
    logger.info(f"Searching database for '{sport}' query: '{query}'")
    try:
        collection = client.get_or_create_collection(name="sports_facts")
        
        # If collection is empty, try populating first
        if collection.count() == 0:
            logger.warning("Vector collection is empty. Populating before search...")
            populate_database(client)
            
        query_emb = get_embedding(query)
        
        # Apply metadata filter by sport
        where_filter = {"sport": sport}
        
        results = collection.query(
            query_embeddings=[query_emb],
            n_results=limit,
            where=where_filter
        )
        
        formatted = []
        if results and "documents" in results and results["documents"]:
            docs = results["documents"][0]
            metas = results["metadatas"][0] if "metadatas" in results else [{}] * len(docs)
            distances = results["distances"][0] if "distances" in results else [0.0] * len(docs)
            
            for doc, meta, dist in zip(docs, metas, distances):
                formatted.append({
                    "text": doc,
                    "metadata": meta,
                    "distance": dist
                })
                
        logger.info(f"Found {len(formatted)} matching facts in database.")
        return formatted
        
    except Exception as e:
        logger.error(f"Semantic search failed: {e}")
        # Graceful degradation - return empty list instead of crashing
        return []
