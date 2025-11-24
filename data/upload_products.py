"""
Firestore products 컬렉션 재업로드 스크립트

경로: TEMI_BACKEND/data/upload_products.py

사용법:
    프로젝트 루트(TEMI_BACKEND)에서 실행
    python data/upload_products.py
    
주요 기능:
    - goodsNo와 goods_no 두 가지 형식 모두 지원 (자동 통일)
    - dispCatNo/disp_cat_no, detailUrl/detail_url 자동 변환
    - 가격 필드 자동 형변환 (문자열 -> 정수)
    - 배치 업로드 (500개씩)
"""

import sys
import os
from pathlib import Path

# 프로젝트 루트 경로를 sys.path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import json
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime


def init_firebase():
    """Firebase 초기화"""
    try:
        if not firebase_admin._apps:
            # 프로젝트 루트의 serviceAccountKey.json 사용
            cred_path = project_root / 'serviceAccountKey.json'
            
            if not cred_path.exists():
                print(f"❌ Firebase 서비스 계정 키를 찾을 수 없습니다: {cred_path}")
                return None
            
            cred = credentials.Certificate(str(cred_path))
            firebase_admin.initialize_app(cred)
        
        db = firestore.client()
        print("✅ Firebase 초기화 완료\n")
        return db
        
    except Exception as e:
        print(f"❌ Firebase 초기화 실패: {str(e)}")
        return None


def delete_all_products(db):
    """products 컬렉션의 모든 문서 삭제"""
    print("🗑️  기존 products 데이터 삭제 중...")
    
    collection_ref = db.collection('products')
    deleted_count = 0
    
    # 배치 삭제 (500개씩)
    while True:
        docs = list(collection_ref.limit(500).stream())
        if not docs:
            break
        
        batch = db.batch()
        for doc in docs:
            batch.delete(doc.reference)
        batch.commit()
        
        deleted_count += len(docs)
        print(f"   삭제됨: {deleted_count}개")
    
    print(f"✅ 총 {deleted_count}개 문서 삭제 완료\n")
    return deleted_count


def load_products_json():
    """data/json/products.json 파일 로드"""
    json_path = project_root / 'data' / 'json' / 'products.json'
    
    print(f"📂 JSON 파일 로드 중: {json_path}")
    
    if not json_path.exists():
        print(f"❌ 파일을 찾을 수 없습니다: {json_path}")
        return None
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # JSON 구조 확인
        if 'products' in data:
            products = data['products']
        elif isinstance(data, list):
            products = data
        else:
            print("❌ JSON 형식이 올바르지 않습니다.")
            print("   예상 형식: {'products': [...]} 또는 [...]")
            return None
        
        print(f"✅ JSON 파일 로드 완료: {len(products)}개 상품\n")
        return products
        
    except json.JSONDecodeError as e:
        print(f"❌ JSON 파싱 오류: {e}")
        return None
    except Exception as e:
        print(f"❌ 파일 로드 오류: {e}")
        return None


def normalize_field_names(product):
    """
    스네이크 케이스를 카멜 케이스로 통일
    goods_no -> goodsNo
    disp_cat_no -> dispCatNo
    detail_url -> detailUrl
    """
    normalized = product.copy()
    
    # goods_no -> goodsNo
    if 'goods_no' in normalized:
        if 'goodsNo' not in normalized:
            normalized['goodsNo'] = normalized['goods_no']
        del normalized['goods_no']
    
    # disp_cat_no -> dispCatNo
    if 'disp_cat_no' in normalized:
        if 'dispCatNo' not in normalized:
            normalized['dispCatNo'] = normalized['disp_cat_no']
        del normalized['disp_cat_no']
    
    # detail_url -> detailUrl
    if 'detail_url' in normalized:
        if 'detailUrl' not in normalized:
            normalized['detailUrl'] = normalized['detail_url']
        del normalized['detail_url']
    
    return normalized


def convert_product_data(product):
    """
    상품 데이터를 Firestore 업로드 형식으로 변환
    - 필드명 정규화 (스네이크 케이스 -> 카멜 케이스)
    - product_id 필드 추가
    - 가격 필드를 정수로 변환
    - 타임스탬프 추가
    """
    try:
        # 1. 필드명 정규화
        converted = normalize_field_names(product)
        
        # 2. goodsNo 확인
        if 'goodsNo' not in converted or not converted['goodsNo']:
            return None, "goodsNo 필드가 없거나 비어있음"
        
        goods_id = converted['goodsNo']
        
        # 3. product_id 추가
        converted['product_id'] = goods_id
        
        # 4. 가격 필드 변환 (문자열 -> 정수)
        if 'price_org' in converted:
            try:
                converted['price_org'] = int(converted['price_org'])
            except (ValueError, TypeError):
                converted['price_org'] = 0
        
        if 'price_cur' in converted:
            try:
                converted['price_cur'] = int(converted['price_cur'])
            except (ValueError, TypeError):
                converted['price_cur'] = 0
        
        # 5. page_idx 변환
        if 'page_idx' in converted:
            try:
                converted['page_idx'] = int(converted['page_idx'])
            except (ValueError, TypeError):
                converted['page_idx'] = 0
        
        # 6. t_number 변환 (있는 경우)
        if 't_number' in converted:
            try:
                converted['t_number'] = int(converted['t_number'])
            except (ValueError, TypeError):
                pass  # 문자열로 유지
        
        # 7. 타임스탬프 추가
        converted['created_at'] = datetime.now()
        converted['updated_at'] = datetime.now()
        
        # 8. stock 필드 추가 (기본값: 50)
        if 'stock' not in converted:
            converted['stock'] = 50
        
        return converted, None
        
    except Exception as e:
        return None, str(e)


