from temperance.activity_detail_summary import summarize_activity_detail_bundle


def test_summarize_activity_detail_bundle_drops_large_detail_arrays() -> None:
    payload = {
        "details": {
            "activityId": 123,
            "detailsAvailable": True,
            "measurementCount": 32,
            "metricsCount": 2000,
            "totalMetricsCount": 4000,
            "metricDescriptors": [{"key": "directHeartRate"}],
            "activityDetailMetrics": [{"metrics": [1, 2, 3]}],
            "heartRateDTOs": [{"hr": 140}],
            "geoPolylineDTO": {"polyline": "abc"},
            "deviceName": "Forerunner",
        },
        "weather": {
            "temp": 21.5,
            "apparentTemp": 22,
            "relativeHumidity": 70,
            "windSpeed": 8,
            "weatherStationDTO": {"name": "Station", "extra": "drop nested blob"},
        },
        "hr_timezones": [
            {"zoneNumber": 1, "secsInZone": 1200},
            {"zoneNumber": 2, "secsInZone": 800},
        ],
    }

    summary = summarize_activity_detail_bundle(payload)

    assert summary["storage"] == "summary"
    assert summary["details"]["activityId"] == 123
    assert summary["details"]["detailsAvailable"] is True
    assert summary["details"]["measurementCount"] == 32
    assert summary["details"]["metricsCount"] == 2000
    assert summary["details"]["totalMetricsCount"] == 4000
    assert summary["details"]["deviceName"] == "Forerunner"
    assert "metricDescriptors" not in summary["details"]
    assert "activityDetailMetrics" not in summary["details"]
    assert "heartRateDTOs" not in summary["details"]
    assert "geoPolylineDTO" not in summary["details"]
    assert summary["weather"]["temp"] == 21.5
    assert "weatherStationDTO" not in summary["weather"]
    assert summary["hr_timezones"] == [
        {"zoneNumber": 1, "secsInZone": 1200},
        {"zoneNumber": 2, "secsInZone": 800},
    ]
    assert summary["dropped_detail_keys"] == [
        "activityDetailMetrics",
        "geoPolylineDTO",
        "heartRateDTOs",
        "metricDescriptors",
    ]


def test_summarize_activity_detail_bundle_preserves_unknown_small_scalars() -> None:
    payload = {
        "details": {
            "activityId": "a1",
            "trainingEffectLabel": "PRODUCTIVE",
            "someSmallScalar": "keep",
            "someNestedBlob": {"large": ["drop"]},
        }
    }

    summary = summarize_activity_detail_bundle(payload)

    assert summary["details"]["trainingEffectLabel"] == "PRODUCTIVE"
    assert summary["details"]["someSmallScalar"] == "keep"
    assert "someNestedBlob" not in summary["details"]
