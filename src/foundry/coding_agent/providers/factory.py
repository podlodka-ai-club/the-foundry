from __future__ import annotations

from typing import TYPE_CHECKING

from .anthropic import AnthropicProvider
from .base import BaseLLMProvider
from .chatgpt import ChatGPTProvider
from .deepseek import DeepSeekProvider

if TYPE_CHECKING:
    from ...config import Settings


class LLMProviderFactory:
    """Создание LLM-провайдера из централизованных Settings."""

    _providers: dict[str, type[BaseLLMProvider]] = {
        "DEEPSEEK": DeepSeekProvider,
        "ANTHROPIC": AnthropicProvider,
        "CHATGPT": ChatGPTProvider,
    }

    @classmethod
    def create_provider(
        cls,
        llm_type: str,
        api_key: str,
        model_name: str | None = None,
    ) -> BaseLLMProvider:
        provider_class = cls._providers.get(llm_type.upper())
        if provider_class is None:
            supported = ", ".join(cls._providers)
            raise ValueError(
                f"Unsupported LLM type: {llm_type}. Supported: {supported}"
            )
        return provider_class(api_key=api_key, model_name=model_name)

    @classmethod
    def create_from_settings(cls, settings: "Settings") -> BaseLLMProvider:
        api_key_map = {
            "DEEPSEEK": settings.deepseek_api_key,
            "ANTHROPIC": settings.anthropic_api_key,
            "CHATGPT": settings.openai_api_key,
        }
        model_map = {
            "DEEPSEEK": settings.deepseek_model_name,
            "ANTHROPIC": settings.anthropic_model_name,
            "CHATGPT": settings.chatgpt_model_name,
        }
        llm_type = settings.coding_llm
        api_key = api_key_map.get(llm_type)
        if not api_key:
            raise ValueError(f"API key for {llm_type} is missing in Settings")
        return cls.create_provider(llm_type, api_key, model_map.get(llm_type))

    @classmethod
    def register_provider(
        cls, llm_type: str, provider_class: type[BaseLLMProvider]
    ) -> None:
        if not issubclass(provider_class, BaseLLMProvider):
            raise TypeError(
                f"{provider_class.__name__} must subclass BaseLLMProvider"
            )
        cls._providers[llm_type.upper()] = provider_class

    @classmethod
    def get_supported_providers(cls) -> list[str]:
        return list(cls._providers)
