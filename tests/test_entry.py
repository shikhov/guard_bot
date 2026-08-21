import hashlib
import hmac
import sys
import types
import unittest
from time import time
from urllib.parse import urlencode


js = types.ModuleType("js")
js.fetch = None
js.Request = object
sys.modules.setdefault("js", js)

workers = types.ModuleType("workers")
workers.Response = object
workers.WorkerEntrypoint = object
sys.modules.setdefault("workers", workers)

from entry import mini_app_url, validate_web_app_init_data, webhook_secret


class EntryHelpersTest(unittest.TestCase):
    def test_webhook_secret_is_stable_and_not_plaintext(self):
        token = "123456:secret"
        self.assertEqual(webhook_secret(token), hashlib.sha256(token.encode()).hexdigest())
        self.assertNotEqual(webhook_secret(token), token)

    def test_valid_init_data(self):
        token = "123456:secret"
        values = {"auth_date": str(int(time())), "query_id": "query", "user": "{}"}
        check_string = "\n".join(f"{key}={value}" for key, value in sorted(values.items()))
        secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
        values["hash"] = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
        self.assertTrue(validate_web_app_init_data(urlencode(values), token))

    def test_invalid_and_expired_init_data_are_rejected(self):
        token = "123456:secret"
        values = {"auth_date": "1", "query_id": "query"}
        check_string = "\n".join(f"{key}={value}" for key, value in sorted(values.items()))
        secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
        values["hash"] = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
        self.assertFalse(validate_web_app_init_data(urlencode(values), token))
        values["hash"] = "0" * 64
        self.assertFalse(validate_web_app_init_data(urlencode(values), token))

    def test_mini_app_url_encodes_title(self):
        result = mini_app_url("https://bot.example/telegram/webhook", "q1", "Мой чат")
        self.assertEqual(result, "https://bot.example/join_request?query_id=q1&title=%D0%9C%D0%BE%D0%B9+%D1%87%D0%B0%D1%82")


if __name__ == "__main__":
    unittest.main()
