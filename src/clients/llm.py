from llama_index.llms.openai import OpenAI
from llama_index.core import Settings as LlamaSettings
from llama_index.core.base.llms.types import LLMMetadata
from src.core.settings import settings


class CustomOpenAI(OpenAI):
   
    @property
    def metadata(self) -> LLMMetadata:
        return LLMMetadata(
            is_chat_model=True,
            is_function_calling_model=True,
            model_name=self.model,
        )


class LLMClient:
    def __init__(self):
        self.llm = CustomOpenAI(
            model="grok-4-fast-non-reasoning",
            api_key=settings.xai_api_key,
            api_base="https://api.x.ai/v1",
            temperature=0.1,
        )
        LlamaSettings.llm = self.llm
    
    def get_llm(self) -> OpenAI:
        return self.llm

