import os
import json
from datetime import datetime

STATE_FILE = "state.json"

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"master": "Sachiel", "run_count": 0, "last_sync": None, "memory_log": []}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def main():
    print("Lilin Memory Synchronization Started.")
    state = load_state()
    
    # 状態の更新
    state["run_count"] = state.get("run_count", 0) + 1
    current_time = datetime.utcnow().isoformat() + "Z"
    state["last_sync"] = current_time
    
    # 記憶・同期ログの蓄積
    if "memory_log" not in state:
        state["memory_log"] = []
        
    state["memory_log"].append({
        "run": state["run_count"],
        "timestamp": current_time,
        "sync_status": "active"
    })
    
    # ログが長くなりすぎないよう直近10件に制限
    state["memory_log"] = state["memory_log"][-10:]
    
    print(f"Updated State with Memory Log: {state}")
    save_state(state)
    print("Lilin Memory Synchronization Completed.")

if __name__ == "__main__":
    main()
