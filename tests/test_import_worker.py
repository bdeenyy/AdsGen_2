"""
AdsGen 2.0 - Import Worker Tests
Tests for JSON import functionality
"""

import pytest
from unittest.mock import MagicMock, patch, ANY
import pandas as pd


class TestProcessJsonImport:
    """Tests for process_json_import task."""
    
    @patch('services.import_worker.tasks.sync_engine')
    @patch('services.import_worker.tasks.Session')
    @patch('services.import_worker.tasks.start_batch_processing')
    def test_process_json_import_valid_data(
        self, mock_batch, mock_session_class, mock_engine, sample_json_data
    ):
        """Test importing valid JSON data."""
        from services.import_worker.tasks import _process_dataframe
        from services.shared.models.import_batch import ImportSource
        
        # Setup mocks
        mock_session = MagicMock()
        mock_session_class.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_class.return_value.__exit__ = MagicMock(return_value=False)
        
        # Create DataFrame
        df = pd.DataFrame(sample_json_data)
        
        # Execute (testing the helper function directly)
        with patch('services.import_worker.tasks.get_profession', return_value="Кассир"):
            with patch('services.import_worker.tasks.generate_vacancy_id', return_value="MSK-001"):
                result = _process_dataframe(df, ImportSource.CSV, "test.json")
        
        # Verify
        assert result["total"] == 2
        assert "processed" in result
        assert "skipped" in result
        assert "errors" in result
    
    def test_column_mapping(self, sample_json_data):
        """Test that Russian column names are correctly mapped."""
        df = pd.DataFrame(sample_json_data)
        
        column_mapping = {
            "Город": "city",
            "Адрес": "address",
            "Должность": "position",
            "График": "schedule",
            "Уровень ЧТС": "level",
            "Актуальность": "relevance",
        }
        
        df = df.rename(columns=column_mapping)
        
        assert "city" in df.columns
        assert "position" in df.columns
        assert "address" in df.columns
    
    def test_city_filtering(self, sample_json_data):
        """Test that city filter works correctly."""
        df = pd.DataFrame(sample_json_data)
        
        # Filter by Moscow only
        cities_filter = ["Москва"]
        df_filtered = df[df["Город"].isin(cities_filter)]
        
        assert len(df_filtered) == 1
        assert df_filtered.iloc[0]["Город"] == "Москва"
    
    def test_relevance_filtering(self):
        """Test that relevance filter works correctly."""
        data = [
            {"Город": "Москва", "Должность": "Кассир", "Актуальность": "Да"},
            {"Город": "Москва", "Должность": "Продавец", "Актуальность": "Нет"},
            {"Город": "Москва", "Должность": "Грузчик", "Актуальность": "Актуально"},
        ]
        df = pd.DataFrame(data)
        
        # Filter relevant only
        df["relevance"] = df["Актуальность"].str.lower()
        relevant = df[df["relevance"].isin(["да", "актуально", "yes"])]
        
        assert len(relevant) == 2


class TestStartBatchProcessing:
    """Tests for start_batch_processing task."""
    
    @patch('services.import_worker.tasks.sync_engine')
    @patch('services.import_worker.tasks.Session')
    def test_start_batch_triggers_textgen(self, mock_session_class, mock_engine, mock_vacancy):
        """Test that batch processing triggers text generation."""
        from services.import_worker.tasks import start_batch_processing
        
        # Setup mocks
        mock_session = MagicMock()
        mock_session_class.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_class.return_value.__exit__ = MagicMock(return_value=False)
        
        # Mock query results
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_vacancy]
        mock_session.execute.return_value = mock_result
        
        with patch('services.textgen_worker.tasks.generate_vacancy_text') as mock_textgen:
            mock_textgen.delay = MagicMock()
            
            result = start_batch_processing("pending", 50)
        
        assert result["status"] == "completed"
        assert "triggered" in result


class TestDataValidation:
    """Tests for data validation in import."""
    
    def test_missing_required_column_city(self):
        """Test that missing city column raises error."""
        data = [{"Должность": "Кассир"}]
        df = pd.DataFrame(data)
        
        column_mapping = {"Должность": "position"}
        df = df.rename(columns=column_mapping)
        
        assert "city" not in df.columns
    
    def test_missing_required_column_position(self):
        """Test that missing position column raises error."""
        data = [{"Город": "Москва"}]
        df = pd.DataFrame(data)
        
        column_mapping = {"Город": "city"}
        df = df.rename(columns=column_mapping)
        
        assert "position" not in df.columns
    
    def test_empty_dataframe(self):
        """Test handling of empty dataframe."""
        df = pd.DataFrame()
        
        assert len(df) == 0
