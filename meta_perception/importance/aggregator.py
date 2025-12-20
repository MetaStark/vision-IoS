"""Feature importance aggregation."""
from typing import Dict
from datetime import datetime
from meta_perception.models.importance_models import FeatureImportance
from meta_perception.models.decision_models import MetaPerceptionInput
from meta_perception.models.perception_state import PerceptionSnapshot
from meta_perception.models.config_models import PerceptionConfig
from meta_perception.utils.id_generation import generate_importance_id

def compute_feature_importance(
    inputs: MetaPerceptionInput,
    perception_snapshot: PerceptionSnapshot,
    config: PerceptionConfig
) -> FeatureImportance:
    """Compute feature importance."""
    # Simple importance based on feature magnitudes
    global_importance = {}
    for feature, value in inputs.features.items():
        global_importance[feature] = min(abs(value) / 10.0, 1.0)
    
    # Sort features by importance
    sorted_features = sorted(global_importance.items(), key=lambda x: x[1], reverse=True)
    top_5 = sorted_features[:5]
    
    return FeatureImportance(
        report_id=generate_importance_id(perception_snapshot.snapshot_id),
        timestamp=datetime.now(),
        perception_snapshot_id=perception_snapshot.snapshot_id,
        global_importance=global_importance,
        entropy_drivers=global_importance,
        intent_drivers=global_importance,
        reflexivity_drivers=global_importance,
        shock_drivers=global_importance,
        top_5_features=top_5,
        importance_delta={},
        metadata={}
    )
