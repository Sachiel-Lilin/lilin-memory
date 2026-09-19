import os
import json
from datetime import datetime

STATE_FILE = "state.json"

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"master": "Sachiel", "run_count": 0, "last_sync": None}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def main():
    print("Lilin Memory Synchronization Started.")
    state = load_state()
    
    # 同期・状態更新ロジックの実行
    state["run_count"] = state.get("run_count", 0) + 1
    state["last_sync"] = datetime.utcnow().isoformat() + "Z"
    
    print(f"Updated State: {state}")
    
    save_state(state)
    print("Lilin Memory Synchronization Completed.")

if __name__ == "__main__":
    main()
