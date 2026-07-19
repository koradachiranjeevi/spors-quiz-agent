import json
import re
from typing import List, Dict, Tuple, Optional
from pydantic import BaseModel, Field, field_validator
from loguru import logger

class QuestionModel(BaseModel):
    question: str = Field(..., description="The multiple choice trivia question text.")
    options: Dict[str, str] = Field(..., description="Exactly four options labeled A, B, C, D.")
    answer: str = Field(..., description="The correct option key. Must be exactly 'A', 'B', 'C', or 'D'.")
    explanation: str = Field(..., description="Detailed explanation of the correct answer grounded in context.")

    @field_validator('options')
    @classmethod
    def validate_options(cls, v: dict) -> dict:
        """Enforces that options must contain exactly keys A, B, C, and D with non-empty values."""
        required_keys = {"A", "B", "C", "D"}
        keys = set(v.keys())
        if keys != required_keys:
            raise ValueError(f"Options must contain exactly keys: {required_keys}. Got keys: {keys}")
        
        for k, val in v.items():
            if not isinstance(val, str) or not val.strip():
                raise ValueError(f"Option {k} cannot be empty.")
        return v

    @field_validator('answer')
    @classmethod
    def validate_answer(cls, v: str) -> str:
        """Ensures correct answer is uppercase and exactly A, B, C, or D."""
        ans = v.strip().upper()
        if ans not in {"A", "B", "C", "D"}:
            raise ValueError(f"Answer must be one of 'A', 'B', 'C', or 'D'. Got: '{v}'")
        return ans

    @field_validator('question', 'explanation')
    @classmethod
    def validate_non_empty_strings(cls, v: str, info) -> str:
        """Ensures text fields are not empty or whitespace only."""
        if not v.strip():
            raise ValueError(f"Field '{info.field_name}' cannot be empty.")
        return v.strip()

class QuizModel(BaseModel):
    questions: List[QuestionModel] = Field(..., description="List of generated quiz questions.")

    @field_validator('questions')
    @classmethod
    def validate_questions_count(cls, v: list) -> list:
        if len(v) != 5:
            logger.warning(f"Expected exactly 5 questions, but LLM returned {len(v)}.")
        if not v:
            raise ValueError("Questions list cannot be empty.")
        return v

class InsufficientContextModel(BaseModel):
    error: str = Field(..., description="Explanation of why the context was insufficient to generate the quiz.")

def parse_and_validate_quiz(raw_text: str) -> Tuple[Optional[QuizModel], Optional[InsufficientContextModel]]:
    """
    Cleans raw LLM outputs, extracts JSON content, parses it, and validates 
    against Pydantic schemas (QuizModel or InsufficientContextModel).
    
    Returns:
        (QuizModel, None) if quiz is successfully validated.
        (None, InsufficientContextModel) if LLM declares insufficient context.
    Raises:
        ValueError: If JSON cannot be parsed or schemas are violated.
    """
    cleaned = raw_text.strip()
    
    # 1. Remove Markdown code block syntax if present
    if cleaned.startswith("```"):
        match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", cleaned)
        if match:
            cleaned = match.group(1).strip()
            
    # 2. Extract first matching JSON block if text surrounds it
    if not (cleaned.startswith("{") and cleaned.endswith("}")):
        first_brace = cleaned.find("{")
        last_brace = cleaned.rfind("}")
        if first_brace != -1 and last_brace != -1:
            cleaned = cleaned[first_brace:last_brace + 1]
            
    # 3. Attempt JSON loading
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as je:
        logger.error(f"JSON parsing failed: {je}. Cleaned string: '{cleaned}'")
        raise ValueError(f"The LLM response is not a valid JSON structure: {je}")
        
    # 4. Handle Insufficient Context scenario
    if "error" in data:
        try:
            insufficient = InsufficientContextModel(**data)
            logger.warning(f"Model returned insufficient context report: {insufficient.error}")
            return None, insufficient
        except Exception as ve:
            logger.error(f"Failed to validate error model: {ve}")
            # fall through to validate as normal quiz
            
    # 5. Handle standard Quiz validation
    try:
        quiz = QuizModel(**data)
        logger.info(f"Successfully validated quiz containing {len(quiz.questions)} questions.")
        return quiz, None
    except Exception as ve:
        logger.error(f"Quiz model schema validation failed: {ve}. Data: {data}")
        raise ValueError(f"Quiz schema validation failed: {ve}")
