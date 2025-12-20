"""Artifact manager."""
from pathlib import Path
from meta_perception.artifacts.serializers import save_artifact

class ArtifactManager:
    """Manages artifact storage."""
    
    def __init__(self, base_path: str = "artifacts_output"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def save_snapshot(self, snapshot):
        """Save perception snapshot."""
        path = self.base_path / "perception_snapshots" / f"{snapshot.snapshot_id}.json"
        save_artifact(snapshot, str(path))
        return str(path)
    
    def save_decision(self, decision):
        """Save decision."""
        path = self.base_path / "reports" / f"decision_{decision.decision_id}.json"
        save_artifact(decision, str(path))
        return str(path)
    
    def save_importance_report(self, importance):
        """Save feature importance report."""
        path = self.base_path / "reports" / f"{importance.report_id}.json"
        save_artifact(importance, str(path))
        return str(path)
