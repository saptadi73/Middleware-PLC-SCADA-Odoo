import unittest
from unittest.mock import Mock

from app.services.plc_manual_weighing_service import PLCManualWeighingService


class ManualWeighingWorkflowTest(unittest.TestCase):
    def _make_service(self) -> PLCManualWeighingService:
        service = PLCManualWeighingService()
        service.layouts = [
            {
                "reference_key": "MANUAL01",
                "handshake_address": 9012,
            }
        ]
        return service

    def test_validation_failure_does_not_mark_handshake(self) -> None:
        service = self._make_service()
        service.read_manual_weighing_data = Mock(
            return_value={"handshake_address": 9012, "mo_id": "WH/MO/00001"}
        )
        service.validate_weighing_data = Mock(return_value=(False, "invalid payload"))
        service._find_pending_retry_record = Mock(return_value=None)
        service.sync_to_odoo = Mock(return_value=(True, None))
        service.mark_handshake = Mock(return_value=True)

        ok = service.read_and_sync()

        self.assertFalse(ok)
        service.sync_to_odoo.assert_not_called()
        service.mark_handshake.assert_not_called()

    def test_pending_retry_skips_odoo_and_only_retries_handshake(self) -> None:
        service = self._make_service()
        pending_record = Mock()
        pending_record.id = "retry-1"
        service.read_manual_weighing_data = Mock(
            return_value={"handshake_address": 9012, "mo_id": "WH/MO/00001"}
        )
        service.validate_weighing_data = Mock(return_value=(True, None))
        service._find_pending_retry_record = Mock(return_value=pending_record)
        service.sync_to_odoo = Mock(return_value=(True, None))
        service.mark_handshake = Mock(return_value=True)
        service._mark_retry_completed = Mock()

        ok = service.read_and_sync()

        self.assertTrue(ok)
        service.sync_to_odoo.assert_not_called()
        service.mark_handshake.assert_called_once_with(9012)
        service._mark_retry_completed.assert_called_once_with("retry-1")

    def test_success_marks_handshake_after_sync(self) -> None:
        service = self._make_service()
        call_order: list[str] = []

        service.read_manual_weighing_data = Mock(
            return_value={"handshake_address": 9012, "mo_id": "WH/MO/00001"}
        )
        service.validate_weighing_data = Mock(return_value=(True, None))
        service._find_pending_retry_record = Mock(return_value=None)

        def _sync_to_odoo(_data):
            call_order.append("sync")
            return (True, None)

        def _record_success(_data):
            call_order.append("record")
            return "retry-1"

        def _mark_handshake(_address):
            call_order.append("handshake")
            return True

        service.sync_to_odoo = Mock(side_effect=_sync_to_odoo)
        service._record_successful_sync = Mock(side_effect=_record_success)
        service.mark_handshake = Mock(side_effect=_mark_handshake)
        service._mark_retry_completed = Mock(side_effect=lambda record_id: call_order.append(f"complete:{record_id}"))

        ok = service.read_and_sync()

        self.assertTrue(ok)
        self.assertEqual(call_order, ["sync", "record", "handshake", "complete:retry-1"])
        service.mark_handshake.assert_called_once_with(9012)

    def test_sync_failure_does_not_mark_handshake(self) -> None:
        service = self._make_service()
        service.read_manual_weighing_data = Mock(
            return_value={"handshake_address": 9012, "mo_id": "WH/MO/00001"}
        )
        service.validate_weighing_data = Mock(return_value=(True, None))
        service._find_pending_retry_record = Mock(return_value=None)
        service.sync_to_odoo = Mock(return_value=(False, "odoo down"))
        service.mark_handshake = Mock(return_value=True)

        ok = service.read_and_sync()

        self.assertFalse(ok)
        service.sync_to_odoo.assert_called_once()
        service.mark_handshake.assert_not_called()


if __name__ == "__main__":
    unittest.main()
