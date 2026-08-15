import unittest
from unittest.mock import patch

from src.verify_comfy_models import (
    PROMPT_ENHANCER,
    REQUIRED_MODELS,
    missing_models,
    normalize_model_names,
    verify_model_discovery,
)


class TestVerifyComfyModels(unittest.TestCase):
    def test_normalize_model_names_accepts_nested_paths(self) -> None:
        self.assertEqual(
            normalize_model_names(["nested\\model.safetensors"]),
            {"nested/model.safetensors"},
        )

    def test_missing_models_reports_prompt_enhancer(self) -> None:
        listings = {
            folder: set(models) for folder, models in REQUIRED_MODELS.items()
        }

        self.assertEqual(
            missing_models(listings, require_prompt_enhancer=True),
            {"text_encoders": [PROMPT_ENHANCER]},
        )

    def test_live_check_queries_all_required_model_routes(self) -> None:
        listings = {
            folder: set(models) for folder, models in REQUIRED_MODELS.items()
        }
        listings["text_encoders"].add(PROMPT_ENHANCER)

        with patch(
            "src.verify_comfy_models.fetch_listing",
            side_effect=lambda _server, folder, _timeout: listings[folder],
        ) as fetch_listing:
            verify_model_discovery(
                "http://127.0.0.1:8188",
                timeout=1,
                require_prompt_enhancer=True,
            )

        self.assertEqual(
            {call.args[1] for call in fetch_listing.call_args_list},
            set(REQUIRED_MODELS),
        )


if __name__ == "__main__":
    unittest.main()
