import pytest
from engines.base_engine import BaseEngine


class ConcreteEngine(BaseEngine):
    """Concrete implementation for testing BaseEngine"""

    def process(self, data):
        return {'processed': True, 'data': data}


@pytest.mark.unit
class TestBaseEngine:
    """Test BaseEngine abstract class and filtering logic"""

    def test_engine_initialization(self, mock_db):
        """Test engine initializes with correct parameters"""
        engine = ConcreteEngine(
            db=mock_db,
            name='TestEngine',
            event_types=['MCP', 'HTTP'],
            producers=['local', 'remote']
        )

        assert engine.name == 'TestEngine'
        assert engine.event_types == ['MCP', 'HTTP']
        assert engine.producers == ['local', 'remote']
        assert engine.db == mock_db

    def test_should_process_with_matching_event_type(self, mock_db):
        """Test engine accepts events with matching event type"""
        engine = ConcreteEngine(
            db=mock_db,
            name='TestEngine',
            event_types=['MCP'],
            producers=None
        )

        event = {'eventType': 'MCP', 'producer': 'local'}
        assert engine.should_process(event) is True

    def test_should_not_process_with_non_matching_event_type(self, mock_db):
        """Test engine rejects events with non-matching event type"""
        engine = ConcreteEngine(
            db=mock_db,
            name='TestEngine',
            event_types=['HTTP'],
            producers=None
        )

        event = {'eventType': 'MCP', 'producer': 'local'}
        assert engine.should_process(event) is False

    def test_should_process_with_matching_producer(self, mock_db):
        """Test engine accepts events with matching producer"""
        engine = ConcreteEngine(
            db=mock_db,
            name='TestEngine',
            event_types=None,
            producers=['local']
        )

        event = {'eventType': 'MCP', 'producer': 'local'}
        assert engine.should_process(event) is True

    def test_should_not_process_with_non_matching_producer(self, mock_db):
        """Test engine rejects events with non-matching producer"""
        engine = ConcreteEngine(
            db=mock_db,
            name='TestEngine',
            event_types=None,
            producers=['remote']
        )

        event = {'eventType': 'MCP', 'producer': 'local'}
        assert engine.should_process(event) is False

    def test_should_process_with_both_filters_matching(self, mock_db):
        """Test engine accepts events when both filters match"""
        engine = ConcreteEngine(
            db=mock_db,
            name='TestEngine',
            event_types=['MCP'],
            producers=['local']
        )

        event = {'eventType': 'MCP', 'producer': 'local'}
        assert engine.should_process(event) is True

    def test_should_not_process_with_one_filter_not_matching(self, mock_db):
        """Test engine rejects events when one filter doesn't match"""
        engine = ConcreteEngine(
            db=mock_db,
            name='TestEngine',
            event_types=['MCP'],
            producers=['remote']
        )

        event = {'eventType': 'MCP', 'producer': 'local'}
        assert engine.should_process(event) is False

    def test_should_process_with_no_filters(self, mock_db):
        """Test engine accepts all events when no filters are set"""
        engine = ConcreteEngine(
            db=mock_db,
            name='TestEngine',
            event_types=None,
            producers=None
        )

        event = {'eventType': 'MCP', 'producer': 'local'}
        assert engine.should_process(event) is True

    @pytest.mark.asyncio
    async def test_handle_event_processes_valid_event(self, mock_db):
        """Test handle_event processes valid events"""
        engine = ConcreteEngine(
            db=mock_db,
            name='TestEngine',
            event_types=['MCP'],
            producers=['local']
        )

        event = {'eventType': 'MCP', 'producer': 'local', 'data': 'test'}
        result = await engine.handle_event(event)

        assert result is not None
        assert result['processed'] is True
        assert result['data'] == event

    @pytest.mark.asyncio
    async def test_handle_event_rejects_invalid_event(self, mock_db):
        """Test handle_event rejects events that don't pass filters"""
        engine = ConcreteEngine(
            db=mock_db,
            name='TestEngine',
            event_types=['HTTP'],
            producers=['local']
        )

        event = {'eventType': 'MCP', 'producer': 'local'}
        result = await engine.handle_event(event)

        assert result is None

    @pytest.mark.asyncio
    async def test_handle_event_handles_exceptions(self, mock_db):
        """Test handle_event handles exceptions gracefully"""
        class FailingEngine(BaseEngine):
            def process(self, data):
                raise ValueError("Intentional error")

        engine = FailingEngine(
            db=mock_db,
            name='FailingEngine',
            event_types=None,
            producers=None
        )

        event = {'eventType': 'MCP', 'producer': 'local'}
        result = await engine.handle_event(event)

        assert result is None

    def test_process_is_abstract(self, mock_db):
        """Test that process method must be implemented"""
        with pytest.raises(TypeError):
            BaseEngine(db=mock_db, name='Test')

    @pytest.mark.asyncio
    async def test_handle_event_awaits_async_process(self, mock_db):
        """Test handle_event properly awaits async process methods"""
        class AsyncEngine(BaseEngine):
            async def process(self, data):
                return {'async': True, 'data': data}

        engine = AsyncEngine(
            db=mock_db,
            name='AsyncEngine',
            event_types=None,
            producers=None
        )

        event = {'eventType': 'MCP', 'producer': 'local'}
        result = await engine.handle_event(event)

        assert result is not None
        assert result['async'] is True
        assert result['data'] == event
