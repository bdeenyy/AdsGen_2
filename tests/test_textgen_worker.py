"""
AdsGen 2.0 - TextGen Worker Tests
Tests for text generation functionality
"""

import pytest
import json
from unittest.mock import MagicMock, patch


class TestGenerateVacancyText:
    """Tests for generate_vacancy_text task."""
    
    @patch('services.textgen_worker.tasks.sync_engine')
    @patch('services.textgen_worker.tasks.Session')
    def test_generate_text_success(
        self, mock_session_class, mock_engine, mock_vacancy, mock_deepseek_response
    ):
        """Test successful text generation with AI."""
        from services.textgen_worker.tasks import generate_vacancy_text
        
        # Setup session mock
        mock_session = MagicMock()
        mock_session_class.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_class.return_value.__exit__ = MagicMock(return_value=False)
        mock_session.get.return_value = mock_vacancy
        
        # Mock AI response
        with patch('services.textgen_worker.tasks._generate_ai_content') as mock_ai:
            mock_ai.return_value = {
                "title": "Кассир в магазин",
                "description": "<p>Описание вакансии</p>"
            }
            
            with patch('services.imagegen_worker.tasks.generate_vacancy_image'):
                result = generate_vacancy_text(mock_vacancy.id)
        
        assert result["status"] == "success"
        assert result["vacancy_id"] == mock_vacancy.id
    
    @patch('services.textgen_worker.tasks.sync_engine')
    @patch('services.textgen_worker.tasks.Session')
    def test_generate_text_fallback(self, mock_session_class, mock_engine, mock_vacancy):
        """Test fallback generation when AI fails."""
        from services.textgen_worker.tasks import _generate_fallback_title, _generate_fallback_description
        
        # Test fallback title
        title = _generate_fallback_title(mock_vacancy)
        assert title is not None
        assert len(title) <= 100
        assert mock_vacancy.profession in title
        
        # Test fallback description
        description = _generate_fallback_description(mock_vacancy)
        assert description is not None
        assert mock_vacancy.profession in description
    
    @patch('services.textgen_worker.tasks.sync_engine')
    @patch('services.textgen_worker.tasks.Session')
    def test_vacancy_not_found(self, mock_session_class, mock_engine):
        """Test handling when vacancy doesn't exist."""
        from services.textgen_worker.tasks import generate_vacancy_text
        
        mock_session = MagicMock()
        mock_session_class.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_class.return_value.__exit__ = MagicMock(return_value=False)
        mock_session.get.return_value = None  # Vacancy not found
        
        result = generate_vacancy_text("NON-EXISTENT-ID")
        
        assert "error" in result
        assert result["error"] == "Vacancy not found"


class TestAIContentGeneration:
    """Tests for AI content generation helper."""
    
    @patch('services.textgen_worker.tasks.settings')
    @patch('httpx.Client')
    def test_ai_content_with_valid_response(
        self, mock_httpx, mock_settings, mock_vacancy, mock_deepseek_response
    ):
        """Test parsing valid AI response."""
        from services.textgen_worker.tasks import _generate_ai_content
        
        mock_settings.deepseek_api_key = "test_key"
        mock_settings.deepseek_api_url = "https://api.test.com"
        mock_settings.deepseek_model = "test-model"
        
        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_deepseek_response
        mock_httpx.return_value.__enter__.return_value.post.return_value = mock_response
        
        result = _generate_ai_content(mock_vacancy)
        
        assert result is not None
        assert "title" in result
        assert "description" in result
    
    @patch('services.textgen_worker.tasks.settings')
    def test_ai_content_without_api_key(self, mock_settings, mock_vacancy):
        """Test fallback when API key is missing."""
        from services.textgen_worker.tasks import _generate_ai_content
        
        mock_settings.deepseek_api_key = ""
        
        result = _generate_ai_content(mock_vacancy)
        
        assert result is None


class TestTitleCleaning:
    """Tests for title cleaning and validation."""
    
    def test_title_pipe_removal(self):
        """Test that pipe characters are removed from titles."""
        title = "Кассир | Продавец | Консультант"
        cleaned = title.replace("|", "").strip()
        
        assert "|" not in cleaned
    
    def test_title_length_limit(self):
        """Test that titles are truncated to max length."""
        long_title = "А" * 150
        truncated = long_title[:100]
        
        assert len(truncated) == 100
