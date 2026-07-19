import time
from loguru import logger
from src import database, search, llm, prompts, parser

def generate_quiz_rag(
    sport: str,
    difficulty: str,
    db_client,
    provider: str = None,
    api_key: str = None,
    base_url: str = None,
    model: str = None
) -> dict:
    """
    Orchestrates the Retrieval-Augmented Generation (RAG) pipeline:
    1. Retrieve historical facts from ChromaDB using semantic search.
    2. Retrieve latest news snippets from DuckDuckGo search.
    3. Merge contexts and build LLM prompts.
    4. Call the LLM (Llama 3.1 or chosen provider) to generate the quiz.
    5. Parse and validate the response against Pydantic models.
    6. Return unified result dict containing status, context, and quiz or errors.
    """
    start_time = time.time()
    logger.info(f"Starting RAG Quiz Pipeline | Sport: '{sport}' | Difficulty: '{difficulty}'")
    
    # 1. Retrieve Historical Facts
    historical_facts = []
    try:
        search_query = f"{sport} history championships gold medals tournaments records"
        historical_facts = database.semantic_search(db_client, search_query, sport, limit=6)
    except Exception as e:
        logger.error(f"Error retrieving historical context: {e}")
        
    # 2. Retrieve Live News
    live_news = []
    try:
        live_news = search.search_live_news(sport, max_results=5)
    except Exception as e:
        logger.error(f"Error retrieving live news context: {e}")
        
    # Format context strings for the LLM prompt
    hist_contexts = []
    for idx, fact in enumerate(historical_facts, 1):
        meta = fact.get("metadata", {})
        hist_contexts.append(f"Fact {idx}: {fact.get('text', '')} (Topic: {meta.get('topic', 'General')}, Year: {meta.get('year', 'N/A')})")
    
    hist_context_str = "\n".join(hist_contexts) if hist_contexts else "No historical facts found."
    
    live_contexts = []
    for idx, news in enumerate(live_news, 1):
        live_contexts.append(f"News {idx}: {news.get('title', '')} - {news.get('snippet', '')} (Link: {news.get('link', '')})")
        
    live_context_str = "\n".join(live_contexts) if live_contexts else "No live news search results available."
    
    # 3. Assemble Prompts
    system_prompt = prompts.SYSTEM_PROMPT
    user_prompt = prompts.USER_PROMPT_TEMPLATE.format(
        sport=sport,
        difficulty=difficulty.lower(),
        historical_context=hist_context_str,
        live_context=live_context_str
    )
    
    # 4. Invoke LLM with Retry Logic (max 2 attempts)
    max_attempts = 2
    for attempt in range(1, max_attempts + 1):
        try:
            logger.info(f"LLM Generation Attempt {attempt}/{max_attempts}...")
            raw_response = llm.generate_quiz_response(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                provider=provider,
                api_key=api_key,
                base_url=base_url,
                model=model
            )
            
            # 5. Parse and Validate
            quiz_model, error_model = parser.parse_and_validate_quiz(raw_response)
            
            elapsed = time.time() - start_time
            
            if error_model:
                logger.warning(f"RAG execution terminated: Insufficient context. Time: {elapsed:.2f}s")
                return {
                    "status": "insufficient_context",
                    "error_message": error_model.error,
                    "historical_context": historical_facts,
                    "live_context": live_news,
                    "elapsed_time": elapsed
                }
                
            if quiz_model:
                logger.info(f"RAG Quiz generation succeeded in {elapsed:.2f}s.")
                return {
                    "status": "success",
                    "quiz": quiz_model.model_dump(),
                    "historical_context": historical_facts,
                    "live_context": live_news,
                    "elapsed_time": elapsed
                }
                
        except Exception as e:
            logger.warning(f"LLM generation/parsing attempt {attempt} failed: {e}")
            if attempt == max_attempts:
                elapsed = time.time() - start_time
                logger.error("All LLM generation/parsing attempts failed.")
                return {
                    "status": "error",
                    "error_message": f"Failed to generate a valid quiz after {max_attempts} attempts. Error details: {e}",
                    "historical_context": historical_facts,
                    "live_context": live_news,
                    "elapsed_time": elapsed
                }
            # Short sleep before retrying
            time.sleep(1)
            
    # Fallback return in case loop completes without returning (should not happen)
    elapsed = time.time() - start_time
    return {
        "status": "error",
        "error_message": "Unexpected error in RAG generator pipeline loop.",
        "historical_context": historical_facts,
        "live_context": live_news,
        "elapsed_time": elapsed
    }
