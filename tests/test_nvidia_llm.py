import unittest
from unittest.mock import Mock, patch

import requests

from toss_manager.config import NvidiaLLMSettings
from toss_manager.llm.nvidia import NvidiaLLMError, NvidiaQwenClient


class NvidiaQwenClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = NvidiaQwenClient(
            NvidiaLLMSettings(api_key="nvapi-secret"), timeout=5
        )

    def test_uses_fixed_qwen_model_and_bearer_key(self) -> None:
        response = Mock(ok=True, status_code=200)
        response.json.return_value = {"choices": [{"message": {"content": "분석 답변"}}]}
        self.client.session.post = Mock(return_value=response)
        answer = self.client.complete([{"role": "user", "content": "질문"}])
        self.assertEqual(answer, "분석 답변")
        kwargs = self.client.session.post.call_args.kwargs
        self.assertEqual(kwargs["json"]["model"], "qwen/qwen3.5-397b-a17b")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer nvapi-secret")
        self.assertFalse(kwargs["json"]["stream"])

    @patch("toss_manager.llm.nvidia.time.sleep")
    def test_429_retries_once(self, sleep: Mock) -> None:
        limited = Mock(ok=False, status_code=429, headers={"Retry-After": "2"})
        success = Mock(ok=True, status_code=200)
        success.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
        self.client.session.post = Mock(side_effect=[limited, success])
        self.assertEqual(self.client.complete([{"role": "user", "content": "q"}]), "ok")
        sleep.assert_called_once_with(2.0)
        self.assertEqual(self.client.session.post.call_count, 2)

    def test_missing_key_never_sends_request(self) -> None:
        client = NvidiaQwenClient(NvidiaLLMSettings(api_key=""))
        client.session.post = Mock()
        with self.assertRaisesRegex(NvidiaLLMError, "NVIDIA_API_KEY"):
            client.complete([{"role": "user", "content": "q"}])
        client.session.post.assert_not_called()

    def test_timeout_becomes_safe_error(self) -> None:
        self.client.session.post = Mock(side_effect=requests.Timeout())
        with self.assertRaisesRegex(NvidiaLLMError, "시간이 초과"):
            self.client.complete([{"role": "user", "content": "q"}])


if __name__ == "__main__":
    unittest.main()
