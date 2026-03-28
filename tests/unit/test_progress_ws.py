"""
Tests for Progress Monitoring.
"""

from legacy.distributed_task_v2.progress_ws import (
    MessageType,
    ProgressTracker,
    ProgressUpdate,
    StageProgress,
    TaskProgress,
)


class TestProgressUpdate:
    """Test ProgressUpdate class."""

    def test_create_update(self):
        """Test creating a progress update."""
        update = ProgressUpdate(
            task_id="task-001",
            message_type=MessageType.TASK_STATUS,
            data={"progress": 0.5}
        )

        assert update.task_id == "task-001"
        assert update.message_type == MessageType.TASK_STATUS
        assert update.data["progress"] == 0.5

    def test_to_json(self):
        """Test JSON serialization."""
        update = ProgressUpdate(
            task_id="task-001",
            message_type=MessageType.TASK_STATUS,
            data={"status": "running"}
        )

        json_str = update.to_json()

        assert "task-001" in json_str
        assert "task_status" in json_str

    def test_from_json(self):
        """Test JSON deserialization."""
        json_str = '{"task_id": "task-001", "message_type": "task_status", "timestamp": 1234567890, "data": {"progress": 0.5}}'

        update = ProgressUpdate.from_json(json_str)

        assert update.task_id == "task-001"
        assert update.message_type == MessageType.TASK_STATUS
        assert update.data["progress"] == 0.5


class TestTaskProgress:
    """Test TaskProgress class."""

    def test_create_task_progress(self):
        """Test creating task progress."""
        progress = TaskProgress(
            task_id="task-001",
            status="running",
            progress=0.5,
            total_stages=3,
            completed_stages=1
        )

        assert progress.task_id == "task-001"
        assert progress.status == "running"
        assert progress.progress == 0.5

    def test_to_dict(self):
        """Test task progress serialization."""
        progress = TaskProgress(
            task_id="task-001",
            status="running",
            progress=0.5,
            total_stages=3,
            completed_stages=1
        )

        data = progress.to_dict()

        assert data["task_id"] == "task-001"
        assert data["status"] == "running"
        assert data["progress"] == 0.5


class TestStageProgress:
    """Test StageProgress class."""

    def test_create_stage_progress(self):
        """Test creating stage progress."""
        progress = StageProgress(
            stage_id="stage-1",
            task_id="task-001",
            status="running",
            progress=0.3,
            total_chunks=10,
            completed_chunks=3
        )

        assert progress.stage_id == "stage-1"
        assert progress.status == "running"
        assert progress.progress == 0.3

    def test_to_dict(self):
        """Test stage progress serialization."""
        progress = StageProgress(
            stage_id="stage-1",
            task_id="task-001",
            status="running",
            progress=0.3,
            total_chunks=10,
            completed_chunks=3,
            failed_chunks=1
        )

        data = progress.to_dict()

        assert data["stage_id"] == "stage-1"
        assert data["total_chunks"] == 10
        assert data["completed_chunks"] == 3
        assert data["failed_chunks"] == 1


