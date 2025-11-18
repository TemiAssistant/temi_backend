"""
Firestore products 컬렉션 재업로드 스크립트

경로: TEMI_BACKEND/data/upload_products.py

사용법:
    프로젝트 루트(TEMI_BACKEND)에서 실행
    python data/upload_products.py
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


def upload_products(db, products):
    """products를 Firestore에 배치 업로드"""
    print(f"📤 Firestore에 {len(products)}개 상품 업로드 중...\n")
    
    collection_ref = db.collection('products')
    success_count = 0
    error_count = 0
    
    # 배치 업로드 (500개씩)
    for i in range(0, len(products), 500):
        batch = db.batch()
        batch_products = products[i:i + 500]
        
        for product in batch_products:
            try:
                # product_id를 문서 ID로 사용
                if 'product_id' in product:
                    doc_id = product['product_id']
                else:
                    print(f"⚠️  경고: product_id가 없는 상품 건너뜀")
                    error_count += 1
                    continue
                
                # 타임스탬프 추가
                product['created_at'] = datetime.now()
                product['updated_at'] = datetime.now()
                
                # 배치에 추가
                doc_ref = collection_ref.document(doc_id)
                batch.set(doc_ref, product)
                success_count += 1
                
            except Exception as e:
                error_count += 1
                print(f"⚠️  오류 발생: {str(e)}")
        
        # 배치 커밋
        try:
            batch.commit()
            progress = min(i + 500, len(products))
            percent = (progress / len(products)) * 100
            print(f"   진행: {progress}/{len(products)} ({percent:.1f}%)")
        except Exception as e:
            print(f"❌ 배치 업로드 실패: {str(e)}")
            error_count += len(batch_products)
    
    print(f"\n✅ 업로드 완료: {success_count}개 성공, {error_count}개 실패\n")
    return success_count, error_count


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
    
    # 5. 결과 요약
    print("=" * 70)
    print("📊 최종 결과")
    print("=" * 70)
    print(f"✅ 성공: {success}개")
    print(f"❌ 실패: {error}개")
    print(f"📍 총: {len(products)}개")
    print("=" * 70)
    print()
    print("💡 Firebase Console에서 확인:")
    print("   https://console.firebase.google.com/")
    print()


if __name__ == "__main__":
    main()