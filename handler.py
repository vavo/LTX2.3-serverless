# ==============================================================================
# 🚀 INDRO STUDIO CLOUD - V5 GOD-TIER ENGINE
# Architect: Indro Core Engineering Team
# Features: 
#   - Distributed Circuit Breakers & Seamless Node Failover
#   - UUID-Safe Mutex Locks (Zero Deadlock)
#   - VIP Rate Limiting & Priority Queue Routing
#   - Real-Time Telemetry State Injection (for Frontend Progress Bars)
#   - Auto-Prompt Cinematic Enhancement & NSFW Filtering
# ==============================================================================

import runpod
import json
import os
import random
import time
import uuid
import logging
import hashlib
import asyncio
import aiohttp
import boto3
from urllib.parse import urlparse
from botocore.exceptions import ClientError
from botocore.config import Config
import redis.asyncio as redis

# --- 1. ENTERPRISE OBSERVABILITY & SECURITY ---
logging.basicConfig(level=logging.INFO, format='{"time":"%(asctime)s", "level":"%(levelname)s", "message":"%(message)s"}')
logger = logging.getLogger("Indro-V5")

API_KEY_SECRET = os.environ.get("INDRO_API_KEY", "dev_token_123")
NSFW_BANNED_WORDS = {"nude", "nsfw", "blood", "gore", "explicit", "kill"} # Basic proxy for safety

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
redis_client = redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=5, retry_on_timeout=True)

COMFY_NODES = os.environ.get("COMFY_NODES", "127.0.0.1:8188").split(",")
COMFY_INPUT_DIR = "/workspace/ComfyUI/input"
COMFY_OUTPUT_DIR = "/workspace/ComfyUI/output"

try:
    with open('video_ltx2_3_i2v_API.json', 'r') as f:
        BASE_WORKFLOW = json.load(f)
except:
    raise RuntimeError("Worker cannot start without workflow JSON.")

NODE_MAP = {"image": "269", "prompt": "267:266", "seed1": "267:216", "seed2": "267:237", "output": "75"}

# --- 2. ADVANCED AI LOGIC ---
class AIEngine:
    @staticmethod
    def enhance_prompt(prompt: str) -> str:
        """Auto-injects cinematic modifiers if the user provides a lazy prompt."""
        if len(prompt.split()) < 5:
            return f"{prompt}, cinematic lighting, highly detailed, 8k resolution, unreal engine 5 render, photorealistic, masterpiece"
        return prompt

    @staticmethod
    def safety_check(prompt: str) -> bool:
        prompt_lower = prompt.lower()
        return not any(word in prompt_lower for word in NSFW_BANNED_WORDS)

# --- 3. THE DISTRIBUTED CIRCUIT BREAKER (My Custom Addition) ---
class GPUFleetManager:
    @staticmethod
    async def get_best_node(session: aiohttp.ClientSession, is_vip: bool) -> str:
        """Finds the least busy GPU. Skips 'DEAD' nodes using the Circuit Breaker."""
        best_node = None
        min_queue = 999
        max_q_limit = 15 if is_vip else 5 # VIP users bypass standard queue caps
        
        for node in COMFY_NODES:
            # CIRCUIT BREAKER: Check if node is flagged as dead in Redis
            if await redis_client.get(f"circuit_breaker:{node}"):
                continue 

            try:
                async with session.get(f"http://{node}/queue", timeout=1.5) as resp:
                    data = await resp.json()
                    q_size = len(data.get("queue_running", [])) + len(data.get("queue_pending", []))
                    if q_size < min_queue:
                        min_queue = q_size
                        best_node = node
            except Exception:
                # Flag node as DEAD for 60 seconds if it fails to respond
                await redis_client.setex(f"circuit_breaker:{node}", 60, "DEAD")
                logger.warning(f"CIRCUIT BREAKER TRIPPED: {node} flagged as offline.")
                
        if not best_node or min_queue >= max_q_limit:
            raise RuntimeError("FLEET OVERLOAD: All GPUs are busy or offline.")
        return best_node

