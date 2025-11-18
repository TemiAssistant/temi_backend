import json
import re
from pathlib import Path


PRODUCT_DIR = Path("product")
OUTPUT_PATH = Path("json/products.json")


def parse_int(value): 
    """문자/숫자 혼합 (예: '21,000') 을 int로 변환"""
    if value is None:
        return None
    try:
        s = str(value).replace(",", "").strip()
        return int(s)
    except ValueError:
        return None


def calc_discount_rate(price_org, price_cur):
    """
    할인율 = (원가 - 현재가) / 원가 * 100
    -> 정수 반올림
    """
    po = parse_int(price_org)
    pc = parse_int(price_cur)

    if po is None or pc is None or po == 0:
        return 0

    rate = (po - pc) / po * 100
    return round(rate)


def parse_unit_weight(volume_str):
    """
    volume 문자열에서 ml 혹은 g 앞의 숫자 하나를 unit_weight 로 사용
    예) '300ml', '100 ml', '200g'
    못 찾으면 None
    """
    if not volume_str:
        return None

    # 300ml, 300 ml, 300㎖, 300g, 300 g, 300그램 등
    m = re.search(r"(\d+)\s*(ml|mL|ML|㎖|g|G|그램)", volume_str)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    return None


def parse_skin_types(spec_str):
    """
    spec -> skin_types (list)
    예: "지성, 건성 / 복합성" -> ["지성", "건성", "복합성"]
    """
    if not spec_str:
        return []

    parts = re.split(r"[,/·\|]", spec_str)
    cleaned = [p.strip() for p in parts if p.strip()]
    return cleaned or [spec_str.strip()]


def parse_ingredients(ing_str):
    """
    ingredients 문자열을 콤마 기준으로 리스트로 변환
    """
    if not ing_str:
        return []
    return [part.strip() for part in ing_str.split(",") if part.strip()]


def natural_sort_key(path: Path):
    """
    파일명(P1M1, P1M2, ...)을 자연스럽게 정렬하기 위한 key
    P<숫자>M<숫자> 형태라면 (P숫자, M숫자)로 정렬
    """
    stem = path.stem
    m = re.match(r"P(\d+)M(\d+)", stem)
    if m:
        return int(m.group(1)), int(m.group(2))
    return (0, stem)


def build_product(record: dict, index: int) -> dict:
    """
    P1M1.json 안의 각 딕셔너리(record)를
    최종 products.json 에 들어갈 product 포맷으로 변환
    """
    price_org = record.get("price_org")
    price_cur = record.get("price_cur")

    original_price = parse_int(price_org)
    price = parse_int(price_cur)
    discount_rate = calc_discount_rate(price_org, price_cur)
    # unit_weight = parse_unit_weight(record.get("volume", ""))

    product = {
        # product_id: prod_1, prod_2, ...
        "product_id": f"prod_{index}",
        "name": record.get("name"),
        "brand": record.get("brand"),
        "category": record.get("first_category"),
        "sub_category": record.get("mid_category"),
        "price": price,
        "original_price": original_price,
        "discount_rate": discount_rate,

        # TODO: unit_weight 고민
        "stock": {
            "current": 0,
            "threshold": 0,
            "unit_weight": 0,
        },

        "description": {
            "usage": record.get("usage"),
            "caution": record.get("caution")
        },

        # 성분/피부타입
        "ingredients": parse_ingredients(record.get("ingredients")),
        "skin_types": parse_skin_types(record.get("spec")),

        # 이미지/상세 URL
        "image_url": record.get("image"),
        "is_active": True,
    }

    return product


def main():
    PRODUCT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    # data/product 안의 json 파일 전부 정렬해서 읽기
    json_files = sorted(PRODUCT_DIR.glob("*.json"), key=natural_sort_key)

    products = []
    idx = 1  # prod_1부터 시작

    for fpath in json_files:
        with fpath.open("r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as e:
                print(f"[WARN] JSON decode error in {fpath}: {e}")
                continue

        if not isinstance(data, list):
            print(f"[WARN] {fpath} 최상단이 리스트가 아닙니다. 건너뜀.")
            continue

        for record in data:
            if not isinstance(record, dict):
                continue
            product = build_product(record, idx)
            products.append(product)
            idx += 1

    output_obj = {
        "products": products
    }

    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(output_obj, f, ensure_ascii=False, indent=2)

    print(f"[완료] {len(products)}개 저장")


if __name__ == "__main__":
    main()
