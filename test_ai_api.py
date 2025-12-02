"""
AI 추천 API 테스트 스크립트

사용법:
    python test_ai_api.py

요구사항:
    - FastAPI 서버 실행 중 (포트 8000)
    - BentoML 서비스 실행 중 (포트 3000)
"""

import requests
import json
from typing import Dict, Any


class TemiAITester:
    """AI API 테스터"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        
    def test_health(self):
        """헬스 체크"""
        print("\n" + "="*60)
        print("🏥 AI 서비스 헬스 체크")
        print("="*60)
        
        url = f"{self.base_url}/api/ai/health"
        
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            print(f"✅ 상태: {data['status']}")
            print(f"   서비스: {data['service']}")
            print(f"   BentoML: {'✅ 연결됨' if data['bentoml_available'] else '❌ 연결 안됨'}")
            print(f"   상품 로드: {data['products_loaded']}개")
            
            return True
            
        except Exception as e:
            print(f"❌ 헬스 체크 실패: {str(e)}")
            return False
    
    def test_chat(self):
        """질문 기반 추천 테스트"""
        print("\n" + "="*60)
        print("💬 질문 기반 추천 테스트")
        print("="*60)
        
        url = f"{self.base_url}/api/ai/chat"
        
        test_queries = [
            "지성 피부에 좋은 토너 찾아줘",
            "건조한 피부에 좋은 세럼 추천해줘",
            "3만원 이하 선크림 알려줘",
        ]
        
        for query in test_queries:
            print(f"\n📝 질문: {query}")
            
            payload = {
                "query": query,
                "customer_id": "test_user",
                "limit": 3
            }
            
            try:
                response = requests.post(url, json=payload, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                print(f"\n   🔍 분석 결과:")
                extracted = data['extracted_info']
                if extracted.get('skin_type'):
                    print(f"      - 피부타입: {extracted['skin_type']}")
                if extracted.get('category'):
                    print(f"      - 카테고리: {extracted['category']}")
                if extracted.get('price_range'):
                    print(f"      - 가격범위: {extracted['price_range']}")
                
                print(f"\n   🎁 추천 상품 ({data['total']}개):")
                for i, product in enumerate(data['recommendations'], 1):
                    print(f"      {i}. {product['name']}")
                    print(f"         브랜드: {product['brand']}")
                    print(f"         가격: {product['price']:,}원")
                    print(f"         점수: {product['similarity_score']:.3f}")
                    print(f"         이유: {product['reason']}")
                
                if data.get('message'):
                    print(f"\n   💡 메시지: {data['message']}")
                
            except Exception as e:
                print(f"   ❌ 오류: {str(e)}")
    
    def test_recommend(self):
        """필터 기반 추천 테스트"""
        print("\n" + "="*60)
        print("🔍 필터 기반 추천 테스트")
        print("="*60)
        
        url = f"{self.base_url}/api/ai/recommend"
        
        test_filters = [
            {
                "name": "지성 피부 + 토너",
                "payload": {
                    "skin_type": "지성",
                    "category": "토너",
                    "limit": 3
                }
            },
            {
                "name": "건성 피부 + 가격 2만원 이하",
                "payload": {
                    "skin_type": "건성",
                    "price_max": 20000,
                    "limit": 3
                }
            },
        ]
        
        for test in test_filters:
            print(f"\n📌 필터: {test['name']}")
            print(f"   조건: {test['payload']}")
            
            try:
                response = requests.post(url, json=test['payload'], timeout=10)
                response.raise_for_status()
                data = response.json()
                
                print(f"\n   🎁 추천 상품 ({data['total']}개):")
                for i, product in enumerate(data['recommendations'], 1):
                    print(f"      {i}. {product['name']}")
                    print(f"         {product['brand']} | {product['price']:,}원")
                    print(f"         점수: {product['similarity_score']:.3f}")
                
            except Exception as e:
                print(f"   ❌ 오류: {str(e)}")


def main():
    """메인 테스트 실행"""
    print("\n" + "🤖 Temi AI 추천 API 테스트".center(60, "="))
    
    tester = TemiAITester()
    
    # 1. 헬스 체크
    if not tester.test_health():
        print("\n⚠️  서비스가 실행되지 않았습니다. 서버를 먼저 시작하세요.")
        return
    
    # 2. 질문 기반 추천
    tester.test_chat()
    
    # 3. 필터 기반 추천
    tester.test_recommend()
    
    print("\n" + "="*60)
    print("✅ 테스트 완료!")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
