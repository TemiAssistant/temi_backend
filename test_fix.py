# test_fix.py
import requests
import json

BASE_URL = "http://localhost:8000"

def test(name, method, url, **kwargs):
    """테스트 헬퍼"""
    print(f"\n{'='*60}")
    print(f"🧪 {name}")
    print(f"{'='*60}")
    print(f"URL: {url}")
    
    try:
        if method == "GET":
            response = requests.get(url, **kwargs)
        else:
            response = requests.post(url, **kwargs)
        
        print(f"✅ Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 성공!")
            
            # 결과 미리보기
            if isinstance(data, list):
                print(f"📦 결과 개수: {len(data)}")
                if len(data) > 0:
                    print(f"첫 번째 항목:")
                    print(json.dumps(data[0], indent=2, ensure_ascii=False))
            elif isinstance(data, dict):
                if 'products' in data:
                    print(f"📦 검색 결과: {data.get('total', 0)}개")
                    print(f"현재 페이지: {len(data.get('products', []))}개")
                else:
                    print(json.dumps(data, indent=2, ensure_ascii=False))
            
            return True
        else:
            print(f"❌ 실패!")
            print(f"응답: {response.text[:500]}")
            return False
            
    except Exception as e:
        print(f"❌ 에러 발생: {e}")
        return False

# 테스트 실행
print("\n" + "="*60)
print("🚀 Products API 테스트")
print("="*60)

# Test 1: 서버 연결
test("서버 상태", "GET", f"{BASE_URL}/")

# Test 2: 전체 상품
test("전체 상품 목록", "GET", f"{BASE_URL}/api/products", params={"limit": 3})

# Test 3: 상품 상세
test("상품 상세", "GET", f"{BASE_URL}/api/products/prod_001")

# Test 4: 빠른 검색 - 설화수
test(
    "빠른 검색 - 설화수", 
    "GET", 
    f"{BASE_URL}/api/products/search/quick",
    params={"q": "설화수", "limit": 3}
)

# Test 5: 빠른 검색 - 에센스
test(
    "빠른 검색 - 에센스", 
    "GET", 
    f"{BASE_URL}/api/products/search/quick",
    params={"q": "에센스", "limit": 5}
)

# Test 6: 복합 검색
test(
    "복합 검색", 
    "POST", 
    f"{BASE_URL}/api/products/search",
    json={
        "category": "스킨케어",
        "min_price": 10000,
        "max_price": 50000,
        "sort_by": "price_low",
        "page": 1,
        "page_size": 5
    }
)

# Test 7: 카테고리 목록
test("카테고리 목록", "GET", f"{BASE_URL}/api/products/categories")

# Test 8: 브랜드 목록
test("브랜드 목록", "GET", f"{BASE_URL}/api/products/brands")

# Test 9: 인기 상품
test(
    "인기 상품", 
    "GET", 
    f"{BASE_URL}/api/products/recommendations/popular",
    params={"limit": 5} 
)

print("\n" + "="*60)
print("✅ 테스트 완료!")
print("="*60 + "\n")