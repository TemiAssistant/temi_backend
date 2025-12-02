"""
AI 서비스 레이어 - OpenAI RAG 버전
"""

import logging
from typing import Dict, Any, List, Optional
import httpx
from app.models.ai_models import (
    ChatRequest,
    ChatResponse,
    RecommendationRequest,
    RecommendationResponse,
    ExtractedInfo,
    ProductRecommendation,
    HealthResponse,
)

logger = logging.getLogger(__name__)


class AIService:
    """BentoML AI 서비스 클라이언트 (OpenAI RAG)"""
    
    def __init__(self, bentoml_url: str = "http://localhost:4000"):
        self.bentoml_url = bentoml_url.rstrip("/")
        self.timeout = 60.0  # RAG는 시간이 더 걸림
        
    async def _call_bentoml(
        self, 
        endpoint: str, 
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """BentoML API 호출"""
        url = f"{self.bentoml_url}/{endpoint}"
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url, 
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                response.raise_for_status()
                return response.json()
                
        except httpx.TimeoutException:
            logger.error(f"BentoML 타임아웃: {url}")
            raise TimeoutError(f"BentoML 서비스 응답 시간 초과")
            
        except httpx.HTTPError as e:
            logger.error(f"BentoML 호출 실패: {url}, {str(e)}")
            raise ConnectionError(f"BentoML 서비스 연결 실패: {str(e)}")
    
    def _parse_openai_response(self, answer: str) -> List[ProductRecommendation]:
        """
        OpenAI 텍스트 응답을 ProductRecommendation 리스트로 파싱
        
        예상 형식:
        1. 제품명: 토리든 다이브인 토너
           설명: ...
           추천 이유: ...
        """
        products = []
        
        # 간단한 파싱 (실제로는 더 정교하게)
        lines = answer.split('\n')
        current_product = {}
        
        for line in lines:
            line = line.strip()
            
            if line.startswith(('1.', '2.', '3.', '4.', '5.')):
                # 새 제품 시작
                if current_product:
                    products.append(current_product)
                    current_product = {}
                
                # 제품명 추출
                if '제품명:' in line or '제품:' in line:
                    name = line.split(':', 1)[-1].strip()
                    current_product['name'] = name
                else:
                    current_product['name'] = line.split('.', 1)[-1].strip()
            
            elif '설명:' in line:
                current_product['description'] = line.split(':', 1)[-1].strip()
            
            elif '추천 이유:' in line or '이유:' in line:
                current_product['reason'] = line.split(':', 1)[-1].strip()
        
        # 마지막 제품 추가
        if current_product:
            products.append(current_product)
        
        # ProductRecommendation 객체로 변환
        recommendations = []
        for idx, prod in enumerate(products, 1):
            rec = ProductRecommendation(
                product_id=f"rag_{idx}",
                name=prod.get('name', '알 수 없는 제품'),
                brand="",  # OpenAI 응답에서 브랜드 분리 필요
                price=0,  # 가격 정보 없음
                category="",
                description=prod.get('description', '')[:100],
                similarity_score=1.0 - (idx * 0.1),  # 순서대로 점수
                reason=prod.get('reason', '')
            )
            recommendations.append(rec)
        
        return recommendations
    
    async def chat(self, request: ChatRequest) -> ChatResponse:
        """질문 기반 추천 (OpenAI RAG)"""
        payload = {
            "query": request.query,
            "customer_id": request.customer_id,
            "limit": request.limit
        }
        
        try:
            logger.info(f"OpenAI RAG 요청: {request.query}")
            result = await self._call_bentoml("chat", payload)
            
            # OpenAI 텍스트 응답을 그대로 사용 (파싱 건너뛰기)
            answer = result.get("answer", "")
            
            # 간단한 더미 추천 (실제로는 answer 텍스트가 중요)
            recommendations = [
                ProductRecommendation(
                    product_id="openai_1",
                    name="OpenAI 추천 결과",
                    brand="",
                    price=0,
                    category="",
                    description=answer[:200],  # 앞 200자만
                    similarity_score=1.0,
                    reason="OpenAI RAG 분석 결과"
                )
            ]
            
            return ChatResponse(
                success=result.get("success", True),
                query=result["query"],
                extracted_info=ExtractedInfo(),
                recommendations=recommendations,
                total=1,
                message=answer  # 전체 답변을 message에 포함
            )
            
        except Exception as e:
            logger.error(f"Chat API 오류: {str(e)}")
            return await self._fallback_recommendations(request.limit)
    
    async def recommend(
        self, 
        request: RecommendationRequest
    ) -> RecommendationResponse:
        """필터 기반 추천 (OpenAI RAG)"""
        payload = {
            "skin_type": request.skin_type,
            "category": request.category,
            "price_min": request.price_min,
            "price_max": request.price_max,
            "limit": request.limit
        }
        
        try:
            result = await self._call_bentoml("recommend", payload)
            
            answer = result.get("answer", "")
            recommendations = self._parse_openai_response(answer)
            
            return RecommendationResponse(
                success=result.get("success", True),
                filters=payload,
                recommendations=recommendations,
                total=len(recommendations)
            )
            
        except Exception as e:
            logger.error(f"Recommend API 오류: {str(e)}")
            raise
    
    async def health_check(self) -> HealthResponse:
        """BentoML 서비스 헬스 체크"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.bentoml_url}/health")
                response.raise_for_status()
                data = response.json()
                
                return HealthResponse(
                    status=data.get("status", "unknown"),
                    service=data.get("service", "temi_ai_recommender"),
                    products_loaded=0,  # RAG는 동적 검색
                    bentoml_available=True
                )
                
        except Exception as e:
            logger.warning(f"BentoML 헬스 체크 실패: {str(e)}")
            return HealthResponse(
                status="unhealthy",
                service="temi_ai_recommender",
                products_loaded=0,
                bentoml_available=False
            )
    
    async def _fallback_recommendations(
        self, 
        limit: int
    ) -> ChatResponse:
        """Fallback 추천"""
        logger.warning("Fallback 추천 실행")
        
        mock_recommendations = [
            ProductRecommendation(
                product_id="fallback_001",
                name="토리든 다이브인 토너",
                brand="토리든",
                price=18000,
                category="토너",
                description="인기 토너",
                similarity_score=0.8,
                reason="베스트셀러"
            )
        ]
        
        return ChatResponse(
            success=False,
            query="",
            extracted_info=ExtractedInfo(),
            recommendations=mock_recommendations[:limit],
            total=len(mock_recommendations[:limit]),
            message="AI 서비스 연결 실패. 인기 상품을 추천합니다."
        )


# 싱글톤 인스턴스
ai_service = AIService()
