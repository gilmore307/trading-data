import unittest

from data_runtime.provider_policy import ProviderPolicyError, require_provider_execution_allowed


class ProviderPolicyTests(unittest.TestCase):
    def test_missing_manager_controls_fails_closed(self):
        with self.assertRaisesRegex(ProviderPolicyError, "live provider calls are not allowed"):
            require_provider_execution_allowed({}, provider="alpaca", endpoint_family="bars")

    def test_allowed_provider_policy_returns_summary(self):
        policy = require_provider_execution_allowed(
            {
                "manager_controls": {
                    "allow_live_provider_calls": True,
                    "autonomous_historical_provider_acquisition": True,
                    "allowed_providers": ["alpaca"],
                    "allowed_endpoint_families": ["bars"],
                    "max_requests": 10,
                    "max_rows": 100,
                    "max_symbols": 5,
                    "timeout_seconds": 20,
                    "retry_policy_ref": "retry_policy_test",
                    "rate_limit_policy_ref": "rate_limit_policy_test",
                }
            },
            provider="alpaca",
            endpoint_family="bars",
            requested_requests=2,
            requested_rows=50,
            requested_symbols=3,
        )
        self.assertEqual(policy.summary_row()["contract_type"], "provider_execution_policy")
        self.assertEqual(policy.max_rows, 100)

    def test_limit_excess_fails_closed(self):
        task_key = {
            "manager_controls": {
                "allow_live_provider_calls": True,
                "autonomous_historical_provider_acquisition": True,
                "allowed_providers": "*",
                "allowed_endpoint_families": "*",
                "max_symbols": 1,
            }
        }
        with self.assertRaisesRegex(ProviderPolicyError, "requested symbols exceeds"):
            require_provider_execution_allowed(task_key, provider="alpaca", endpoint_family="bars", requested_symbols=2)

    def test_max_time_window_excess_fails_closed(self):
        task_key = {
            "manager_controls": {
                "allow_live_provider_calls": True,
                "autonomous_historical_provider_acquisition": True,
                "allowed_providers": "*",
                "allowed_endpoint_families": "*",
                "max_time_window": "31d",
            }
        }
        with self.assertRaisesRegex(ProviderPolicyError, "requested time window exceeds"):
            require_provider_execution_allowed(
                task_key,
                provider="alpaca",
                endpoint_family="bars",
                requested_start="2026-01-01T00:00:00Z",
                requested_end="2026-02-02T00:00:00Z",
            )

    def test_max_time_window_allows_simple_and_iso_durations(self):
        for duration in ("31d", "P31D", "1mo"):
            task_key = {
                "manager_controls": {
                    "allow_live_provider_calls": True,
                    "autonomous_historical_provider_acquisition": True,
                    "allowed_providers": "*",
                    "allowed_endpoint_families": "*",
                    "max_time_window": duration,
                }
            }
            policy = require_provider_execution_allowed(
                task_key,
                provider="alpaca",
                endpoint_family="bars",
                requested_start="2026-01-01T00:00:00Z",
                requested_end="2026-02-01T00:00:00Z",
            )
            self.assertEqual(policy.max_time_window, duration)


if __name__ == "__main__":
    unittest.main()
