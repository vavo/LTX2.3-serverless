"""
Network Volume diagnostics for worker-comfyui.

This module provides tools to debug network volume model path issues.
Enable diagnostics by setting NETWORK_VOLUME_DEBUG=true environment variable.
"""

import os


def get_persistent_root():
    """Return the active persistent root used by the worker."""
    configured_root = os.environ.get("WORKSPACE_ROOT")
    if configured_root:
        return configured_root

    if os.path.isdir("/workspace"):
        return "/workspace"

    if os.path.isdir("/runpod-volume"):
        return "/runpod-volume"

    return "/runpod-volume"

# Expected model types and their file extensions
MODEL_TYPES = {
    "checkpoints": [".safetensors", ".ckpt", ".pt", ".pth", ".bin"],
    "clip": [".safetensors", ".pt", ".bin"],
    "clip_vision": [".safetensors", ".pt", ".bin"],
    "configs": [".yaml", ".json"],
    "controlnet": [".safetensors", ".pt", ".pth", ".bin"],
    "embeddings": [".safetensors", ".pt", ".bin"],
    "loras": [".safetensors", ".pt"],
    "upscale_models": [".safetensors", ".pt", ".pth"],
    "vae": [".safetensors", ".pt", ".bin"],
    "unet": [".safetensors", ".pt", ".bin"],
}


def is_network_volume_debug_enabled():
    """Check if network volume debug mode is enabled via environment variable."""
    return os.environ.get("NETWORK_VOLUME_DEBUG", "false").lower() == "true"


def run_network_volume_diagnostics():
    """
    Run comprehensive network volume diagnostics and print helpful output.
    Only runs when NETWORK_VOLUME_DEBUG=true environment variable is set.
    """
    print("=" * 70)
    print("NETWORK VOLUME DIAGNOSTICS (NETWORK_VOLUME_DEBUG=true)")
    print("=" * 70)

    # Check extra_model_paths.yaml
    extra_model_paths_file = "/comfyui/extra_model_paths.yaml"
    print("\n[1] Checking extra_model_paths.yaml configuration...")
    if os.path.isfile(extra_model_paths_file):
        print(f"    ✓ FOUND: {extra_model_paths_file}")
        with open(extra_model_paths_file, "r") as f:
            content = f.read()
            print("\n    Configuration content:")
            for line in content.split("\n"):
                print(f"      {line}")
    else:
        print(f"    ✗ NOT FOUND: {extra_model_paths_file}")
        print(
            "    This file is required for ComfyUI to find models on the network volume."
        )

    # Check network volume mount
    persistent_root = get_persistent_root()
    print(f"\n[2] Checking network volume mount at {persistent_root}...")
    if os.path.isdir(persistent_root):
        print(f"    ✓ MOUNTED: {persistent_root}")
    else:
        print(f"    ✗ NOT MOUNTED: {persistent_root}")
        print(
            "    Make sure you have attached a network volume to your serverless endpoint."
        )
        print("=" * 70)
        return

    # Check directory structure
    print("\n[3] Checking directory structure...")
    models_dir = os.path.join(persistent_root, "models")
    if os.path.isdir(models_dir):
        print(f"    ✓ FOUND: {models_dir}")
    else:
        print(f"    ✗ NOT FOUND: {models_dir}")
        print("\n    ⚠️  PROBLEM: The 'models' directory does not exist!")
        print("    You need to create the following structure on your network volume:")
        print_expected_structure()
        print("=" * 70)
        return

    # List model directories and their contents
    print("\n[4] Scanning model directories...")
    found_any_models = False

    for model_type, extensions in MODEL_TYPES.items():
        model_path = os.path.join(models_dir, model_type)
        if os.path.isdir(model_path):
            files = []
            try:
                for f in os.listdir(model_path):
                    file_path = os.path.join(model_path, f)
                    if os.path.isfile(file_path):
                        # Check if file has valid extension
                        ext = os.path.splitext(f)[1].lower()
                        if ext in extensions:
                            size = os.path.getsize(file_path)
                            size_str = format_size(size)
                            files.append(f"{f} ({size_str})")
                            found_any_models = True
                        else:
                            files.append(f"{f} (⚠️ ignored - invalid extension)")
            except Exception as e:
                print(f"    {model_type}/: Error reading directory - {e}")
                continue

            if files:
                print(f"\n    {model_type}/:")
                for f in files:
                    print(f"      - {f}")
            else:
                print(f"\n    {model_type}/: (empty)")
        else:
            print(f"\n    {model_type}/: (directory not found)")

    # Summary
    print("\n[5] Summary")
    if found_any_models:
        print("    ✓ Models found on network volume!")
        print("    ComfyUI should be able to load these models.")
    else:
        print("    ⚠️  No valid model files found on network volume!")
        print("\n    Make sure your models have the correct file extensions:")
        print("    - Checkpoints: .safetensors, .ckpt, .pt, .pth, .bin")
        print("    - LoRAs: .safetensors, .pt")
        print("    - VAE: .safetensors, .pt, .bin")
        print("    - etc.")

    print_expected_structure()
    print("=" * 70)


def print_expected_structure():
    """Print the expected directory structure for the network volume."""
    print("\n    Expected directory structure:")
    print("    <persistent-root>/")
    print("    └── models/")
    print("        ├── checkpoints/    <- Put your .safetensors/.ckpt models here")
    print("        ├── loras/          <- Put your LoRA files here")
    print("        ├── vae/            <- Put your VAE files here")
    print("        ├── clip/           <- Put your CLIP models here")
    print("        ├── controlnet/     <- Put your ControlNet models here")
    print("        ├── embeddings/     <- Put your embedding files here")
    print("        └── upscale_models/ <- Put your upscale models here")


def format_size(size_bytes):
    """Format bytes into human-readable size."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"

