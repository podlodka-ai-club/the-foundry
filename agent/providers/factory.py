import os
from typing import Dict

from .base import BaseLLMProvider
from .deepseek import DeepSeekProvider
from .anthropic import AnthropicProvider
from .chatgpt import ChatGPTProvider


class LLMProviderFactory:
    """
    Фабрика для создания провайдеров LLM.
    
    Реализует паттерн Factory для создания экземпляров провайдеров
    на основе конфигурации из переменных окружения.
    """
    
    _providers: Dict[str, type] = {
        'DEEPSEEK': DeepSeekProvider,
        'ANTHROPIC': AnthropicProvider,
        'CHATGPT': ChatGPTProvider,
    }
    
    @classmethod
    def create_provider(cls, llm_type: str, api_key: str) -> BaseLLMProvider:
        """
        Создание провайдера по типу LLM.
        
        Args:
            llm_type: Тип LLM (DEEPSEEK, ANTHROPIC, CHATGPT)
            api_key: API ключ для доступа к LLM
            
        Returns:
            Экземпляр провайдера
            
        Raises:
            ValueError: Если тип LLM не поддерживается
        """
        provider_class = cls._providers.get(llm_type.upper())
        
        if not provider_class:
            supported = ', '.join(cls._providers.keys())
            raise ValueError(
                f"Неподдерживаемый тип LLM: {llm_type}. "
                f"Поддерживаемые типы: {supported}"
            )
        
        return provider_class(api_key)
    
    @classmethod
    def create_from_env(cls) -> BaseLLMProvider:
        """
        Создание провайдера из переменных окружения.
        
        Читает CODING_LLM для определения типа провайдера
        и соответствующий API ключ.
        
        Returns:
            Экземпляр провайдера
            
        Raises:
            ValueError: Если API ключ не найден или тип LLM не поддерживается
        """
        llm_type = os.getenv('CODING_LLM', 'DEEPSEEK').upper()
        
        api_key_map = {
            'DEEPSEEK': 'DEEPSEEK_API_KEY',
            'ANTHROPIC': 'ANTHROPIC_API_KEY',
            'CHATGPT': 'CHATGPT_API_KEY',
        }
        
        api_key_env = api_key_map.get(llm_type)
        if not api_key_env:
            raise ValueError(f"Неподдерживаемый тип LLM: {llm_type}")
        
        api_key = os.getenv(api_key_env)
        if not api_key:
            raise ValueError(
                f"API ключ для {llm_type} не найден. "
                f"Установите переменную окружения {api_key_env}"
            )
        
        return cls.create_provider(llm_type, api_key)
    
    @classmethod
    def register_provider(cls, llm_type: str, provider_class: type):
        """
        Регистрация нового провайдера.
        
        Позволяет расширять фабрику новыми провайдерами без изменения кода.
        
        Args:
            llm_type: Тип LLM (например, 'GEMINI')
            provider_class: Класс провайдера (должен наследовать BaseLLMProvider)
        """
        if not issubclass(provider_class, BaseLLMProvider):
            raise TypeError(
                f"Класс {provider_class.__name__} должен наследовать BaseLLMProvider"
            )
        
        cls._providers[llm_type.upper()] = provider_class
    
    @classmethod
    def get_supported_providers(cls) -> list:
        """
        Получение списка поддерживаемых провайдеров.
        
        Returns:
            Список названий поддерживаемых провайдеров
        """
        return list(cls._providers.keys())
