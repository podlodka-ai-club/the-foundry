import pytest
import tempfile
from pathlib import Path

from agent.core import TaskManager, LogManager


class TestTaskManager:
    """Тесты для TaskManager."""
    
    def test_validate_task_id_valid(self):
        """Тест валидации корректного номера задачи."""
        manager = TaskManager()
        assert manager.validate_task_id('TF-1') is True
        assert manager.validate_task_id('AI-123') is True
        assert manager.validate_task_id('TEST') is True
    
    def test_validate_task_id_invalid(self):
        """Тест валидации некорректного номера задачи."""
        manager = TaskManager()
        assert manager.validate_task_id('') is False
        assert manager.validate_task_id('TF 1') is False
        assert manager.validate_task_id('TF@1') is False
    
    def test_get_task_file_path(self):
        """Тест получения пути к файлу задачи."""
        manager = TaskManager(tasks_dir='test_tasks')
        path = manager.get_task_file_path('TF-1')
        assert 'test_tasks' in str(path)
        assert 'TF-1' in str(path)
        assert path.name == 'TF-1_task.md'
    
    def test_get_log_file_path(self):
        """Тест получения пути к лог-файлу."""
        manager = TaskManager(tasks_dir='test_tasks')
        path = manager.get_log_file_path('TF-1')
        assert 'test_tasks' in str(path)
        assert 'TF-1' in str(path)
        assert path.name == 'TF-1_log.md'
    
    def test_load_or_create_task_new_with_prompt(self):
        """Тест создания новой задачи с промптом."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = TaskManager(tasks_dir=tmpdir)
            task_text, task_file = manager.load_or_create_task('TEST-1', 'Test prompt')
            
            assert task_text == 'Test prompt'
            assert task_file.exists()
            assert task_file.read_text(encoding='utf-8') == 'Test prompt'
    
    def test_load_or_create_task_existing_with_prompt(self):
        """Тест добавления промпта к существующей задаче."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = TaskManager(tasks_dir=tmpdir)
            
            task_file = manager.get_task_file_path('TEST-1')
            task_file.parent.mkdir(parents=True, exist_ok=True)
            task_file.write_text('Existing content', encoding='utf-8')
            
            task_text, _ = manager.load_or_create_task('TEST-1', 'New prompt')
            
            assert 'Existing content' in task_text
            assert 'New prompt' in task_text
    
    def test_load_or_create_task_existing_without_prompt(self):
        """Тест загрузки существующей задачи без промпта."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = TaskManager(tasks_dir=tmpdir)
            
            task_file = manager.get_task_file_path('TEST-1')
            task_file.parent.mkdir(parents=True, exist_ok=True)
            task_file.write_text('Task content', encoding='utf-8')
            
            task_text, _ = manager.load_or_create_task('TEST-1', None)
            
            assert task_text == 'Task content'
    
    def test_load_or_create_task_not_found(self):
        """Тест загрузки несуществующей задачи без промпта."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = TaskManager(tasks_dir=tmpdir)
            
            with pytest.raises(FileNotFoundError):
                manager.load_or_create_task('TEST-1', None)


class TestLogManager:
    """Тесты для LogManager."""
    
    def test_save_log_success(self):
        """Тест сохранения лога успешного выполнения."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / 'test_log.md'
            manager = LogManager()
            
            result = manager.save_log(
                log_file,
                'TEST-1',
                'Test task',
                'Aider output',
                success=True,
                renamed_files=None
            )
            
            assert result.exists()
            content = result.read_text(encoding='utf-8')
            assert 'TEST-1' in content
            assert 'Test task' in content
            assert 'Aider output' in content
            assert 'Успешно выполнено' in content
    
    def test_save_log_failure(self):
        """Тест сохранения лога неуспешного выполнения."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / 'test_log.md'
            manager = LogManager()
            
            result = manager.save_log(
                log_file,
                'TEST-1',
                'Test task',
                'Error output',
                success=False,
                renamed_files=None
            )
            
            assert result.exists()
            content = result.read_text(encoding='utf-8')
            assert 'Ошибка выполнения' in content
    
    def test_save_log_with_renamed_files(self):
        """Тест сохранения лога с информацией о переименованных файлах."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / 'test_log.md'
            manager = LogManager()
            
            renamed_files = [
                ("Let's do it.test.py", "test.py"),
                ("old_name.py", "new_name.py")
            ]
            
            result = manager.save_log(
                log_file,
                'TEST-1',
                'Test task',
                'Aider output',
                success=True,
                renamed_files=renamed_files
            )
            
            content = result.read_text(encoding='utf-8')
            assert 'Пост-обработка' in content
            assert 'test.py' in content
            assert 'new_name.py' in content
    
    def test_format_post_process_info(self):
        """Тест форматирования информации о пост-обработке."""
        manager = LogManager()
        
        renamed_files = [
            ("old1.py", "new1.py"),
            ("old2.py", "new2.py")
        ]
        
        info = manager.format_post_process_info(renamed_files)
        
        assert 'Пост-обработка' in info
        assert 'old1.py -> new1.py' in info
        assert 'old2.py -> new2.py' in info
    
    def test_format_post_process_info_empty(self):
        """Тест форматирования пустой информации о пост-обработке."""
        manager = LogManager()
        info = manager.format_post_process_info([])
        assert info == ""
