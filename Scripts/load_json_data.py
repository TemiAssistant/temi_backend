# scripts/load_json_data.py
"""
JSON 파일에서 데이터를 읽어 Firestore에 업로드하는 스크립트
데이터 수정이 필요할 때는 JSON 파일만 수정하면 됩니다!
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.firebase import firestore_db
from datetime import datetime, timedelta
import json
from pathlib import Path

# JSON 파일 경로
DATA_DIR = Path(__file__).parent.parent / 'data' / 'json'

def load_json_file(filename):
    """JSON 파일 로드"""
    filepath = DATA_DIR / filename
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ 파일을 찾을 수 없습니다: {filepath}")
        return None
    except json.JSONDecodeError as e:
        print(f"❌ JSON 파싱 오류: {e}")
        return None

def add_timestamps(data):
    """created_at, updated_at 타임스탬프 추가"""
    data['created_at'] = datetime.now()
    data['updated_at'] = datetime.now()
    return data

def calculate_date(days_ago=None, days_later=None):
    """날짜 계산 헬퍼 함수"""
    if days_ago is not None:
        return (datetime.now() - timedelta(days=days_ago)).isoformat()
    elif days_later is not None:
        return (datetime.now() + timedelta(days=days_later)).isoformat()
    return datetime.now().isoformat()

def load_products():
    """상품 데이터 로드 및 업로드"""
    print("\n" + "="*60)
    print("📦 상품 데이터 로드 중...")
    print("="*60)
    
    data = load_json_file('products.json')
    if not data or 'products' not in data:
        print("❌ 상품 데이터를 불러올 수 없습니다.")
        return 0
    
    products = data['products']
    
    for i, product in enumerate(products, 1):
        try:
            # 타임스탬프 추가
            product = add_timestamps(product)
            
            # Firestore에 업로드
            doc_ref = firestore_db.collection("products").document(product["product_id"])
            doc_ref.set(product)
            
            print(f"  ✅ [{i}/{len(products)}] {product['name']} - {product['price']:,}원")
        except Exception as e:
            print(f"  ❌ [{i}/{len(products)}] 실패: {str(e)}")
    
    print(f"\n✅ 총 {len(products)}개 상품 추가 완료!")
    return len(products)

def load_customers():
    """고객 데이터 로드 및 업로드"""
    print("\n" + "="*60)
    print("👤 고객 데이터 로드 중...")
    print("="*60)
    
    data = load_json_file('customers.json')
    if not data or 'customers' not in data:
        print("❌ 고객 데이터를 불러올 수 없습니다.")
        return 0
    
    customers = data['customers']
    
    for i, customer in enumerate(customers, 1):
        try:
            # 타임스탬프 추가
            customer = add_timestamps(customer)
            
            # Firestore에 업로드
            doc_ref = firestore_db.collection("customers").document(customer["uid"])
            doc_ref.set(customer)
            
            print(f"  ✅ [{i}/{len(customers)}] {customer['name']} ({customer['email']}) - {customer['membership_tier']}")
        except Exception as e:
            print(f"  ❌ [{i}/{len(customers)}] 실패: {str(e)}")
    
    print(f"\n✅ 총 {len(customers)}명 고객 추가 완료!")
    return len(customers)

def load_promotions():
    """프로모션 데이터 로드 및 업로드"""
    print("\n" + "="*60)
    print("🎁 프로모션 데이터 로드 중...")
    print("="*60)
    
    data = load_json_file('promotions.json')
    if not data or 'promotions' not in data:
        print("❌ 프로모션 데이터를 불러올 수 없습니다.")
        return 0
    
    promotions = data['promotions']
    
    for i, promo in enumerate(promotions, 1):
        try:
            # 날짜 계산
            if 'period' in promo:
                promo['period']['start'] = calculate_date(days_ago=promo['period'].get('start_days_ago', 0))
                promo['period']['end'] = calculate_date(days_later=promo['period'].get('end_days_later', 30))
                # 임시 키 제거
                promo['period'].pop('start_days_ago', None)
                promo['period'].pop('end_days_later', None)
            
            # 타임스탬프 추가
            promo = add_timestamps(promo)
            
            # Firestore에 업로드
            doc_ref = firestore_db.collection("promotions").document(promo["promotion_id"])
            doc_ref.set(promo)
            
            print(f"  ✅ [{i}/{len(promotions)}] {promo['title']} - {promo['description']}")
        except Exception as e:
            print(f"  ❌ [{i}/{len(promotions)}] 실패: {str(e)}")
    
    print(f"\n✅ 총 {len(promotions)}개 프로모션 추가 완료!")
    return len(promotions)

def load_store_config():
    """매장 설정 데이터 로드 및 업로드"""
    print("\n" + "="*60)
    print("⚙️  매장 설정 데이터 로드 중...")
    print("="*60)
    
    config = load_json_file('store_config.json')
    if not config:
        print("❌ 매장 설정 데이터를 불러올 수 없습니다.")
        return 0
    
    try:
        # 타임스탬프 추가
        config = add_timestamps(config)
        
        # Firestore에 업로드
        doc_ref = firestore_db.collection("store_config").document("default")
        doc_ref.set(config)
        
        print(f"  ✅ {config['store_name']} 설정 완료")
        print(f"     주소: {config['address']}")
        print(f"     구역 수: {len(config['layout']['zones'])}개")
        print(f"     Temi 로봇: {config['temi_config']['total_units']}대")
        
    except Exception as e:
        print(f"  ❌ 매장 설정 생성 실패: {str(e)}")
        return 0
    
    print("\n✅ 매장 설정 추가 완료!")
    return 1

def main():
    """메인 실행 함수"""
    print("\n" + "="*80)
    print("🔥 JSON 파일에서 Firestore 데이터 로드 시작!")
    print("="*80)
    print(f"📂 데이터 경로: {DATA_DIR}")
    print("="*80)
    
    # 각 함수 실행
    products_count = load_products()
    customers_count = load_customers()
    promotions_count = load_promotions()
    config_count = load_store_config()
    
    # 최종 결과
    print("\n" + "="*80)
    print("📊 최종 결과 요약")
    print("="*80)
    print(f"  📦 상품 (products):           {products_count:>3}개")
    print(f"  👤 고객 (customers):          {customers_count:>3}명")
    print(f"  🎁 프로모션 (promotions):     {promotions_count:>3}개")
    print(f"  ⚙️  매장 설정 (config):        {config_count:>3}개")
    print("="*80)
    print(f"  💾 총 데이터:                 {products_count + customers_count + promotions_count + config_count:>3}개")
    print("="*80)
    
    print("\n✅ 모든 JSON 데이터 로드 완료!")
    print("\n📝 데이터 수정 방법:")
    print(f"   1. {DATA_DIR} 폴더의 JSON 파일 수정")
    print("   2. python scripts/load_json_data.py 재실행")
    print("\n🔗 Firebase Console에서 확인:")
    print("   https://console.firebase.com/\n")

if __name__ == "__main__":
    main()