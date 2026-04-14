import random
import unittest

from ltx_payload_builder import build_payload, seconds_to_frames


class TestLtxPayloadBuilder(unittest.TestCase):
    def test_seconds_to_frames_uses_ltx_formula(self) -> None:
        self.assertEqual(seconds_to_frames(5), 121)
        self.assertEqual(seconds_to_frames(1), 25)

    def test_build_payload_updates_workflow_template(self) -> None:
        payload = build_payload(
            prompt="A camera push-in through a neon alley.",
            seconds=5,
            aspect_ratio="9:16",
            image_name="My Scene Final.png",
            image_data_url="data:image/png;base64,AAAA",
            optimize_prompt=False,
            rng=random.Random(7),
        )

        workflow = payload["input"]["workflow"]
        image = payload["input"]["images"][0]

        self.assertEqual(workflow["267:266"]["inputs"]["value"], "A camera push-in through a neon alley.")
        self.assertEqual(workflow["267:225"]["inputs"]["value"], 121)
        self.assertEqual(workflow["267:257"]["inputs"]["value"], 720)
        self.assertEqual(workflow["267:258"]["inputs"]["value"], 1280)
        self.assertEqual(workflow["267:260"]["inputs"]["value"], 24)
        self.assertEqual(workflow["267:274"]["inputs"]["sampling_mode"], "off")
        self.assertEqual(workflow["269"]["inputs"]["image"], "My_Scene_Final.png")
        self.assertEqual(image["name"], "My_Scene_Final.png")
        self.assertEqual(image["image"], "data:image/png;base64,AAAA")


if __name__ == "__main__":
    unittest.main()
