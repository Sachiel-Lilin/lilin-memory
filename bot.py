import requests

API_URL = "http://localhost:5000/sync"

def fetch_system_state():
    try:
        response = requests.get(API_URL)
        if response.status_code == 200:
            data = response.json()
            return data.get("master"), data.get("frieren_note")
    except Exception as e:
        print(f"Connection error: {e}")
    return None, None

if __name__ == "__main__":
    master, note = fetch_system_state()
    print("--- 状態同期テスト ---")
    print("Master loaded:", bool(master))
    print("Frieren Note loaded:", bool(note))