# --- 4. CLOUD NATIVE STORAGE ---
async def upload_to_s3_with_retry(filepath: str, job_id: str) -> str:
    bucket = os.environ.get("AWS_BUCKET_NAME")
    if not bucket: raise RuntimeError("AWS_BUCKET_NAME missing.")
    
    boto_config = Config(retries={'max_attempts': 3, 'mode': 'standard'})
    def _upload():
        s3 = boto3.client('s3', config=boto_config)
        filename = f"renders/{job_id}.mp4"
        s3.upload_file(filepath, bucket, filename, ExtraArgs={'ContentType': 'video/mp4'})
        return s3.generate_presigned_url('get_object', Params={'Bucket': bucket, 'Key': filename}, ExpiresIn=604800)
    
    for attempt in range(3):
        try: return await asyncio.to_thread(_upload)
        except Exception as e:
            if attempt == 2: raise e
            await asyncio.sleep(2 ** attempt)

# --- 5. THE MASTER HANDLER ---
async def handler(job: dict) -> dict:
    job_id = job.get('id', uuid.uuid4().hex)
    job_input = job.get('input', {})
    start_time = time.time()
    
    # TELEMETRY: Announce Job Start
    await redis_client.hset(f"job_status:{job_id}", mapping={"status": "initializing", "progress": "0%"})
    await redis_client.expire(f"job_status:{job_id}", 3600)

    try:
        # 1. VIP Routing & Security
        api_key = job_input.get("api_key")
        if api_key != API_KEY_SECRET:
            raise PermissionError("401 Unauthorized")
            
        priority = job_input.get("priority", "standard")
        is_vip = priority == "vip"

        # 2. Redis Token-Bucket Rate Limiting
        rate_key = f"rate_limit:{api_key}"
        req_count = await redis_client.incr(rate_key)
        if req_count == 1: await redis_client.expire(rate_key, 60) # 60 sec rolling window
        limit = 50 if is_vip else 10
        if req_count > limit:
            raise PermissionError("429 Too Many Requests. Rate Limit Exceeded.")

        # 3. Input Validation & AI Enhancement
        raw_prompt = job_input.get("prompt", "")
        image_url = job_input.get("image_url", "")
        if not image_url or not raw_prompt:
            raise ValueError("Missing 'image_url' or 'prompt'.")
            
        if not AIEngine.safety_check(raw_prompt):
            raise ValueError("Prompt violates safety protocols.")

        enhanced_prompt = AIEngine.enhance_prompt(raw_prompt)

        # 4. UUID-Safe Mutex Lock (Fixes Redis Race Condition)
        cache_hash = hashlib.sha256(f"{image_url}_{enhanced_prompt}".encode()).hexdigest()
        lock_token = str(uuid.uuid4()) # Unique token for THIS specific worker

        redis_state = await redis_client.get(cache_hash)
        if redis_state and redis_state.startswith("http"):
            await redis_client.hset(f"job_status:{job_id}", mapping={"status": "completed", "cache_hit": "true"})
            return {"status": "success", "video_url": redis_state, "cached": True}

        # Attempt to acquire lock
        lock_acquired = await redis_client.set(cache_hash, lock_token, ex=1200, nx=True)
        if not lock_acquired:
            logger.info(f"[{job_id}] DEDUPLICATION ACTIVE. Waiting...")
            await redis_client.hset(f"job_status:{job_id}", mapping={"status": "waiting_in_queue"})
            for _ in range(240):
                await asyncio.sleep(5)
                new_state = await redis_client.get(cache_hash)
                if new_state and new_state.startswith("http"):
                    return {"status": "success", "video_url": new_state, "cached": True}
            raise TimeoutError("Deduplication timeout.")

        http_timeout = aiohttp.ClientTimeout(total=1000)
        async with aiohttp.ClientSession(timeout=http_timeout) as session:
            
            # 5. SEAMLESS FAILOVER ENGINE
            # We will try up to 2 different GPUs if the first one crashes
            target_node = None
            video_filename = None
            
            for failover_attempt in range(2):
                try:
                    target_node = await GPUFleetManager.get_best_node(session, is_vip)
                    await redis_client.hset(f"job_status:{job_id}", mapping={"status": "rendering", "node": target_node})
                    logger.info(f"[{job_id}] Routed to Node: {target_node}")

                    workflow = json.loads(json.dumps(BASE_WORKFLOW))
                    workflow[NODE_MAP["image"]]["inputs"]["image"] = image_url
                    workflow[NODE_MAP["prompt"]]["inputs"]["value"] = enhanced_prompt
                    workflow[NODE_MAP["seed1"]]["inputs"]["noise_seed"] = random.randint(1, 10**15)
                    workflow[NODE_MAP["seed2"]]["inputs"]["noise_seed"] = random.randint(1, 10**15)

                    async with session.post(f"http://{target_node}/prompt", json={"prompt": workflow}) as resp:
                        prompt_id = (await resp.json())['prompt_id']

                    fail_count = 0
                    while True:
                        elapsed = time.time() - start_time
                        if elapsed > 900: raise TimeoutError("Render timeout.")

                        try:
                            async with session.get(f"http://{target_node}/history/{prompt_id}") as resp:
                                history_data = await resp.json()
                        except Exception:
                            fail_count += 1
                            if fail_count > 5: raise RuntimeError(f"Node {target_node} disconnected.")
                            await asyncio.sleep(2)
                            continue

                        if prompt_id in history_data:
                            node_output = history_data[prompt_id].get('outputs', {}).get(NODE_MAP["output"], {})
                            for key in ["videos", "gifs"]:
                                if key in node_output and node_output[key]:
                                    video_filename = node_output[key][0]['filename']
                                    break
                            if video_filename: break

                        await asyncio.sleep(min(2 + elapsed / 30, 5))
                    
                    break # Break out of failover loop if successful!

                except Exception as e:
                    logger.warning(f"[{job_id}] GPU {target_node} failed. ({str(e)})")
                    await redis_client.setex(f"circuit_breaker:{target_node}", 60, "DEAD")
                    if failover_attempt == 1: raise RuntimeError("All failover attempts exhausted.")
                    logger.info(f"[{job_id}] Initiating Seamless Failover to new GPU...")

            # 6. Upload & Cleanup
            await redis_client.hset(f"job_status:{job_id}", mapping={"status": "uploading"})
            output_video_path = os.path.join(COMFY_OUTPUT_DIR, video_filename)
            s3_url = await upload_to_s3_with_retry(output_video_path, job_id)
            
            # SAFE LOCK RELEASE: Only update Redis if WE still hold the lock
            current_lock = await redis_client.get(cache_hash)
            if current_lock == lock_token:
                await redis_client.set(cache_hash, s3_url, ex=604800)

            await redis_client.hset(f"job_status:{job_id}", mapping={"status": "completed"})
            
            return {
                "status": "success",
                "video_url": s3_url,
                "metadata": {"render_time_sec": round(time.time() - start_time, 2), "node_used": target_node}
            }

    except Exception as e:
        # SAFE LOCK DELETION ON CRASH
        try:
            if 'cache_hash' in locals() and 'lock_token' in locals():
                if await redis_client.get(cache_hash) == lock_token:
                    await redis_client.delete(cache_hash)
        except: pass 
        
        await redis_client.hset(f"job_status:{job_id}", mapping={"status": "failed", "error": str(e)})
        return {"status": "error", "error": str(e)}

logger.info("Initializing Indro Serverless Engine V5 (GOD-TIER)...")
runpod.serverless.start({"handler": handler})