def validate_product(product):
    """
    상품 데이터 검증
    goodsNo 또는 goods_no 지원
    """
    # goodsNo 또는 goods_no 확인
    has_goods_id = ('goodsNo' in product and product['goodsNo']) or \
                   ('goods_no' in product and product['goods_no'])
    
    if not has_goods_id:
        return False, "필수 필드 누락 또는 빈 값: goodsNo/goods_no"
    
    # name 확인
    if 'name' not in product or not product['name']:
        return False, "필수 필드 누락 또는 빈 값: name"
    
    # brand 확인
    if 'brand' not in product or not product['brand']:
        return False, "필수 필드 누락 또는 빈 값: brand"
    
    return True, None


def upload_products(db, products):
    """products를 Firestore에 배치 업로드"""
    print(f"📤 Firestore에 {len(products)}개 상품 업로드 중...\n")
    
    collection_ref = db.collection('products')
    success_count = 0
    error_count = 0
    errors = []
    
    # 배치 업로드 (500개씩)
    for i in range(0, len(products), 500):
        batch = db.batch()
        batch_products = products[i:i + 500]
        batch_success = 0
        
        for product in batch_products:
            try:
                # 데이터 검증
                is_valid, error_msg = validate_product(product)
                if not is_valid:
                    error_count += 1
                    goods_id = product.get('goodsNo') or product.get('goods_no', 'UNKNOWN')
                    errors.append(f"[{goods_id}] {error_msg}")
                    continue
                
                # 데이터 변환
                converted_product, error_msg = convert_product_data(product)
                if converted_product is None:
                    error_count += 1
                    goods_id = product.get('goodsNo') or product.get('goods_no', 'UNKNOWN')
                    errors.append(f"[{goods_id}] 변환 실패: {error_msg}")
                    continue
                
                # goodsNo를 문서 ID로 사용
                doc_id = converted_product['goodsNo']
                
                # 배치에 추가
                doc_ref = collection_ref.document(doc_id)
                batch.set(doc_ref, converted_product)
                batch_success += 1
                
            except Exception as e:
                error_count += 1
                goods_id = product.get('goodsNo') or product.get('goods_no', 'UNKNOWN')
                errors.append(f"[{goods_id}] 예외 발생: {str(e)}")
        
        # 배치 커밋
        try:
            batch.commit()
            success_count += batch_success
            progress = min(i + 500, len(products))
            percent = (progress / len(products)) * 100
            print(f"   진행: {progress}/{len(products)} ({percent:.1f}%) - 성공: {batch_success}개")
        except Exception as e:
            error_count += batch_success
            errors.append(f"배치 커밋 실패: {str(e)}")
            print(f"   ❌ 배치 커밋 실패: {str(e)}")
    
    # 에러 상세 출력
    if errors:
        print(f"\n⚠️  발생한 오류 ({len(errors)}개):")
        for idx, error in enumerate(errors[:10], 1):  # 최대 10개만 출력
            print(f"   {idx}. {error}")
        if len(errors) > 10:
            print(f"   ... 외 {len(errors) - 10}개 오류")
    
    print(f"\n✅ 업로드 완료: {success_count}개 성공, {error_count}개 실패\n")
    return success_count, error_count


def verify_upload(db, expected_count):
    """업로드 검증 - Firestore에 실제로 저장된 문서 수 확인"""
    print("🔍 업로드 검증 중...")
    
    try:
        collection_ref = db.collection('products')
        docs = list(collection_ref.limit(1).stream())
        
        if not docs:
            print("   ⚠️  업로드된 문서가 없습니다!")
            return False
        
        # 샘플 문서 확인
        sample_doc = docs[0].to_dict()
        print(f"   ✅ 샘플 문서 확인 성공")
        print(f"      - 문서 ID: {docs[0].id}")
        print(f"      - 상품명: {sample_doc.get('name', 'N/A')}")
        print(f"      - 브랜드: {sample_doc.get('brand', 'N/A')}")
        print(f"      - 가격: {sample_doc.get('price_cur', 'N/A')}원")
        print(f"      - 재고: {sample_doc.get('stock', 'N/A')}개\n")
        
        return True
        
    except Exception as e:
        print(f"   ❌ 검증 실패: {str(e)}\n")
        return False


def main():
    """메인 실행 함수"""
    print("=" * 70)
    print("🔥 Firestore Products 컬렉션 재업로드")
    print("=" * 70)
    print(f"📁 프로젝트 루트: {project_root}")
    print("=" * 70)
    print()
    
    # 1. Firebase 초기화
    db = init_firebase()
    if not db:
        return
    
    # 2. 기존 데이터 삭제
    delete_all_products(db)
    
    # 3. JSON 파일 로드
    products = load_products_json()
    if not products:
        return
    
    # 4. Firestore에 업로드
    success, error = upload_products(db, products)
    
    # 5. 업로드 검증
    verify_upload(db, len(products))
    
    # 6. 결과 요약
    print("=" * 70)
    print("📊 최종 결과")
    print("=" * 70)
    print(f"✅ 성공: {success}개")
    print(f"❌ 실패: {error}개")
    print(f"📍 총: {len(products)}개")
    if len(products) > 0:
        print(f"📈 성공률: {(success/len(products)*100):.1f}%")
    print("=" * 70)
    print()
    print("💡 Firebase Console에서 확인:")
    print("   https://console.firebase.google.com/")
    print()
    
    if error > 0:
        print("⚠️  일부 상품 업로드에 실패했습니다.")
        print("   위의 오류 메시지를 확인하여 데이터를 수정해주세요.")
        print()


if __name__ == "__main__":
    main()