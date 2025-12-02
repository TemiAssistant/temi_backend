"""
AI 추천 API 엔드포인트
Temi Android에서 호출

경로: /api/ai/**
"""

from fastapi import APIRouter, HTTPException, status
from app.models.ai_models import (
    ChatRequest,
    ChatResponse,
    RecommendationRequest,
    RecommendationResponse,
    HealthResponse,
)
from app.services.ai_service import ai_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai", tags=["AI Recommendations"])


# ==================== 질문 기반 추천 ====================

@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="질문 기반 추천 (자연어)",
    description="""
    Temi Android에서 사용자 질문을 받아 AI가 분석하고 상품을 추천합니다.
    
    **예시 질문:**
    - "지성 피부에 좋은 토너 찾아줘"
    - "건조한 피부에 좋은 세럼 추천해줘"
    - "3만원 이하 선크림 알려줘"
    
    **응답:**
    - 질문 분석 결과 (피부타입, 카테고리, 가격 등)
    - 추천 상품 목록 (유사도 점수 포함)
    - 추천 이유
    """
)
async def chat_recommendation(request: ChatRequest):
    """
    질문 기반 AI 추천
    
    Temi Android 호출 예시:
    ```java
    // Retrofit 또는 HttpURLConnection
    POST http://YOUR_SERVER:8000/api/ai/chat
    Body: {
        "query": "지성 피부에 좋은 토너 찾아줘",
        "customer_id": "user_001",
        "limit": 5
    }
    ```
    """
    try:
        logger.info(f"AI Chat 요청: {request.query}")
        response = await ai_service.chat(request)
        logger.info(f"AI Chat 완료: {response.total}개 추천")
        return response
        
    except TimeoutError as e:
        logger.error(f"타임아웃: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="AI 서비스 응답 시간 초과"
        )
        
    except ConnectionError as e:
        logger.error(f"연결 실패: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI 서비스 연결 실패"
        )
        
    except Exception as e:
        logger.error(f"AI Chat 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI 추천 중 오류 발생: {str(e)}"
        )


# ==================== 필터 기반 추천 ====================

@router.post(
    "/recommend",
    response_model=RecommendationResponse,
    summary="필터 기반 추천",
    description="""
    구조화된 필터로 상품을 추천합니다.
    
    **필터 옵션:**
    - skin_type: 피부 타입 (지성, 건성, 복합성, 민감성)
    - category: 카테고리 (토너, 세럼, 크림 등)
    - price_min/max: 가격 범위
    """
)
async def filter_recommendation(request: RecommendationRequest):
    """
    필터 기반 추천
    
    Temi Android 호출 예시:
    ```java
    POST http://YOUR_SERVER:8000/api/ai/recommend
    Body: {
        "skin_type": "지성",
        "category": "토너",
        "price_max": 30000,
        "limit": 5
    }
    ```
    """
    try:
        logger.info(f"AI Recommend 요청: {request.dict()}")
        response = await ai_service.recommend(request)
        logger.info(f"AI Recommend 완료: {response.total}개 추천")
        return response
        
    except Exception as e:
        logger.error(f"AI Recommend 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"추천 중 오류 발생: {str(e)}"
        )


# ==================== 헬스 체크 ====================

@router.get(
    "/health",
    response_model=HealthResponse,
    summary="AI 서비스 상태 확인",
    description="BentoML AI 서비스 연결 상태를 확인합니다"
)
async def health_check():
    """
    AI 서비스 헬스 체크
    
    Temi Android에서 주기적으로 호출하여 서비스 상태 확인
    """
    return await ai_service.health_check()


# ==================== 테스트용 엔드포인트 ====================

@router.get(
    "/test",
    summary="API 테스트",
    description="간단한 API 응답 테스트"
)
async def test_endpoint():
    """API 작동 확인용"""
    return {
        "status": "ok",
        "message": "AI API is running",
        "endpoints": {
            "chat": "POST /api/ai/chat",
            "recommend": "POST /api/ai/recommend",
            "health": "GET /api/ai/health"
        }
    }