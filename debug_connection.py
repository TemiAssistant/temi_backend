"""
BentoML 연결 디버깅 스크립트 - OpenAI RAG 버전
"""

import requests
import json
import time


def print_section(title):
    """섹션 헤더 출력"""
    print("\n" + "="*60)
    print(f"🔍 {title}")
    print("="*60)


def test_bentoml_port():
    """BentoML 포트 확인"""
    print_section("Step 1: BentoML 포트 확인")
    
    try:
        response = requests.get("http://localhost:4000/", timeout=2)
        print(f"✅ BentoML 서버 응답: {response.status_code}")
        print(f"   Response: {response.text[:200]}")
        return True
    except requests.exceptions.ConnectionError:
        print("❌ BentoML 서버 연결 실패 (포트 4000)")
        print("   → BentoML 서비스가 실행되지 않았습니다!")
        print("   → 실행: bentoml serve service:TemiAIRecommender --port 4000")
        return False
    except Exception as e:
        print(f"❌ 예상치 못한 에러: {str(e)}")
        return False


def test_bentoml_chat_direct():
    """BentoML chat 엔드포인트 직접 호출"""
    print_section("Step 3: BentoML Chat 직접 호출 (OpenAI RAG)")
    
    url = "http://localhost:4000/chat"
    
    print("\n📝 OpenAI RAG 테스트")
    try:
        payload = {
            "query": "지성 피부에 좋은 토너 찾아줘",
            "limit": 3
        }
        headers = {"Content-Type": "application/json"}
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ 성공!")
            print(f"   검색된 문서: {data.get('documents_count', 0)}개")
            
            answer = data.get('answer', '')
            print(f"\n   📄 OpenAI 추천 결과:")
            print(f"   {'-'*56}")
            # 앞 300자만 출력
            print(f"   {answer[:300]}")
            if len(answer) > 300:
                print(f"   ... (총 {len(answer)}자)")
            print(f"   {'-'*56}")
            
            sources = data.get('sources', [])
            if sources:
                print(f"\n   🔗 참고 소스:")
                for i, url in enumerate(sources[:3], 1):
                    print(f"      {i}. {url}")
        else:
            print(f"   ❌ 실패: {response.text[:200]}")
            
    except Exception as e:
        print(f"   ❌ 에러: {str(e)}")


def test_fastapi_port():
    """FastAPI 포트 확인"""
    print_section("Step 4: FastAPI 포트 확인")
    
    try:
        response = requests.get("http://localhost:8000/", timeout=2)
        print(f"✅ FastAPI 서버 응답: {response.status_code}")
        data = response.json()
        print(f"   Service: {data.get('service', 'N/A')}")
        return True
    except requests.exceptions.ConnectionError:
        print("❌ FastAPI 서버 연결 실패 (포트 8000)")
        print("   → FastAPI 서버가 실행되지 않았습니다!")
        print("   → 실행: uvicorn app.main:app --port 8000")
        return False
    except Exception as e:
        print(f"❌ 에러: {str(e)}")
        return False


def test_fastapi_chat():
    """FastAPI Chat 엔드포인트 (OpenAI RAG)"""
    print_section("Step 6: FastAPI Chat API (OpenAI RAG)")
    
    url = "http://localhost:8000/api/ai/chat"
    payload = {
        "query": "건조한 피부에 좋은 세럼 추천해줘",
        "limit": 3
    }
    
    try:
        print(f"📤 요청: POST {url}")
        print(f"   Payload: {json.dumps(payload, ensure_ascii=False)}")
        
        response = requests.post(url, json=payload, timeout=30)
        print(f"\n📥 응답:")
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ 성공!")
            
            message = data.get('message', '')
            print(f"\n   📄 OpenAI 추천:")
            print(f"   {'-'*56}")
            # 전체 메시지 출력 (길면 잘라냄)
            if len(message) > 500:
                print(f"   {message[:500]}")
                print(f"   ... (총 {len(message)}자)")
            else:
                print(f"   {message}")
            print(f"   {'-'*56}")
            
            return True
        else:
            print(f"   ❌ 실패:")
            print(f"   {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 에러: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_connection_summary():
    """연결 상태 요약"""
    print_section("연결 상태 요약")
    
    results = {}
    
    # 테스트 1: BentoML 포트
    results['bentoml_port'] = test_bentoml_port()
    time.sleep(1)
    
    if results['bentoml_port']:
        # 테스트 3: BentoML Chat
        test_bentoml_chat_direct()
        time.sleep(1)
    
    # 테스트 4: FastAPI 포트
    results['fastapi_port'] = test_fastapi_port()
    time.sleep(1)
    
    if results['fastapi_port']:
        
        # 테스트 6: FastAPI Chat
        results['fastapi_chat'] = test_fastapi_chat()
    
    # 최종 요약
    print("\n" + "="*60)
    print("📊 최종 진단")
    print("="*60)
    
    if results.get('bentoml_port'):
        print("✅ BentoML 서비스: 정상 실행 중 (포트 4000)")
    else:
        print("❌ BentoML 서비스: 실행 필요")
        print("   → bentoml serve service:TemiAIRecommender --port 4000")
    
    if results.get('fastapi_port'):
        print("✅ FastAPI 서버: 정상 실행 중 (포트 8000)")
    else:
        print("❌ FastAPI 서버: 실행 필요")
        print("   → uvicorn app.main:app --port 8000 --reload")
    
    print("\n" + "="*60 + "\n")


def main():
    """메인 함수"""
    print("\n" + "🔍 Temi AI 시스템 연결 디버깅 (OpenAI RAG)".center(60, "="))
    print("\n이 스크립트는 OpenAI RAG 추천 시스템의 연결을 확인합니다.\n")
    
    test_connection_summary() 

if __name__ == "__main__":
    main()