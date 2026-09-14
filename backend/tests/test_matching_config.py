from backend.app.services import matching_config_service as svc


class TestWeightsService:
    def test_defaults_match_original_constants(self, db, seed):
        w = svc.get_weights(db)
        assert w.gstin_weight == 0.60
        assert w.pan_weight == 0.55
        assert w.name_weight == 0.42
        assert w.address_weight == 0.28
        assert w.pin_weight == 0.12
        assert w.pin_requires_name_sim == 0.35
        assert w.auto_link_threshold == 0.92
        assert w.review_threshold == 0.70

    def test_update_persists_and_stamps_actor(self, db, seed):
        out = svc.update_weights(db, {"review_threshold": 0.65}, updated_by="admin")
        assert out["review_threshold"] == 0.65
        assert out["updated_by"] == "admin"
        # untouched fields keep their default
        assert out["auto_link_threshold"] == 0.92

        w = svc.get_weights(db)
        assert w.review_threshold == 0.65

    def test_matching_engine_uses_updated_weights(self, db, seed):
        from backend.app.db.models.source_record import SourceRecord
        from backend.app.services.matching_engine import process_source_record

        def _weak_record(external_id):
            sr = SourceRecord(
                source_system_id=db.query(SourceRecord.source_system_id).first()[0],
                external_id=external_id,
                raw_payload={}, normalized_payload={},
                extracted_name="Acme Steel Wrks",
            )
            db.add(sr)
            db.commit()
            db.refresh(sr)
            return sr

        # With the default 0.70 review threshold, name similarity alone
        # isn't corroborating enough to reach review.
        before = process_source_record(db, _weak_record("weak-default").id)
        assert before["decision"] == "NEW_ENTITY"

        # Lower the review threshold far enough and the same kind of weak
        # name-only match should now clear it.
        svc.update_weights(db, {"review_threshold": 0.05}, updated_by="admin")
        after = process_source_record(db, _weak_record("weak-lowered").id)
        assert after["decision"] == "REVIEW"

    def test_calibration_report_buckets_review_cases_by_confidence(self, db, seed):
        report = svc.calibration_report(db)
        assert report["sample_size"] >= 1
        assert any(b["label"] for b in report["buckets"])
        assert "weights" in report


class TestWeightsApi:
    def test_get_weights_requires_admin(self, client, seed, token):
        assert (
            client.get("/api/v1/matching/weights", headers=token("reviewer")).status_code
            == 403
        )
        resp = client.get("/api/v1/matching/weights", headers=token("admin"))
        assert resp.status_code == 200
        assert resp.json()["auto_link_threshold"] == 0.92

    def test_put_weights_updates_and_is_audited_by_actor(self, client, seed, token):
        resp = client.put(
            "/api/v1/matching/weights",
            headers=token("admin"),
            json={"pin_weight": 0.2},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["pin_weight"] == 0.2
        assert body["updated_by"] == "admin@test.local"

    def test_put_weights_rejects_out_of_range_values(self, client, seed, token):
        resp = client.put(
            "/api/v1/matching/weights",
            headers=token("admin"),
            json={"review_threshold": 1.5},
        )
        assert resp.status_code == 422

    def test_calibration_endpoint(self, client, seed, token):
        resp = client.get("/api/v1/matching/calibration", headers=token("admin"))
        assert resp.status_code == 200
        body = resp.json()
        assert "buckets" in body and "signals" in body
