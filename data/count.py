import json
from pathlib import Path

PRODUCT_DIR = Path("product")

def count_items():
    json_files = sorted(PRODUCT_DIR.glob("*.json"))
    total_count = 0

    for fpath in json_files:
        try:
            with fpath.open("r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, list):
                count = len(data)
            else:
                print(f"[WARN] {fpath.name} 최상단이 리스트가 아님 — 건너뜀")
                continue

            print(f"{fpath.name}: {count} 개")
            total_count += count

        except Exception as e:
            print(f"[ERROR] {fpath} 읽기 실패 — {e}")

    print("-" * 40)
    print(f"전체 총 개수: {total_count} 개")


if __name__ == "__main__":
    count_items()
