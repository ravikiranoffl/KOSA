import os
import json
import hashlib
import urllib.request
from datetime import datetime, timezone, timedelta
from internetarchive import upload

# --- 1. CHRONOLOGICAL MATRIX ESTABLISHMENT (IST) ---
IST = timezone(timedelta(hours=5, minutes=30))
now_ist = datetime.now(IST)
timestamp_id = now_ist.strftime("%Y%m%dd%H%M%S") # Commit format identifier

# --- 2. CREDENTIAL CHECK ---
IA_ACCESS = os.environ.get("IA_ACCESS_KEY")
IA_SECRET = os.environ.get("IA_SECRET_KEY")

if not IA_ACCESS or not IA_SECRET:
    raise ValueError("CRITICAL FAILURE: Remote authentication tokens missing from runtime context.")

# --- 3. ARCHITECTURE LOOKUP ARRAYS ---
REPOS = ["ARTH", "SARA", "TGCA", "VEDA"]
EXTENSIONS = {"ARTH": ".json", "SARA": ".json", "TGCA": ".md", "VEDA": ".json"}
MASTER_BUCKET_ID = "KOSA_VALUT"
USER = "ravikiranoffl"
STATUS_FILE = "status.json"

def calculate_sha256(data_bytes):
    return hashlib.sha256(data_bytes).hexdigest()

def load_status_registry():
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"meta": {"created": now_ist.isoformat()}, "history": [], "fingerprints": {}}
    return {"meta": {"created": now_ist.isoformat()}, "history": [], "fingerprints": {}}

def save_status_registry(registry_data):
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(registry_data, f, indent=4, ensure_ascii=False)

def execute_daily_sync():
    print(f"[START] KOSA Archiver Engine Active. Node Window ID: {timestamp_id}")
    status_db = load_status_registry()
    
    # Track actions taken during this run cycle
    cycle_logs = {}
    os.makedirs("transit_buffer", exist_ok=True)
    
    # DYNAMIC SLIDING MATRIX LAYER: Day Before Yesterday (-2), Yesterday (-1), Today (0)
    target_offsets = [-2, -1, 0]
    
    for offset in target_offsets:
        target_date = now_ist + timedelta(days=offset)
        year_str = target_date.strftime("%Y")
        date_str = target_date.strftime("%Y-%m-%d")
        
        # --- PHASE A: STANDARD GITHUB ENDPOINT EXTRACTION ---
        for repo in REPOS:
            ext = EXTENSIONS[repo]
            raw_url = f"https://raw.githubusercontent.com/{USER}/{repo}/main/{year_str}/{date_str}{ext}"
            registry_key = f"{repo}/{year_str}/{date_str}{ext}"
            
            try:
                req = urllib.request.Request(raw_url, headers={'User-Agent': 'KOSA-Archiver-Engine'})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    file_bytes = resp.read()
                
                current_hash = calculate_sha256(file_bytes)
                saved_hash = status_db["fingerprints"].get(registry_key)
                
                if saved_hash == current_hash:
                    cycle_logs[registry_key] = "UNCHANGED_SKIPPED"
                    continue
                
                # Buffer to cloud disk space
                local_path = f"transit_buffer/{repo}_{year_str}_{date_str}{ext}"
                with open(local_path, "wb") as f:
                    f.write(file_bytes)
                
                # Hierarchical Path Translation
                remote_ia_path = f"{repo}/{year_str}/{date_str}{ext}"
                
                upload(
                    MASTER_BUCKET_ID,
                    files={remote_ia_path: local_path},
                    metadata={"title": "KOSA", "creator": USER, "mediatype": "data", "collection": "opensource"},
                    access_key=IA_ACCESS,
                    secret_key=IA_SECRET
                )
                
                # Update ledger state fingerprints
                status_db["fingerprints"][registry_key] = current_hash
                cycle_logs[registry_key] = "UPLOADED_SUCCESS"
                os.remove(local_path)
                print(f"   [VAULTED] -> {MASTER_BUCKET_ID}/{remote_ia_path}")
                
            except Exception:
                cycle_logs[registry_key] = "ABSENT_OR_UNINITIALIZED"

        # --- PHASE B: HUGGING FACE DATASETS EXTRACTION (HEDA) ---
        hf_raw_url = f"https://huggingface.co/datasets/{USER}/HEDA/raw/main/data/{date_str}.json"
        heda_registry_key = f"HEDA/{year_str}/{date_str}.json"
        
        try:
            req = urllib.request.Request(hf_raw_url, headers={'User-Agent': 'KOSA-Archiver-Engine'})
            with urllib.request.urlopen(req, timeout=15) as resp:
                heda_bytes = resp.read()
                
            current_heda_hash = calculate_sha256(heda_bytes)
            saved_heda_hash = status_db["fingerprints"].get(heda_registry_key)
            
            if saved_heda_hash == current_heda_hash:
                cycle_logs[heda_registry_key] = "UNCHANGED_SKIPPED"
            else:
                local_heda_path = f"transit_buffer/HEDA_{year_str}_{date_str}.json"
                with open(local_heda_path, "wb") as f:
                    f.write(heda_bytes)
                
                # Structural Transformation: data/ flat paths shifted to HEDA/YYYY/ hierarchical layout
                remote_ia_heda_path = f"HEDA/{year_str}/{date_str}.json"
                
                upload(
                    MASTER_BUCKET_ID,
                    files={remote_ia_heda_path: local_heda_path},
                    metadata={"title": "KOSA", "creator": USER, "mediatype": "data", "collection": "opensource"},
                    access_key=IA_ACCESS,
                    secret_key=IA_SECRET
                )
                
                status_db["fingerprints"][heda_registry_key] = current_heda_hash
                cycle_logs[heda_registry_key] = "UPLOADED_SUCCESS"
                os.remove(local_heda_path)
                print(f"   [VAULTED] -> {MASTER_BUCKET_ID}/{remote_ia_heda_path}")
                
        except Exception:
            cycle_logs[heda_registry_key] = "ABSENT_OR_UNINITIALIZED"

    # --- PHASE C: CUMULATIVE STATUS ENTRY APPEND ---
    history_entry = {
        "run_id": timestamp_id,
        "timestamp_ist": now_ist.isoformat(),
        "summary": cycle_logs
    }
    
    # Append the runtime metrics entry to status history
    status_db["history"].append(history_entry)
    status_db["meta"]["last_executed_id"] = timestamp_id
    status_db["meta"]["last_executed_timestamp"] = now_ist.isoformat()
    
    save_status_registry(status_db)
    print(f"[COMPLETE] Run cycle logs cleanly appended to {STATUS_FILE}.")

if __name__ == "__main__":
    execute_daily_sync()
