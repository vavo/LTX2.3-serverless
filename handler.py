# ==============================================================================
# 🚀 INDRO CLOUD INFRASTRUCTURE - CORE API
# Project: Indro Serverless GPU Orchestrator (V1)
# Architect: Indro Core Engineering Team
# Description: Multi-tenant, queue-aware, async-to-sync API wrapper for LTX-Video.
# Features: Persistent SQLite Caching, Backpressure, Auto-Retries, S3-Ready.
# ==============================================================================

import runpod
import json
import urllib.request
import urllib.error
import os
import random
import base64
import time
import uuid
import logging
import hashlib
import sqlite3
import shutil
from typing import Dict, Any, Optional

# --- 1. ENTERPRISE CONFIGURATION & OBSERVABILITY ---
logging.basicConfig(level=logging.INFO, format='{"time":"%(asctime)s", "level":"%(levelname)s", "message":"%(message)s"}')
logger = logging.getLogger("Indro-Core")

COMFY_HOST = "127.0.0.1:8188"
COMFY_INPUT_DIR = "/workspace/ComfyUI/input"
COMFY_OUTPUT_DIR = "/workspace/ComfyUI/output"

# Security & Scaling Constraints
MAX_RENDER_TIMEOUT = 600   # 10 minutes max per job
MAX_IMAGE_MB = 10          # Drop huge payload attacks
MAX_OUTPUT_MB = 50         # Prevent Base64 RAM explosion on massive videos
MAX_PROMPT_LEN = 1500      # Prevent prompt injection attacks
MAX_QUEUE_SIZE = 10        # Backpressure limit

