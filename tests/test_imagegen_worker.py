"""
AdsGen 2.0 - ImageGen Worker Tests
Tests for image generation functionality
"""

import pytest
from unittest.mock import MagicMock, patch


class TestGenerateVacancyImage:
    """Tests for generate_vacancy_image task."""
    
    @patch('services.imagegen_worker.tasks.sync_engine')
    @patch('services.imagegen_worker.tasks.Session')
    def test_generate_image_success(
        self, mock_session_class, mock_engine, mock_vacancy, mock_comfyui_response
    ):
        """Test successful image generation."""
        from services.imagegen_worker.tasks import generate_vacancy_image
        
        # Setup session mock
        mock_session = MagicMock()
        mock_session_class.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_class.return_value.__exit__ = MagicMock(return_value=False)
        mock_session.get.return_value = mock_vacancy
        
        # Mock ComfyUI and translation
        with patch('services.imagegen_worker.tasks._call_comfyui') as mock_comfy:
            mock_comfy.return_value = "https://disk.yandex.ru/test.jpg"
            
            with patch('services.imagegen_worker.tasks._translate_to_english') as mock_translate:
                mock_translate.return_value = "Cashier"
                
                with patch('services.validation_worker.tasks.validate_vacancy_content'):
                    result = generate_vacancy_image(mock_vacancy.id)
        
        assert result["status"] == "success"
        assert "image_url" in result
    
    @patch('services.imagegen_worker.tasks.sync_engine')
    @patch('services.imagegen_worker.tasks.Session')
    def test_generate_image_fallback(self, mock_session_class, mock_engine, mock_vacancy):
        """Test fallback image when ComfyUI fails."""
        from services.imagegen_worker.tasks import generate_vacancy_image, FALLBACK_IMAGE
        
        mock_session = MagicMock()
        mock_session_class.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_class.return_value.__exit__ = MagicMock(return_value=False)
        mock_session.get.return_value = mock_vacancy
        
        with patch('services.imagegen_worker.tasks._call_comfyui') as mock_comfy:
            mock_comfy.return_value = None  # ComfyUI fails
            
            with patch('services.imagegen_worker.tasks._translate_to_english', return_value="Cashier"):
                with patch('services.validation_worker.tasks.validate_vacancy_content'):
                    result = generate_vacancy_image(mock_vacancy.id)
        
        assert mock_vacancy.image_url == FALLBACK_IMAGE
    
    @patch('services.imagegen_worker.tasks.sync_engine')
    @patch('services.imagegen_worker.tasks.Session')
    def test_vacancy_not_found(self, mock_session_class, mock_engine):
        """Test handling when vacancy doesn't exist."""
        from services.imagegen_worker.tasks import generate_vacancy_image
        
        mock_session = MagicMock()
        mock_session_class.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_class.return_value.__exit__ = MagicMock(return_value=False)
        mock_session.get.return_value = None
        
        result = generate_vacancy_image("NON-EXISTENT-ID")
        
        assert "error" in result


class TestComfyUIIntegration:
    """Tests for ComfyUI API integration."""
    
    @patch('services.imagegen_worker.tasks.settings')
    @patch('httpx.Client')
    def test_comfyui_call_success(self, mock_httpx, mock_settings, mock_comfyui_response):
        """Test successful ComfyUI API call."""
        from services.imagegen_worker.tasks import _call_comfyui
        
        mock_settings.comfyui_url = "http://localhost:8188"
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_comfyui_response
        mock_httpx.return_value.__enter__.return_value.post.return_value = mock_response
        
        result = _call_comfyui("Cashier", "man", 30, "notes")
        
        assert result == "https://disk.yandex.ru/i/test_image.jpg"
    
    @patch('services.imagegen_worker.tasks.settings')
    def test_comfyui_not_configured(self, mock_settings):
        """Test handling when ComfyUI is not configured."""
        from services.imagegen_worker.tasks import _call_comfyui
        
        mock_settings.comfyui_url = ""
        
        result = _call_comfyui("Cashier", "man", 30)
        
        assert result is None


class TestTranslation:
    """Tests for translation functionality."""
    
    @patch('services.imagegen_worker.tasks.settings')
    @patch('httpx.Client')
    def test_translation_success(
        self, mock_httpx, mock_settings, mock_deepseek_translation_response
    ):
        """Test successful Russian to English translation."""
        from services.imagegen_worker.tasks import _translate_to_english
        
        mock_settings.deepseek_api_key = "test_key"
        mock_settings.deepseek_api_url = "https://api.test.com"
        mock_settings.deepseek_model = "test-model"
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_deepseek_translation_response
        mock_httpx.return_value.__enter__.return_value.post.return_value = mock_response
        
        result = _translate_to_english("Кассир")
        
        assert result == "Cashier"
    
    @patch('services.imagegen_worker.tasks.settings')
    def test_translation_without_api_key(self, mock_settings):
        """Test fallback when API key is missing."""
        from services.imagegen_worker.tasks import _translate_to_english
        
        mock_settings.deepseek_api_key = ""
        
        result = _translate_to_english("Кассир")
        
        # Should return original text as fallback
        assert result == "Кассир"
    
    def test_translation_empty_text(self):
        """Test handling of empty text."""
        from services.imagegen_worker.tasks import _translate_to_english
        
        with patch('services.imagegen_worker.tasks.settings') as mock_settings:
            mock_settings.deepseek_api_key = "test_key"
            
            result = _translate_to_english("")
            
            assert result == ""
