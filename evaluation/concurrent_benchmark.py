import asyncio
import aiohttp
import time
import os
import sys

SERVER_IP = os.getenv("SERVER_IP", "10.0.0.15")
PORT = os.getenv("PORT", "30801")
URL = f"http://{SERVER_IP}:{PORT}/v1/tag/upload"
BASE_DIR = os.getenv("BASE_DIR", "/home/ubuntu/AIDC-CTCM-Team2")
N_USERS = int(os.getenv("N_USERS", "3"))

CANDIDATE_FILES = [
    "data/Lecture - Pandas Basics.ipynb",
    "data/Lecture - Decision Trees.ipynb",
    "data/Lecture_ML_Workflow.ipynb",
]

MODELS_TO_TEST = ["qwen", "openai"]

def resolve_files():
    resolved = []
    for f in CANDIDATE_FILES:
        full = os.path.join(BASE_DIR, f)
        if os.path.exists(full):
            resolved.append(full)
        elif os.path.exists(f):
            resolved.append(f)
        else:
            print(f"[WARNING] not found: {f}")
    return resolved

async def send_request(session, filepath, model_name, user_id):
    filename = os.path.basename(filepath)
    with open(filepath, 'rb') as f:
        file_bytes = f.read()
    data = aiohttp.FormData()
    data.add_field('file', file_bytes, filename=filename)
    data.add_field('model', model_name)
    t0 = time.perf_counter()
    try:
        async with session.post(
            URL, data=data,
            timeout=aiohttp.ClientTimeout(total=600)
        ) as resp:
            await resp.json()
            latency = time.perf_counter() - t0
            ok = resp.status == 200
            print(f"  [User {user_id}] {filename:<35} | {latency:.1f}s | {'OK' if ok else 'ERR'}")
            return latency, ok
    except Exception as e:
        latency = time.perf_counter() - t0
        print(f"  [User {user_id}] {filename:<35} | {latency:.1f}s | FAIL ({e.__class__.__name__})")
        return latency, False

async def user_session(session, files, user_id, model):
    results = []
    for f in files:
        lat, ok = await send_request(session, f, model, user_id)
        results.append((lat, ok))
    return results

async def run_model(session, model, files, n_users):
    print(f"\n{'='*65}")
    print(f"MODEL: [{model.upper()}] — {n_users} users × {len(files)} files")
    print(f"{'='*65}")

    print(f"Baseline (1 user sequential)...")
    t0 = time.perf_counter()
    baseline_results = []
    for f in files:
        lat, ok = await send_request(session, f, model, 0)
        baseline_results.append((lat, ok))
    seq_time = time.perf_counter() - t0
    seq_avg = sum(l for l, _ in baseline_results) / len(baseline_results) if baseline_results else 0
    print(f"  sequential total: {seq_time:.1f}s | avg/file: {seq_avg:.1f}s")

    await asyncio.sleep(10)

    print(f"\nConcurrent ({n_users} users)...")
    t0 = time.perf_counter()
    tasks = [user_session(session, files, i+1, model) for i in range(n_users)]
    all_results = await asyncio.gather(*tasks)
    wall = time.perf_counter() - t0

    flat = [(l, ok) for user in all_results for l, ok in user]
    success = sum(1 for _, ok in flat if ok)
    total = len(flat)
    latencies = [l for l, ok in flat if ok]
    avg_lat = sum(latencies) / len(latencies) if latencies else 0
    speedup = (seq_time * n_users) / wall if wall > 0 else 0
    throughput = success / wall * 3600 if wall > 0 else 0

    print(f"\n--- [{model}] results ---")
    print(f"success:           {success}/{total}")
    print(f"wall time:         {wall:.1f}s")
    print(f"avg latency/file:  {avg_lat:.1f}s")
    print(f"sequential est:    {seq_time * n_users:.1f}s ({seq_time:.1f}s × {n_users})")
    print(f"speedup:           {speedup:.2f}x")
    print(f"throughput:        {throughput:.0f} files/hr")

    return {
        "model": model,
        "success": f"{success}/{total}",
        "seq_time": seq_time,
        "wall": wall,
        "speedup": speedup,
        "throughput": throughput,
    }

async def main():
    files = resolve_files()
    if not files:
        print("[ERROR] no files found")
        sys.exit(1)

    print(f"Server:  {URL}")
    print(f"Users:   {N_USERS}")
    print(f"Files:   {[os.path.basename(f) for f in files]}")
    print(f"Models:  {MODELS_TO_TEST}")

    conn = aiohttp.TCPConnector(limit=30)
    async with aiohttp.ClientSession(connector=conn) as session:
        summary = []
        for model in MODELS_TO_TEST:
            r = await run_model(session, model, files, N_USERS)
            summary.append(r)
            await asyncio.sleep(15)

    print(f"\n\n{'='*75}")
    print("CONCURRENT BENCHMARK SUMMARY")
    print(f"{'='*75}")
    print(f"{'Model':<10} | {'Success':<8} | {'Seq (1 user)':<14} | {'Concurrent':<12} | {'Speedup':<9} | {'Throughput'}")
    print("-"*75)
    for s in summary:
        print(f"{s['model']:<10} | {s['success']:<8} | {s['seq_time']:<12.1f}s | {s['wall']:<10.1f}s | {s['speedup']:<7.2f}x | {s['throughput']:.0f} files/hr")
    print("="*75)

if __name__ == "__main__":
    asyncio.run(main())
