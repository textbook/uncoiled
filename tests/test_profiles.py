import os

from uncoiled import get_active_profiles


class TestGetActiveProfiles:
    def test_no_env_var(self) -> None:
        os.environ.pop("UNCOILED_PROFILES", None)
        assert get_active_profiles() == []

    def test_empty_env_var(self) -> None:
        os.environ["UNCOILED_PROFILES"] = ""
        try:
            assert get_active_profiles() == []
        finally:
            del os.environ["UNCOILED_PROFILES"]

    def test_single_profile(self) -> None:
        os.environ["UNCOILED_PROFILES"] = "prod"
        try:
            assert get_active_profiles() == ["prod"]
        finally:
            del os.environ["UNCOILED_PROFILES"]

    def test_multiple_profiles(self) -> None:
        os.environ["UNCOILED_PROFILES"] = "prod,debug"
        try:
            assert get_active_profiles() == ["prod", "debug"]
        finally:
            del os.environ["UNCOILED_PROFILES"]

    def test_whitespace_handling(self) -> None:
        os.environ["UNCOILED_PROFILES"] = " prod , debug "
        try:
            assert get_active_profiles() == ["prod", "debug"]
        finally:
            del os.environ["UNCOILED_PROFILES"]

    def test_trailing_comma(self) -> None:
        os.environ["UNCOILED_PROFILES"] = "prod,"
        try:
            assert get_active_profiles() == ["prod"]
        finally:
            del os.environ["UNCOILED_PROFILES"]