class TestProgressTracker:
    """Test ProgressTracker class."""

    def test_init(self):
        """Test tracker initialization."""
        tracker = ProgressTracker()

        assert len(tracker._task_progress) == 0
        assert len(tracker._stage_progress) == 0

    def test_register_task(self):
        """Test registering a task."""
        tracker = ProgressTracker()

        progress = tracker.register_task("task-001", total_stages=3)

        assert progress.task_id == "task-001"
        assert progress.total_stages == 3
        assert progress.status == "pending"
        assert "task-001" in tracker._task_progress

    def test_register_stage(self):
        """Test registering a stage."""
        tracker = ProgressTracker()
        tracker.register_task("task-001", total_stages=1)

        progress = tracker.register_stage("task-001", "stage-1", total_chunks=10)

        assert progress.stage_id == "stage-1"
        assert progress.total_chunks == 10
        assert "task-001:stage-1" in tracker._stage_progress

    def test_update_task_status(self):
        """Test updating task status."""
        tracker = ProgressTracker()
        tracker.register_task("task-001", total_stages=1)

        tracker.update_task_status("task-001", "running", progress=0.5)

        progress = tracker.get_task_progress("task-001")
        assert progress.status == "running"
        assert progress.progress == 0.5

    def test_update_stage_progress(self):
        """Test updating stage progress."""
        tracker = ProgressTracker()
        tracker.register_task("task-001", total_stages=1)
        tracker.register_stage("task-001", "stage-1", total_chunks=10)

        tracker.update_stage_progress("task-001", "stage-1", completed_chunks=5)

        progress = tracker.get_stage_progress("task-001", "stage-1")
        assert progress.completed_chunks == 5
        assert progress.progress == 0.5

    def test_complete_chunk(self):
        """Test completing a chunk."""
        tracker = ProgressTracker()
        tracker.register_task("task-001", total_stages=1)
        tracker.register_stage("task-001", "stage-1", total_chunks=10)

        tracker.complete_chunk("task-001", "stage-1", "chunk-1")

        progress = tracker.get_stage_progress("task-001", "stage-1")
        assert progress.completed_chunks == 1
        assert progress.progress == 0.1

    def test_fail_chunk(self):
        """Test failing a chunk."""
        tracker = ProgressTracker()
        tracker.register_task("task-001", total_stages=1)
        tracker.register_stage("task-001", "stage-1", total_chunks=10)

        tracker.fail_chunk("task-001", "stage-1", "chunk-1", "Test error")

        progress = tracker.get_stage_progress("task-001", "stage-1")
        assert progress.failed_chunks == 1

    def test_complete_task(self):
        """Test completing a task."""
        tracker = ProgressTracker()
        tracker.register_task("task-001", total_stages=1)

        tracker.complete_task("task-001", result={"total": 100})

        progress = tracker.get_task_progress("task-001")
        assert progress.status == "completed"
        assert progress.progress == 1.0

    def test_subscribe(self):
        """Test subscribing to updates."""
        tracker = ProgressTracker()
        received_updates = []

        def callback(update):
            received_updates.append(update)

        tracker.subscribe("task-001", callback)
        tracker.register_task("task-001", total_stages=1)

        assert len(received_updates) == 1
        assert received_updates[0].task_id == "task-001"

    def test_unsubscribe(self):
        """Test unsubscribing from updates."""
        tracker = ProgressTracker()
        received_updates = []

        def callback(update):
            received_updates.append(update)

        tracker.subscribe("task-001", callback)
        tracker.unsubscribe("task-001", callback)
        tracker.register_task("task-001", total_stages=1)

        assert len(received_updates) == 0

    def test_get_history(self):
        """Test getting progress history."""
        tracker = ProgressTracker()
        tracker.register_task("task-001", total_stages=1)
        tracker.update_task_status("task-001", "running")
        tracker.complete_task("task-001")

        history = tracker.get_history("task-001")

        assert len(history) == 3

    def test_get_task_progress_not_found(self):
        """Test getting progress for non-existent task."""
        tracker = ProgressTracker()

        progress = tracker.get_task_progress("nonexistent")

        assert progress is None

    def test_get_stage_progress_not_found(self):
        """Test getting progress for non-existent stage."""
        tracker = ProgressTracker()

        progress = tracker.get_stage_progress("task-001", "stage-1")

        assert progress is None


class TestMessageType:
    """Test MessageType enum."""

    def test_message_types(self):
        """Test all message types are defined."""
        assert MessageType.TASK_STATUS.value == "task_status"
        assert MessageType.STAGE_PROGRESS.value == "stage_progress"
        assert MessageType.CHUNK_COMPLETE.value == "chunk_complete"
        assert MessageType.TASK_RESULT.value == "task_result"
        assert MessageType.TASK_ERROR.value == "task_error"
        assert MessageType.NODE_STATUS.value == "node_status"
        assert MessageType.SYSTEM_STATS.value == "system_stats"
