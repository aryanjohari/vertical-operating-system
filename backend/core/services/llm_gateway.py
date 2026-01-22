import logging
import os
from typing import Optional

from google import genai
from google.genai import types


class LLMGateway:
    """
    Centralized LLM gateway for all model calls.

    Responsibilities:
    - Single place to initialize the genai client with API key
    - Enforce default model selection (Gemini 1.5 Pro)
    - Provide lightweight retry handling and logging
    - Future hooks: cost tracking and rate limiting
    """

    def __init__(self):
        self.logger = logging.getLogger("Apex.LLMGateway")
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is not set.")

        self.client = genai.Client(api_key=api_key)
        self.default_model = os.getenv("APEX_LLM_MODEL", "gemini-2.5-flash")

    def generate_content(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.6,
        max_retries: int = 3,
    ) -> str:
        """
        Generate content with centralized retries and logging.
        """
        target_model = model or self.default_model
        last_error = None

        for attempt in range(1, max_retries + 1):
            try:
                self.logger.info(
                    f"LLM request attempt {attempt}/{max_retries} | model={target_model}"
                )

                response = self.client.models.generate_content(
                    model=target_model,
                    contents=user_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        temperature=temperature,
                    ),
                )

                text = (response.text or "").strip()
                if not text:
                    raise ValueError("Empty LLM response text.")

                # Hook: cost tracking / token logging can be added here
                return text

            except Exception as e:
                last_error = e
                self.logger.warning(
                    f"LLM attempt {attempt} failed: {e}", exc_info=True
                )

        # Exhausted retries
        raise RuntimeError(
            f"LLM generation failed after {max_retries} attempts: {last_error}"
        )

    def generate_embeddings(
        self,
        texts: list[str],
        model: str = "text-embedding-004",
        max_retries: int = 3,
    ) -> list[list[float]]:
        """
        Generate embeddings using Google's embedding API.
        
        Args:
            texts: List of text strings to embed
            model: Embedding model to use (default: text-embedding-004)
            max_retries: Maximum number of retry attempts
            
        Returns:
            List of embedding vectors (list of floats)
        """
        if not texts:
            return []
        
        last_error = None
        
        for attempt in range(1, max_retries + 1):
            try:
                self.logger.debug(
                    f"Embedding request attempt {attempt}/{max_retries} | model={model} | texts={len(texts)}"
                )
                
                response = self.client.models.embed_content(
                    model=model,
                    contents=texts
                )
                
                embeddings = [e.values for e in response.embeddings]
                
                if not embeddings or len(embeddings) != len(texts):
                    raise ValueError(f"Embedding count mismatch: expected {len(texts)}, got {len(embeddings)}")
                
                return embeddings
                
            except Exception as e:
                last_error = e
                self.logger.warning(
                    f"Embedding attempt {attempt} failed: {e}", exc_info=True
                )
        
        # Exhausted retries
        raise RuntimeError(
            f"Embedding generation failed after {max_retries} attempts: {last_error}"
        )


# Singleton instance
llm_gateway = LLMGateway()
