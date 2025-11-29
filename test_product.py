"""간단한 Product API 수동 테스트 스크립트."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

import requests

BASE_URL = os.environ.get("PRODUCT_API_BASE_URL", "http://localhost:8000")
PRODUCT_API = f"{BASE_URL}/api/products"


def print_section(title: str) -> None:
    line = "=" * 60
    print(f"\n{line}\n{title}\n{line}")


def request_api(
    name: str,
    method: str,
    url: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    json_body: Optional[Dict[str, Any]] = None,
) -> Optional[requests.Response]:
    print_section(name)
    print(f"요청: {method} {url}")
    if params:
        print(f"쿼리: {params}")
    if json_body:
        print(f"바디: {json.dumps(json_body, ensure_ascii=False)}")

    try:
        response = requests.request(method, url, params=params, json=json_body, timeout=10)
    except Exception as exc:  # pragma: no cover
        print(f"요청 실패: {exc}")
        return None

    print(f"응답 코드: {response.status_code}")
    if response.headers.get("content-type", "").startswith("application/json"):
        try:
            payload = response.json()
        except ValueError:
            payload = response.text
    else:
        payload = response.text

    if isinstance(payload, list):
        print(f"목록 결과 {len(payload)}개 / 첫 항목:")
        preview = payload[:1]
    else:
        preview = payload

    print(json.dumps(preview, indent=2, ensure_ascii=False))
    return response


def fetch_sample_product_id() -> Optional[str]:
    response = request_api(
        "샘플 상품 조회",
        "GET",
        PRODUCT_API,
        params={"limit": 1, "offset": 0},
    )
    if not response or response.status_code != 200:
        return None
    data = response.json()
    if isinstance(data, list) and data:
        return data[0].get("product_id")
    return None


def main() -> None:
    print_section("Products API 테스트 시작")

    request_api("루트 상태", "GET", f"{BASE_URL}/")
    request_api("상품 개수 통계", "GET", f"{PRODUCT_API}/count")
    request_api("필터 옵션", "GET", f"{PRODUCT_API}/filters/options")
    request_api("카테고리 목록", "GET", f"{PRODUCT_API}/categories")
    request_api("브랜드 목록", "GET", f"{PRODUCT_API}/brands")

    request_api(
        "빠른 검색 (립)",
        "GET",
        f"{PRODUCT_API}/search/quick",
        params={"q": "립", "limit": 3},
    )

    request_api(
        "복합 검색 (카테고리+가격+피부타입)",
        "GET",
        f"{PRODUCT_API}/search",
        params={
            "category": "스킨케어",
            "sub_category": "토너",
            "min_price": 5000,
            "max_price": 30000,
            "skin_type": "모든 피부 타입",
            "sort_by": "price_low",
            "page": 1,
            "page_size": 5,
        },
    )

    product_id = fetch_sample_product_id()
    if product_id:
        request_api("상품 상세", "GET", f"{PRODUCT_API}/{product_id}")
        request_api(
            "사용 방법",
            "GET",
            f"{PRODUCT_API}/instructions/usage/{product_id}",
        )
        request_api(
            "주의 사항",
            "GET",
            f"{PRODUCT_API}/instructions/caution/{product_id}",
        )
    else:
        print("⚠️ 샘플 상품 ID를 가져오지 못했습니다.")

    print_section("Products API 테스트 종료")


if __name__ == "__main__":
    main()
