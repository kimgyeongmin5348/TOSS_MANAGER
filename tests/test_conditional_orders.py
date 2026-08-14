import unittest
from datetime import date, timedelta
from unittest.mock import Mock

from toss_manager.client import TossAPIClient
from toss_manager.conditional_orders import build_condition, build_conditional_order
from toss_manager.config import Settings


class ConditionalOrderPayloadTests(unittest.TestCase):
    def test_single_limit_payload_matches_official_schema(self) -> None:
        first = build_condition("SELL", "305", "304.5", "LIMIT")
        payload = build_conditional_order(
            symbol="nvda", order_kind="SINGLE", quantity="1.5",
            order_type="LIMIT", expire_date=date.today() + timedelta(days=1),
            first=first, client_order_id="porto-test-1",
        )
        self.assertEqual(payload["symbol"], "NVDA")
        self.assertEqual(payload["first"]["orderPrice"], "304.5")
        self.assertEqual(payload["clientOrderId"], "porto-test-1")

    def test_oco_rejects_market_order(self) -> None:
        with self.assertRaisesRegex(ValueError, "지정가"):
            build_conditional_order(
                symbol="NVDA", order_kind="OCO", quantity="1",
                order_type="MARKET", expire_date=date.today() + timedelta(days=1),
                first={"orderSide": "SELL"}, second={"orderSide": "SELL"},
            )

    def test_oto_enforces_buy_then_sell(self) -> None:
        with self.assertRaisesRegex(ValueError, "첫 조건이 매수"):
            build_conditional_order(
                symbol="NVDA", order_kind="OTO", quantity="1",
                order_type="LIMIT", expire_date=date.today() + timedelta(days=1),
                first={"orderSide": "SELL"}, second={"orderSide": "SELL"},
            )


class ConditionalOrderClientTests(unittest.TestCase):
    def test_create_uses_account_header_and_payload(self) -> None:
        client = TossAPIClient(Settings("client", "secret"))
        client._token = Mock(return_value="token")
        response = Mock(ok=True, status_code=200, content=b"{}")
        response.json.return_value = {"result": {"conditionalOrderId": "new-id"}}
        client.session.request = Mock(return_value=response)

        result = client.create_conditional_order(7, {"symbol": "NVDA"})

        self.assertEqual(result["conditionalOrderId"], "new-id")
        kwargs = client.session.request.call_args.kwargs
        self.assertEqual(kwargs["headers"]["X-Tossinvest-Account"], "7")
        self.assertEqual(kwargs["json"]["symbol"], "NVDA")

    def test_cancel_uses_delete(self) -> None:
        client = TossAPIClient(Settings("client", "secret"))
        client._mutate = Mock(return_value=None)
        client.cancel_conditional_order(2, "order-id")
        self.assertEqual(client._mutate.call_args.args[0], "DELETE")


if __name__ == "__main__":
    unittest.main()
