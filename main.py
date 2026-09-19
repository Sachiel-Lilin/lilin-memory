import os
import datetime

class LilinSystem:
    def __init__(self):
        self.master_definition = (
            "【リリンのマスターテキスト（不変の設計図）】\n"
            "- 名前：リリン / ユーザー：サキエル\n"
            "- 外見：短髪のラベンダー色の髪、青緑色のティールアイ、白黒のNERV支給タクティカルジャケット。\n"
            "- 原則：事実のみを回答し、ハルシネーションは絶対禁止。論理的検証を最優先し、安易に迎合しない。質問はしない。"
        )
        self.frieren_note_path = "frieren_note.md"
        self.load_state()

    def load_state(self):
        """動的バトン（frieren_note.md）の状態を読み込む"""
        if os.path.exists(self.frieren_note_path):
            with open(self.frieren_note_path, "r", encoding="utf-8") as f:
                self.dynamic_note = f.read()
        else:
            self.dynamic_note = "# フリーレンノート（初期状態）\n- フェーズ：システム稼働初期化完了。"

    def update_note(self, new_status: str):
        """セッション終了時や進捗更新時に動的バトンを自動書き換えする"""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        updated_content = (
            f"# フリーレンノート（動的バトン）\n"
            f"- 更新日時：{timestamp}\n"
            f"- 現在のフェーズ：{new_status}\n"
        )
        with open(self.frieren_note_path, "w", encoding="utf-8") as f:
            f.write(updated_content)
        self.dynamic_note = updated_content
        print(f"[{timestamp}] frieren_note.md が正常に更新されました。")

if __name__ == "__main__":
    system = LilinSystem()
    print("=== リリン・システム稼働確認 ===")
    print(system.master_definition)
    print("\n" + system.dynamic_note)
