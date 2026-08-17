from app.services.ml_monitoring_service import (
    MLMonitoringService,
)


def test_governance_healthy_when_metrics_are_within_thresholds():
    result = MLMonitoringService._governance(
        sample_size=500,
        duration_mae=6.5,
        sla_precision=0.45,
        sla_recall=0.78,
        drift_score=0.20,
        optimizer_error=20,
    )

    assert result["health_status"] == "Healthy"
    assert result["retrain_recommended"] is False


def test_governance_recommends_retraining_for_accuracy_degradation():
    result = MLMonitoringService._governance(
        sample_size=500,
        duration_mae=11.2,
        sla_precision=0.40,
        sla_recall=0.75,
        drift_score=0.20,
        optimizer_error=20,
    )

    assert result["health_status"] == "Retrain Recommended"
    assert result["retrain_recommended"] is True


def test_governance_recommends_retraining_for_high_drift():
    result = MLMonitoringService._governance(
        sample_size=500,
        duration_mae=7,
        sla_precision=0.40,
        sla_recall=0.75,
        drift_score=1.2,
        optimizer_error=20,
    )

    assert result["retrain_recommended"] is True


def test_governance_watch_for_small_sample_only():
    result = MLMonitoringService._governance(
        sample_size=40,
        duration_mae=6,
        sla_precision=0.45,
        sla_recall=0.80,
        drift_score=0.20,
        optimizer_error=None,
    )

    assert result["health_status"] == "Watch"
    assert result["retrain_recommended"] is False
