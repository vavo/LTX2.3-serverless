import json
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT_DIR / "video_ltx2_5_i2v_API.json"


class TestLtx25Workflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))

    def test_every_workflow_link_targets_an_existing_node(self) -> None:
        missing_references = []
        for node_id, node in self.workflow.items():
            for input_name, value in node.get("inputs", {}).items():
                if (
                    isinstance(value, list)
                    and len(value) == 2
                    and isinstance(value[0], str)
                    and value[0] not in self.workflow
                ):
                    missing_references.append((node_id, input_name, value[0]))

        self.assertEqual(missing_references, [])

    def test_workflow_uses_the_ltx25_int8_stack(self) -> None:
        self.assertEqual(
            self.workflow["398:384"]["inputs"]["unet_name"],
            "ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors",
        )
        self.assertEqual(
            self.workflow["398:387"]["inputs"]["clip_name"],
            "gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors",
        )
        self.assertEqual(
            self.workflow["398:385"]["inputs"]["vae_name"],
            "ltx-2.5-video-vae-bf16.safetensors",
        )
        self.assertEqual(
            self.workflow["398:386"]["inputs"]["vae_name"],
            "ltx-2.5-audio-vae-bf16.safetensors",
        )


if __name__ == "__main__":
    unittest.main()
