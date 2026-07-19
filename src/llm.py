from openai import OpenAI
from loguru import logger
from src import config

def resolve_provider_settings(provider: str, api_key: str = None, base_url: str = None, model: str = None):
    """
    Resolves the API key, base URL, and model for a given provider,
    falling back to config settings if parameters are omitted.
    """
    prov = (provider or config.LLM_PROVIDER).lower()
    
    # Defaults
    resolved_api_key = api_key
    resolved_base_url = base_url
    resolved_model = model or config.LLM_MODEL
    
    if prov == "groq":
        resolved_base_url = base_url or "https://api.groq.com/openai/v1"
        resolved_api_key = api_key or config.GROQ_API_KEY or config.LLM_API_KEY
        if not model:
            resolved_model = "llama-3.1-8b-instant"
    elif prov == "together":
        resolved_base_url = base_url or "https://api.together.xyz/v1"
        resolved_api_key = api_key or config.TOGETHER_API_KEY or config.LLM_API_KEY
        if not model:
            resolved_model = "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo"
    elif prov == "ollama":
        resolved_base_url = base_url or "http://localhost:11434/v1"
        resolved_api_key = api_key or "ollama" # Ollama does not require key
        if not model:
            resolved_model = "llama3.1"
    elif prov == "openai":
        resolved_base_url = base_url or None # None uses default OpenAI URL
        resolved_api_key = api_key or config.OPENAI_API_KEY
        if not model:
            resolved_model = "gpt-4o-mini"
    else: # custom or openai_compatible
        resolved_base_url = base_url or config.LLM_BASE_URL
        resolved_api_key = api_key or config.LLM_API_KEY
        resolved_model = model or config.LLM_MODEL
        
    return prov, resolved_api_key, resolved_base_url, resolved_model

def generate_quiz_response(
    system_prompt: str, 
    user_prompt: str, 
    provider: str = None, 
    api_key: str = None, 
    base_url: str = None, 
    model: str = None
) -> str:
    """
    Submits prompts to the resolved LLM provider.
    Returns the raw string output from the LLM.
    """
    prov, resolved_key, resolved_url, resolved_model = resolve_provider_settings(
        provider, api_key, base_url, model
    )
    
    logger.info(f"Connecting to LLM Provider: '{prov}' | Model: '{resolved_model}' | Base URL: '{resolved_url}'")
    
    if not resolved_key and prov != "ollama":
        error_msg = f"API key is missing for LLM provider '{prov}'."
        logger.error(error_msg)
        raise ValueError(error_msg)
        
    try:
        client = OpenAI(api_key=resolved_key, base_url=resolved_url)
        
        # Configure JSON mode if supported
        # Groq, OpenAI, and Together support standard response_format parameter
        extra_args = {}
        if prov in ["openai", "groq", "together"]:
            extra_args["response_format"] = {"type": "json_object"}
            
        response = client.chat.completions.create(
            model=resolved_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,  # Low temperature for high factual accuracy and JSON adherence
            max_tokens=3000,
            **extra_args
        )
        
        result_text = response.choices[0].message.content
        logger.info("Successfully received LLM response.")
        logger.debug(f"Response preview: {result_text[:150]}")
        return result_text
        
    except Exception as e:
        logger.error(f"LLM completion failed for provider '{prov}': {e}")
        raise e
