"""
AI 추천 API용 Pydantic 모델
Temi Android에서 사용할 Request/Response 정의
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# ==================== Chat API ====================

class ChatRequest(BaseModel):
    """질문 요청 (자연어)"""
    query: str = Field(..., description="사용자 질문", example="지성 피부에 좋은 토너 찾아줘")
    customer_id: Optional[str] = Field(None, description="고객 ID (옵션)")
    limit: int = Field(5, ge=1, le=20, description="추천 개수")
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "건조한 피부에 좋은 세럼 추천해줘",
                "customer_id": "user_001",
                "limit": 5
            }
        }


class ExtractedInfo(BaseModel):
    """질문에서 추출된 정보"""
    skin_type: Optional[str] = Field(None, description="피부 타입")
    category: Optional[str] = Field(None, description="카테고리")
    price_range: Optional[Dict[str, int]] = Field(None, description="가격 범위")
    keywords: List[str] = Field(default_factory=list, description="키워드")


class ProductRecommendation(BaseModel):
    """추천 상품"""
    product_id: str = Field(..., description="상품 ID")
    name: str = Field(..., description="상품명")
    brand: str = Field(..., description="브랜드")
    price: int = Field(..., description="가격")
    category: str = Field(..., description="카테고리")
    description: str = Field(..., description="설명")
    similarity_score: float = Field(..., description="유사도 점수 (0-1)")
    reason: str = Field(..., description="추천 이유")


class ChatResponse(BaseModel):
    """질문 응답"""
    success: bool = True
    query: str = Field(..., description="원본 질문")
    extracted_info: ExtractedInfo = Field(..., description="추출된 정보")
    recommendations: List[ProductRecommendation] = Field(..., description="추천 상품")
    total: int = Field(..., description="추천 개수")
    message: Optional[str] = Field(None, description="추가 메시지")


# ==================== Recommendation API ====================

class RecommendationRequest(BaseModel):
    """필터 기반 추천 요청"""
    customer_id: Optional[str] = Field(None, description="고객 ID")
    skin_type: Optional[str] = Field(None, description="피부 타입", example="지성")
    category: Optional[str] = Field(None, description="카테고리", example="토너")
    price_min: Optional[int] = Field(None, ge=0, description="최소 가격")
    price_max: Optional[int] = Field(None, ge=0, description="최대 가격")
    limit: int = Field(5, ge=1, le=20, description="추천 개수")
    
    class Config:
        json_schema_extra = {
            "example": {
                "skin_type": "지성",
                "category": "토너",
                "price_max": 30000,
                "limit": 5
            }
        }


class RecommendationResponse(BaseModel):
    """추천 응답"""
    success: bool = True
    filters: Dict[str, Any] = Field(..., description="적용된 필터")
    recommendations: List[ProductRecommendation] = Field(..., description="추천 상품")
    total: int = Field(..., description="추천 개수")


# ==================== Health Check ====================

class HealthResponse(BaseModel):
    """서비스 상태"""
    status: str = Field(..., description="상태 (healthy/unhealthy)")
    service: str = Field(..., description="서비스 이름")
    products_loaded: int = Field(..., description="로드된 상품 수")
    bentoml_available: bool = Field(..., description="BentoML 연결 상태")