"""
AdsGen 2.0 - Validation Worker Tests
Tests for content validation functionality
"""

import pytest
from unittest.mock import MagicMock, patch


class TestValidateVacancyContent:
    """Tests for validate_vacancy_content task."""
    
    @patch('services.validation_worker.tasks.sync_engine')
    @patch('services.validation_worker.tasks.Session')
    def test_validate_success(self, mock_session_class, mock_engine, mock_vacancy):
        """Test successful validation with valid content."""
        from services.validation_worker.tasks import validate_vacancy_content
        
        # Setup valid vacancy
        mock_vacancy.title = "Кассир в магазин"  # Valid title
        mock_vacancy.description = "А" * 350  # Valid length
        mock_vacancy.image_url = "https://example.com/image.jpg"
        
        mock_session = MagicMock()
        mock_session_class.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_class.return_value.__exit__ = MagicMock(return_value=False)
        mock_session.get.return_value = mock_vacancy
        
        # Mock image check
        with patch('services.validation_worker.tasks._validate_image') as mock_img:
            mock_img.return_value = []
            
            with patch('services.publisher_worker.tasks.publish_vacancy'):
                result = validate_vacancy_content(mock_vacancy.id)
        
        assert result["status"] == "passed"
    
    @patch('services.validation_worker.tasks.sync_engine')
    @patch('services.validation_worker.tasks.Session')
    def test_validate_vacancy_not_found(self, mock_session_class, mock_engine):
        """Test handling when vacancy doesn't exist."""
        from services.validation_worker.tasks import validate_vacancy_content
        
        mock_session = MagicMock()
        mock_session_class.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_class.return_value.__exit__ = MagicMock(return_value=False)
        mock_session.get.return_value = None
        
        result = validate_vacancy_content("NON-EXISTENT-ID")
        
        assert "error" in result


class TestTitleValidation:
    """Tests for title validation rules."""
    
    def test_title_missing(self):
        """Test that missing title is caught."""
        from services.validation_worker.tasks import _validate_title
        
        errors = _validate_title(None)
        
        assert len(errors) > 0
        assert "Title is missing" in errors
    
    def test_title_too_long(self):
        """Test that overly long title is caught."""
        from services.validation_worker.tasks import _validate_title, MAX_TITLE_LENGTH
        
        long_title = "А" * (MAX_TITLE_LENGTH + 10)
        errors = _validate_title(long_title)
        
        assert any("too long" in e for e in errors)
    
    def test_title_too_short(self):
        """Test that short title is caught."""
        from services.validation_worker.tasks import _validate_title
        
        errors = _validate_title("Ок")
        
        assert any("too short" in e for e in errors)
    
    def test_title_contains_salary(self):
        """Test that salary in title is detected."""
        from services.validation_worker.tasks import _validate_title
        
        errors = _validate_title("Кассир 50000 руб")
        
        assert any("salary" in e.lower() for e in errors)
    
    def test_title_contains_pipe(self):
        """Test that pipe character is detected."""
        from services.validation_worker.tasks import _validate_title
        
        errors = _validate_title("Кассир | Продавец")
        
        assert any("pipe" in e.lower() or "|" in e for e in errors)
    
    def test_valid_title(self):
        """Test that valid title passes."""
        from services.validation_worker.tasks import _validate_title
        
        errors = _validate_title("Кассир в магазин без опыта")
        
        assert len(errors) == 0


class TestDescriptionValidation:
    """Tests for description validation rules."""
    
    def test_description_missing(self):
        """Test that missing description is caught."""
        from services.validation_worker.tasks import _validate_description
        
        errors, warnings = _validate_description(None)
        
        assert "Description is missing" in errors
    
    def test_description_too_short(self):
        """Test that short description is caught."""
        from services.validation_worker.tasks import _validate_description, MIN_DESCRIPTION_LENGTH
        
        short_desc = "А" * (MIN_DESCRIPTION_LENGTH - 10)
        errors, warnings = _validate_description(short_desc)
        
        assert any("too short" in e for e in errors)
    
    def test_description_too_long(self):
        """Test that overly long description is caught."""
        from services.validation_worker.tasks import _validate_description, MAX_DESCRIPTION_LENGTH
        
        long_desc = "А" * (MAX_DESCRIPTION_LENGTH + 100)
        errors, warnings = _validate_description(long_desc)
        
        assert any("too long" in e for e in errors)
    
    def test_valid_description(self):
        """Test that valid description passes."""
        from services.validation_worker.tasks import _validate_description
        
        valid_desc = "А" * 500  # Valid length
        errors, warnings = _validate_description(valid_desc)
        
        assert len(errors) == 0


class TestStopWords:
    """Tests for stop words detection."""
    
    def test_stop_word_discrimination(self):
        """Test that discriminatory phrases are detected."""
        from services.validation_worker.tasks import _check_stop_words
        
        errors = _check_stop_words("Работа для молодых", "Описание вакансии")
        
        assert len(errors) > 0
    
    def test_stop_word_health(self):
        """Test that health discrimination is detected."""
        from services.validation_worker.tasks import _check_stop_words
        
        errors = _check_stop_words("Вакансия", "Требуется медицинская справка")
        
        assert len(errors) > 0
    
    def test_stop_word_contact(self):
        """Test that contact info in title is detected."""
        from services.validation_worker.tasks import _check_stop_words
        
        errors = _check_stop_words("Работа звоните", "Описание")
        
        assert len(errors) > 0
    
    def test_no_stop_words(self):
        """Test that clean text passes."""
        from services.validation_worker.tasks import _check_stop_words
        
        errors = _check_stop_words("Кассир в магазин", "Работа в дружном коллективе")
        
        assert len(errors) == 0


class TestImageValidation:
    """Tests for image URL validation."""
    
    def test_image_missing(self):
        """Test that missing image is caught."""
        from services.validation_worker.tasks import _validate_image
        
        errors = _validate_image(None)
        
        assert "Image URL is missing" in errors
    
    def test_image_invalid_url(self):
        """Test that invalid URL format is caught."""
        from services.validation_worker.tasks import _validate_image
        
        errors = _validate_image("not-a-url")
        
        assert any("Invalid" in e for e in errors)
    
    @patch('httpx.Client')
    def test_image_accessible(self, mock_httpx):
        """Test image accessibility check."""
        from services.validation_worker.tasks import _validate_image
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "image/jpeg"}
        mock_httpx.return_value.__enter__.return_value.head.return_value = mock_response
        
        errors = _validate_image("https://example.com/image.jpg")
        
        assert len(errors) == 0
    
    @patch('httpx.Client')
    def test_image_not_accessible(self, mock_httpx):
        """Test handling of inaccessible image."""
        from services.validation_worker.tasks import _validate_image
        
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_httpx.return_value.__enter__.return_value.head.return_value = mock_response
        
        errors = _validate_image("https://example.com/missing.jpg")
        
        assert any("not accessible" in e for e in errors)
