"""
AdsGen 2.0 - Publisher Worker Tests
Tests for XML export and publishing functionality
"""

import pytest
from unittest.mock import MagicMock, patch


class TestPublishVacancy:
    """Tests for publish_vacancy task."""
    
    @patch('services.publisher_worker.tasks.sync_engine')
    @patch('services.publisher_worker.tasks.Session')
    def test_publish_vacancy_success(self, mock_session_class, mock_engine, mock_vacancy):
        """Test successful vacancy publishing."""
        from services.publisher_worker.tasks import publish_vacancy
        
        mock_session = MagicMock()
        mock_session_class.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_class.return_value.__exit__ = MagicMock(return_value=False)
        mock_session.get.return_value = mock_vacancy
        
        result = publish_vacancy(mock_vacancy.id)
        
        assert result["status"] == "ready_for_export"
        assert result["vacancy_id"] == mock_vacancy.id
    
    @patch('services.publisher_worker.tasks.sync_engine')
    @patch('services.publisher_worker.tasks.Session')
    def test_publish_vacancy_not_found(self, mock_session_class, mock_engine):
        """Test handling when vacancy doesn't exist."""
        from services.publisher_worker.tasks import publish_vacancy
        
        mock_session = MagicMock()
        mock_session_class.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_class.return_value.__exit__ = MagicMock(return_value=False)
        mock_session.get.return_value = None
        
        result = publish_vacancy("NON-EXISTENT-ID")
        
        assert "error" in result


class TestExportToXml:
    """Tests for export_to_xml task."""
    
    @patch('services.publisher_worker.tasks.sync_engine')
    @patch('services.publisher_worker.tasks.Session')
    def test_export_with_vacancies(self, mock_session_class, mock_engine, mock_vacancy):
        """Test XML export with vacancies."""
        from services.publisher_worker.tasks import export_to_xml
        
        mock_session = MagicMock()
        mock_session_class.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_class.return_value.__exit__ = MagicMock(return_value=False)
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_vacancy]
        mock_session.execute.return_value = mock_result
        
        result = export_to_xml()
        
        assert result["exported"] == 1
        assert "filename" in result
        assert result["filename"].endswith(".xml")
    
    @patch('services.publisher_worker.tasks.sync_engine')
    @patch('services.publisher_worker.tasks.Session')
    def test_export_no_vacancies(self, mock_session_class, mock_engine):
        """Test XML export with no vacancies."""
        from services.publisher_worker.tasks import export_to_xml
        
        mock_session = MagicMock()
        mock_session_class.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_class.return_value.__exit__ = MagicMock(return_value=False)
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result
        
        result = export_to_xml()
        
        assert result["exported"] == 0


class TestXmlGeneration:
    """Tests for XML building functions."""
    
    def test_build_ad_xml_contains_required_fields(self, mock_vacancy):
        """Test that XML contains all required Avito fields."""
        from services.publisher_worker.tasks import _build_ad_xml
        
        xml = _build_ad_xml(mock_vacancy)
        
        # Check for required elements
        assert "<Id>" in xml
        assert "<AdType>" in xml
        assert "<Category>" in xml
        assert "<Title>" in xml
        assert "<Address>" in xml
        assert "</Ad>" in xml
    
    def test_build_ad_xml_escapes_special_chars(self, mock_vacancy):
        """Test that special XML characters are escaped."""
        from services.publisher_worker.tasks import _build_ad_xml
        
        mock_vacancy.city = "Москва & Область"
        mock_vacancy.title = "Кассир <срочно>"
        
        xml = _build_ad_xml(mock_vacancy)
        
        assert "&amp;" in xml or "&" not in xml.replace("&amp;", "").replace("&lt;", "").replace("&gt;", "")
    
    def test_build_xml_multiple_vacancies(self, mock_vacancy):
        """Test XML generation with multiple vacancies."""
        from services.publisher_worker.tasks import _build_xml
        
        vacancies = [mock_vacancy, mock_vacancy]
        
        xml = _build_xml(vacancies)
        
        assert '<?xml version="1.0"' in xml
        assert '<Ads formatVersion="3"' in xml
        assert xml.count("<Ad>") == 2
        assert "</Ads>" in xml


class TestXmlEscaping:
    """Tests for XML escaping function."""
    
    def test_escape_ampersand(self):
        """Test escaping of ampersand."""
        from services.publisher_worker.tasks import _escape_xml
        
        result = _escape_xml("Tom & Jerry")
        
        assert "&amp;" in result
    
    def test_escape_less_than(self):
        """Test escaping of less-than sign."""
        from services.publisher_worker.tasks import _escape_xml
        
        result = _escape_xml("a < b")
        
        assert "&lt;" in result
    
    def test_escape_greater_than(self):
        """Test escaping of greater-than sign."""
        from services.publisher_worker.tasks import _escape_xml
        
        result = _escape_xml("a > b")
        
        assert "&gt;" in result
    
    def test_escape_empty_string(self):
        """Test handling of empty string."""
        from services.publisher_worker.tasks import _escape_xml
        
        result = _escape_xml("")
        
        assert result == ""
    
    def test_escape_none(self):
        """Test handling of None."""
        from services.publisher_worker.tasks import _escape_xml
        
        result = _escape_xml(None)
        
        assert result == ""
    
    def test_escape_quotes(self):
        """Test escaping of quotes."""
        from services.publisher_worker.tasks import _escape_xml
        
        result = _escape_xml('He said "Hello"')
        
        assert "&quot;" in result or '"' not in result
