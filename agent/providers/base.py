from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Tuple


class BaseLLMProvider(ABC):
    """
    Базовый абстрактный класс для провайдеров LLM.
    
    Определяет интерфейс для работы с различными LLM провайдерами.
    Каждый провайдер должен реализовать методы для:
    - Получения настроек модели
    - Формирования команды aider
    - Пост-обработки результатов
    """
    
    def __init__(self, api_key: str):
        """
        Инициализация провайдера.
        
        Args:
            api_key: API ключ для доступа к LLM
        """
        self.api_key = api_key
    
    @abstractmethod
    def get_model_name(self) -> str:
        """
        Получение названия модели.
        
        Returns:
            Название модели для использования в aider
        """
        pass
    
    @abstractmethod
    def configure_aider_command(self, base_cmd: List[str], env: Dict[str, str]) -> Tuple[List[str], Dict[str, str]]:
        """
        Настройка команды aider для конкретного провайдера.
        
        Args:
            base_cmd: Базовая команда aider
            env: Переменные окружения
            
        Returns:
            Кортеж (настроенная_команда, обновленные_переменные_окружения)
        """
        pass
    
    @abstractmethod
    def post_process_files(self, code_dir: Path) -> List[Tuple[str, str]]:
        """
        Пост-обработка файлов после выполнения aider.
        
        Каждый провайдер может иметь свои особенности в создании файлов,
        требующие специфической обработки.
        
        Args:
            code_dir: Директория с кодом
            
        Returns:
            Список кортежей (старое_имя, новое_имя) переименованных файлов
        """
        pass
    
    def get_provider_name(self) -> str:
        """
        Получение названия провайдера.
        
        Returns:
            Название провайдера
        """
        return self.__class__.__name__.replace('Provider', '')
