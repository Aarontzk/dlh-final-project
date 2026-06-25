"""Bronze BMKG Pipeline - Fetch weather data from BMKG API per ADM4 code"""

import sys
import json
import time
import hashlib
import argparse
import threading
from pathlib import Path
from typing import Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import BMKG_API_BASE, ADM4_FILE, RATE_LIMIT, BRONZE_DIR, PIPELINE
from logger import setup_logger

logger = setup_logger(__name__)


class BMKGBronzePipeline:
    def __init__(self, workers: int = 1, adm4file: str = None):
        self.api_base = BMKG_API_BASE
        self.timeout = RATE_LIMIT["timeout"]
        self.rate_limit = RATE_LIMIT
        self.workers = workers
        self._lock = threading.Lock()
        self.stats = {"total": 0, "success": 0, "failed": 0, "skipped": 0}
        self.failed_codes = []
        self.checksums = {}

        if adm4file:
            p = Path(adm4file)
            self.adm4_file = p if p.is_absolute() else ADM4_FILE.parent / p
        else:
            self.adm4_file = ADM4_FILE

        """Versioning pengambilan data"""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_dir = BRONZE_DIR / "bmkg" / ts
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.checksums_file = BRONZE_DIR / "checksums.json"
        self._load_checksums()

    def _load_checksums(self):
        if self.checksums_file.exists():
            with open(self.checksums_file, "r") as f:
                self.checksums = json.load(f)
            logger.info(f"Loaded {len(self.checksums)} existing checksums")

    def _save_checksums(self):
        with open(self.checksums_file, "w") as f:
            json.dump(self.checksums, f)

    def _calculate_md5(self, data: str) -> str:
        return hashlib.md5(data.encode()).hexdigest()

    def _fetch_with_retry(self, adm4_code: str) -> Optional[Dict]:
        url = f"{self.api_base}?adm4={adm4_code}"

        for attempt in range(self.rate_limit["max_retries"]):
            try:
                response = requests.get(url, timeout=self.timeout)

                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 404:
                    logger.debug(f"{adm4_code}: Not found (404)")
                    return None
                elif response.status_code == 429:
                    logger.warning(f"{adm4_code}: Rate limited, attempt {attempt+1}/{self.rate_limit['max_retries']}")
                    if attempt < self.rate_limit["max_retries"] - 1:
                        time.sleep(5 + (self.rate_limit["backoff_factor"] ** attempt))
                else:
                    logger.warning(f"{adm4_code}: HTTP {response.status_code}")

            except requests.Timeout:
                logger.warning(f"{adm4_code}: Timeout (attempt {attempt+1})")
            except requests.RequestException as e:
                logger.warning(f"{adm4_code}: {type(e).__name__} (attempt {attempt+1})")

            if attempt < self.rate_limit["max_retries"] - 1:
                time.sleep(self.rate_limit["delay"] * (self.rate_limit["backoff_factor"] ** attempt))

        return None

    def _save_json(self, adm4_code: str, data: Dict):
        file_path = self.output_dir / f"{adm4_code}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        checksum = self._calculate_md5(json.dumps(data, sort_keys=True))
        with self._lock:
            self.checksums[adm4_code] = checksum

    def process_adm4(self, adm4_code: str) -> bool:
        with self._lock:
            self.stats["total"] += 1
            already_done = PIPELINE["skip_existing"] and adm4_code in self.checksums

        """"idempotensi"""
        if already_done:
            with self._lock:
                self.stats["skipped"] += 1
            return True

        time.sleep(self.rate_limit["delay"])
        data = self._fetch_with_retry(adm4_code)

        if data:
            self._save_json(adm4_code, data)
            with self._lock:
                self.stats["success"] += 1
            logger.info(f"[OK] {adm4_code}")
            return True
        else:
            with self._lock:
                self.stats["failed"] += 1
                self.failed_codes.append(adm4_code)
            logger.warning(f"[FAIL] {adm4_code}")
            return False

    def run(self):
        logger.info("=" * 60)
        logger.info(f"BMKG Bronze Pipeline | Workers: {self.workers}")
        logger.info("=" * 60)

        if not self.adm4_file.exists():
            logger.error(f"ADM4 file not found: {self.adm4_file}")
            return

        logger.info(f"ADM4 file: {self.adm4_file}")
        with open(self.adm4_file, "r") as f:
            codes = [
                line.strip() for line in f
                if line.strip() and not line.startswith("#") and line.strip().count(".") == 3
            ]

        logger.info(f"Loaded {len(codes)} codes")
        start_time = time.time()

        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            futures = {executor.submit(self.process_adm4, code): code for code in codes}

            done = 0
            for future in as_completed(futures):
                done += 1
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Unhandled error for {futures[future]}: {e}")

                if done % 100 == 0:
                    elapsed = time.time() - start_time
                    rate = done / elapsed if elapsed > 0 else 0
                    eta = (len(codes) - done) / rate if rate > 0 else 0
                    logger.info(f"Progress: {done}/{len(codes)} | {rate:.1f} req/s | ETA: {eta:.0f}s")

        self._save_checksums()

        elapsed = time.time() - start_time
        logger.info("=" * 60)
        logger.info(f"Complete! Success: {self.stats['success']} | Failed: {self.stats['failed']} | Skipped: {self.stats['skipped']}")
        logger.info(f"Elapsed: {elapsed:.1f}s ({elapsed/60:.1f}m)")
        logger.info(f"Output: {self.output_dir}")
        logger.info("=" * 60)

        if self.failed_codes and PIPELINE["save_failed_codes"]:
            failed_file = BRONZE_DIR / "failed_codes.txt"
            with open(failed_file, "w") as f:
                for code in self.failed_codes:
                    f.write(f"{code}\n")
            logger.info(f"Failed codes: {failed_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BMKG Bronze Pipeline")
    parser.add_argument("--workers", type=int, default=1, help="Concurrent workers")
    parser.add_argument("--adm4file", type=str, default=None, help="Path to ADM4 file (overrides config)")
    args = parser.parse_args()

    pipeline = BMKGBronzePipeline(workers=args.workers, adm4file=args.adm4file)
    pipeline.run()