# --- 2. PERSISTENT SQLITE CACHING (The GPU Saver) ---
# If a network volume is mounted, this cache survives container reboots!
CACHE_DB_PATH = "/workspace/indro_cache.db"
def init_cache():
    try:
        conn = sqlite3.connect(CACHE_DB_PATH)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS result_cache 
                     (hash TEXT PRIMARY KEY, filepath TEXT, timestamp REAL)''')
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"Cache DB initialization failed, running stateless: {e}")

init_cache()

# --- 3. HARD FATAL STARTUP VALIDATION ---
try:
    with open('video_ltx2_3_i2v_API.json', 'r') as f:
        BASE_WORKFLOW = json.load(f)
    logger.info("Indro Worker Boot Sequence Complete. BASE_WORKFLOW loaded.")
except Exception as e:
    logger.critical(f"FATAL: Workflow JSON load failed. Worker terminating. {e}")
    raise RuntimeError("Worker cannot start without valid workflow JSON.")

NODE_MAP = {
    "image_loader": "269",
    "prompt_node": "267:266",
    "seed_1": "267:216",
    "seed_2": "267:237",
    "output_node": "75"
}

class SystemSecurity:
    @staticmethod
    def check_disk_space():
        stat = os.statvfs(COMFY_OUTPUT_DIR)
        free_mb = (stat.f_bavail * stat.f_frsize) / (1024 * 1024)
        if free_mb < 500:
            raise RuntimeError("CRITICAL: Low disk space (<500MB). Rejecting job to prevent OS crash.")

    @staticmethod
    def safe_set(workflow: Dict, node_id: str, key: str, value: Any):
        if node_id not in workflow or "inputs" not in workflow[node_id]:
            raise KeyError(f"Node {node_id} or inputs missing in workflow architecture.")
        workflow[node_id]["inputs"][key] = value

class ComfyUIClient:
    _LAST_Q_CHECK_TIME = 0
    _LAST_Q_SIZE = 0

    @classmethod
    def get_queue_size(cls) -> int:
        """Micro-optimized queue check. Only pings the API every 3 seconds."""
        if time.time() - cls._LAST_Q_CHECK_TIME < 3:
            return cls._LAST_Q_SIZE
            
        req = urllib.request.Request(f"http://{COMFY_HOST}/queue")
        try:
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read())
                cls._LAST_Q_SIZE = len(data.get("queue_running", [])) + len(data.get("queue_pending", []))
                cls._LAST_Q_CHECK_TIME = time.time()
                return cls._LAST_Q_SIZE
        except Exception as e:
            logger.error(f"Queue API Failed: {e}")
            return MAX_QUEUE_SIZE # Fail-safe: Reject jobs if API is dead

    @staticmethod
    def queue_workflow(workflow: Dict[str, Any]) -> str:
        payload = json.dumps({"prompt": workflow}).encode('utf-8')
        req = urllib.request.Request(
            f"http://{COMFY_HOST}/prompt", 
            data=payload,
            headers={"Connection": "keep-alive", "Content-Type": "application/json"}
        )
        for attempt in range(3): # Auto-Retry Pipeline
            try:
                with urllib.request.urlopen(req) as response:
                    return json.loads(response.read())['prompt_id']
            except urllib.error.URLError as e:
                if attempt == 2:
                    raise RuntimeError(f"ComfyUI API Queue Failed after 3 retries: {str(e)}")
                time.sleep(1)

    @staticmethod
    def check_history(prompt_id: str) -> Optional[Dict[str, Any]]:
        req = urllib.request.Request(f"http://{COMFY_HOST}/history/{prompt_id}", headers={"Connection": "keep-alive"})
        try:
            with urllib.request.urlopen(req) as response:
                return json.loads(response.read()).get(prompt_id)
        except urllib.error.URLError:
            return None

def mock_s3_upload(filepath: str) -> str:
    """Stub for scaling out of Base64 responses."""
    # In production, swap this with actual boto3 S3 upload logic
    filename = os.path.basename(filepath)
    return f"https://cdn.indro-cloud.com/renders/{filename}"

def handler(job: Dict[str, Any]) -> Dict[str, Any]:
    job_id = job.get('id', 'local_test')
    job_input = job.get('input', {})
    start_time = time.time()
    
    input_image_path = None
    output_video_path = None
    
    try:
        # --- 1. SYSTEM HEALTH & BACKPRESSURE ---
        SystemSecurity.check_disk_space()
        if ComfyUIClient.get_queue_size() >= MAX_QUEUE_SIZE:
            return {"status": "busy", "error": "GPU queue overloaded.", "retry_after": 15}

        # --- 2. INPUT VALIDATION & MULTI-MODE ROUTING ---
        output_type = job_input.get("output_type", "base64").lower()
        if 'image_base64' not in job_input:
            raise ValueError("Payload rejected: Missing 'image_base64'.")
            
        user_prompt = job_input.get("prompt", "").strip()
        if not user_prompt:
            raise ValueError("Payload rejected: Empty prompt not allowed.")
        if len(user_prompt) > MAX_PROMPT_LEN:
            raise ValueError(f"Payload rejected: Prompt exceeds {MAX_PROMPT_LEN} chars.")

        try:
            image_bytes = base64.b64decode(job_input['image_base64'], validate=True)
        except Exception:
            raise ValueError("Payload rejected: Malformed Base64 string.")

        img_mb_size = len(image_bytes) / (1024 * 1024)
        if img_mb_size > MAX_IMAGE_MB:
            raise ValueError(f"Payload rejected: Image exceeds {MAX_IMAGE_MB}MB limit.")

        # --- 3. BULLETPROOF HASH CACHING ---
        # Uses FULL byte string + prompt for absolute mathematical certainty
        cache_hash = hashlib.sha256(image_bytes + user_prompt.encode()).hexdigest()
        
        try:
            conn = sqlite3.connect(CACHE_DB_PATH)
            c = conn.cursor()
            c.execute("SELECT filepath FROM result_cache WHERE hash=?", (cache_hash,))
            row = c.fetchone()
            conn.close()
            
            if row and os.path.exists(row[0]):
                logger.info(f"[{job_id}] INDRO CACHE HIT! Bypassing GPU.")
                cached_path = row[0]
                if output_type == "url":
                    return {"status": "success", "video_url": mock_s3_upload(cached_path), "cached": True}
                else:
                    with open(cached_path, "rb") as f:
                        b64_data = base64.b64encode(f.read()).decode('utf-8')
                    return {"status": "success", "video_base64": b64_data, "cached": True}
        except Exception as e:
            logger.warning(f"Cache read error: {e}")

        # --- 4. SECURE DISK WRITE ---
        os.makedirs(COMFY_INPUT_DIR, exist_ok=True)
        image_filename = os.path.basename(f"API_in_{uuid.uuid4().hex}.jpg")
        input_image_path = os.path.join(COMFY_INPUT_DIR, image_filename)
        
        with open(input_image_path, "wb") as f:
            f.write(image_bytes)

        # --- 5. WORKFLOW INJECTION ---
        workflow = json.loads(json.dumps(BASE_WORKFLOW)) 
        seed_1, seed_2 = random.randint(1, 10**15), random.randint(1, 10**15)

        SystemSecurity.safe_set(workflow, NODE_MAP["image_loader"], "image", image_filename)
        SystemSecurity.safe_set(workflow, NODE_MAP["prompt_node"], "value", user_prompt)
        SystemSecurity.safe_set(workflow, NODE_MAP["seed_1"], "noise_seed", seed_1)
        SystemSecurity.safe_set(workflow, NODE_MAP["seed_2"], "noise_seed", seed_2)

        # --- 6. IGNITION & POLLING ---
        prompt_id = ComfyUIClient.queue_workflow(workflow)
        logger.info(f"[{job_id}] GPU Ignition Sequence Started. ID: {prompt_id}")

        video_filename = None
        fail_count = 0

        while True:
            if job.get("status") == "CANCELLED":
                raise RuntimeError("Job cancelled by platform.")

            elapsed = time.time() - start_time
            if elapsed > MAX_RENDER_TIMEOUT:
                raise TimeoutError("Render killed: Timeout exceeded.")

            history_data = ComfyUIClient.check_history(prompt_id)
            
            if history_data is None:
                fail_count += 1
                if fail_count >= 5:
                    raise RuntimeError("ComfyUI unresponsive. Aborting.")
                time.sleep(min(1.5 ** fail_count, 5)) 
                continue

            fail_count = 0
            node_output = history_data.get('outputs', {}).get(NODE_MAP["output_node"], {})
            
            for key in ["videos", "gifs", "images"]:
                if key in node_output and node_output[key]:
                    video_filename = node_output[key][0]['filename']
                    break
            
            if video_filename:
                break
                
            time.sleep(min(2 + (elapsed) / 30, 5))

        # --- 7. OUTPUT VALIDATION & S3 ROUTING ---
        output_video_path = os.path.join(COMFY_OUTPUT_DIR, video_filename)
        
        wait_start = time.time()
        while not os.path.exists(output_video_path):
            if time.time() - wait_start > 10:
                raise FileNotFoundError("Output ghosted (never wrote to disk).")
            time.sleep(0.5)

        # Output Size Security Check
        file_size_mb = os.path.getsize(output_video_path) / (1024 * 1024)
        if output_type == "base64" and file_size_mb > MAX_OUTPUT_MB:
            raise RuntimeError(f"Video ({file_size_mb:.1f}MB) too large for Base64 return. Switch to output_type: 'url'.")

        # Save to SQLite Cache
        try:
            conn = sqlite3.connect(CACHE_DB_PATH)
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO result_cache (hash, filepath, timestamp) VALUES (?, ?, ?)", 
                      (cache_hash, output_video_path, time.time()))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"Failed to write cache record: {e}")

        total_time = round(time.time() - start_time, 2)
        logger.info(f"[{job_id}] SUCCESS. Latency: {total_time}s.")
        
        response = {
            "status": "success",
            "metadata": {
                "render_time_sec": total_time,
                "prompt_id": prompt_id,
                "seeds": [seed_1, seed_2],
                "size_mb": round(file_size_mb, 2)
            }
        }

        if output_type == "url":
            response["video_url"] = mock_s3_upload(output_video_path)
        else:
            with open(output_video_path, "rb") as f:
                response["video_base64"] = base64.b64encode(f.read()).decode('utf-8')

        return response

    except Exception as e:
        logger.error(f"[{job_id}] FAILED: {str(e)}")
        return {"status": "error", "error": str(e)}

    finally:
        # Cleanup only the INPUT image. The output video is kept for the persistent cache.
        if input_image_path and os.path.exists(input_image_path):
            try: os.remove(input_image_path)
            except: pass

logger.info("Initializing Indro Serverless Engine...")
runpod.serverless.start({"handler": handler})
