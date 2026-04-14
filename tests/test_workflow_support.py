import tempfile
import unittest
from pathlib import Path

from workflow_support import (
    apply_input_filename_map,
    build_output_path,
    build_workflow_cache_key,
    collect_output_entries,
    decode_base64_data,
    safe_input_path,
    write_input_images,
)


class TestWorkflowSupport(unittest.TestCase):
    def test_decode_base64_data_supports_data_urls(self) -> None:
        result = decode_base64_data("data:image/png;base64,dGVzdA==")
        self.assertEqual(result, b"test")

    def test_safe_input_path_rejects_traversal(self) -> None:
        with self.assertRaises(ValueError):
            safe_input_path("/tmp/comfy-input", "../escape.png")

    def test_write_input_images_persists_uploaded_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            written = write_input_images(
                tmp_dir,
                [{"name": "nested/source.png", "image": "dGVzdA=="}],
            )

            self.assertEqual(len(written), 1)
            self.assertEqual(Path(written[0]).read_bytes(), b"test")

    def test_collect_output_entries_extracts_images_and_videos(self) -> None:
        outputs = {
            "a": {"images": [{"filename": "frame.png", "subfolder": "shots"}]},
            "b": {"videos": [{"filename": "clip.mp4", "subfolder": "video"}]},
        }

        entries = collect_output_entries(outputs)

        self.assertEqual(
            entries,
            [
                {
                    "filename": "frame.png",
                    "subfolder": "shots",
                    "media_kind": "image",
                },
                {
                    "filename": "clip.mp4",
                    "subfolder": "video",
                    "media_kind": "video",
                },
            ],
        )

    def test_build_workflow_cache_key_is_stable(self) -> None:
        workflow = {"2": {"inputs": {"x": 1}}}
        images = [{"name": "a.png", "image": "dGVzdA=="}]

        key_a = build_workflow_cache_key(workflow, images)
        key_b = build_workflow_cache_key({"2": {"inputs": {"x": 1}}}, list(images))

        self.assertEqual(key_a, key_b)

    def test_apply_input_filename_map_rewrites_workflow_inputs(self) -> None:
        workflow = {
            "269": {"inputs": {"image": "source.png"}},
            "999": {"inputs": {"items": ["source.png", 1]}},
        }

        updated = apply_input_filename_map(
            workflow,
            {"source.png": "job-123/source.png"},
        )

        self.assertEqual(updated["269"]["inputs"]["image"], "job-123/source.png")
        self.assertEqual(updated["999"]["inputs"]["items"][0], "job-123/source.png")
        self.assertEqual(workflow["269"]["inputs"]["image"], "source.png")

    def test_build_output_path_joins_subfolder(self) -> None:
        result = build_output_path(
            "/tmp/comfy-output",
            {"filename": "clip.mp4", "subfolder": "video", "media_kind": "video"},
        )
        self.assertEqual(result, Path("/tmp/comfy-output/video/clip.mp4").resolve())


if __name__ == "__main__":
    unittest.main()
