# app/models/product.py
"""
상품 관련 Pydantic 모델
요청/응답 데이터 구조 정의 및 검증
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
from enum import Enum


# ==================== Enums ====================

class SkinType(str, Enum):
    """피부 타입"""
    DRY = "건성"
    OILY = "지성"
    COMBINATION = "복합성"
    SENSITIVE = "민감성"
    ALL = "전체"


class Category(str, Enum):
    """상품 카테고리"""
    SKINCARE = "스킨케어"
    MAKEUP = "메이크업"
    HAIRCARE = "헤어케어"
    BODYCARE = "바디케어"
    SUNCARE = "선케어"
    MASKPACK = "마스크팩"
    CLEANSING = "클렌징"


class SortBy(str, Enum):
    """정렬 기준"""
    POPULARITY = "popularity"      # 인기순
    PRICE_LOW = "price_low"        # 낮은 가격순
    PRICE_HIGH = "price_high"      # 높은 가격순
    RATING = "rating"              # 평점순
    RECENT = "recent"              # 최신순
    SALES = "sales"                # 판매량순


# ==================== 기본 모델 ====================

class ProductLocation(BaseModel):
    """상품 위치 정보"""
    zone: str = Field(..., description="매대 구역 코드 (예: A-05)")
    shelf: int = Field(..., ge=1, description="선반 번호")
    x: float = Field(..., description="X 좌표")
    y: float = Field(..., description="Y 좌표")


class ProductStock(BaseModel):
    """재고 정보"""
    current: int = Field(..., ge=0, description="현재 재고 수량")
    threshold: int = Field(..., ge=0, description="재고 부족 임계값")
    unit_weight: int = Field(..., gt=0, description="단위 무게 (gram)")


class ProductRating(BaseModel):
    """평점 정보"""
    average: float = Field(..., ge=0, le=5, description="평균 평점")
    count: int = Field(..., ge=0, description="리뷰 개수")


class ProductSales(BaseModel):
    """판매 통계"""
    total_sold: int = Field(..., ge=0, description="총 판매 수량")
    monthly_sold: int = Field(..., ge=0, description="월간 판매 수량")


# ==================== 상품 응답 모델 ====================

class ProductBase(BaseModel):
    """상품 기본 정보"""
    product_id: str
    name: str
    brand: str
    category: str
    sub_category: str
    price: int
    original_price: int
    discount_rate: int
    is_active: bool


class ProductDetail(ProductBase):
    """상품 상세 정보 (전체 필드)"""
    location: ProductLocation
    stock: ProductStock
    description: Optional[str] = None
    ingredients: List[str] = []
    skin_types: List[str] = []
    concerns: List[str] = []
    rating: Optional[ProductRating] = None
    sales: Optional[ProductSales] = None
    tags: List[str] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProductSummary(ProductBase):
    """상품 요약 정보 (리스트용)"""
    location: ProductLocation
    stock: ProductStock
    rating: Optional[ProductRating] = None
    tags: List[str] = []

    class Config:
        from_attributes = True


# ==================== 검색 요청/응답 ====================

class ProductSearchParams(BaseModel):
    """상품 검색 파라미터"""
    query: Optional[str] = Field(None, description="검색 키워드")
    category: Optional[str] = Field(None, description="카테고리 필터")
    brand: Optional[str] = Field(None, description="브랜드 필터")
    min_price: Optional[int] = Field(None, ge=0, description="최소 가격")
    max_price: Optional[int] = Field(None, ge=0, description="최대 가격")
    skin_type: Optional[str] = Field(None, description="피부 타입")
    concerns: Optional[List[str]] = Field(None, description="피부 고민")
    tags: Optional[List[str]] = Field(None, description="태그 필터")
    in_stock: Optional[bool] = Field(True, description="재고 있는 상품만")
    sort_by: SortBy = Field(SortBy.POPULARITY, description="정렬 기준")
    page: int = Field(1, ge=1, description="페이지 번호")
    page_size: int = Field(20, ge=1, le=100, description="페이지 크기")

    @validator('max_price')
    def validate_price_range(cls, v, values):
        """가격 범위 검증"""
        if v is not None and 'min_price' in values and values['min_price'] is not None:
            if v < values['min_price']:
                raise ValueError('max_price는 min_price보다 커야 합니다')
        return v


class ProductSearchResponse(BaseModel):
    """상품 검색 응답"""
    success: bool = True
    total: int = Field(..., description="전체 검색 결과 수")
    page: int = Field(..., description="현재 페이지")
    page_size: int = Field(..., description="페이지 크기")
    total_pages: int = Field(..., description="전체 페이지 수")
    products: List[ProductSummary]


# ==================== 추천 요청/응답 ====================

class RecommendationRequest(BaseModel):
    """추천 요청"""
    customer_id: Optional[str] = Field(None, description="고객 ID")
    product_id: Optional[str] = Field(None, description="기준 상품 ID")
    skin_type: Optional[str] = Field(None, description="피부 타입")
    concerns: Optional[List[str]] = Field(None, description="피부 고민")
    limit: int = Field(5, ge=1, le=20, description="추천 상품 수")


class RecommendationResponse(BaseModel):
    """추천 응답"""
    success: bool = True
    recommendation_type: str = Field(..., description="추천 타입 (collaborative/content/popular)")
    products: List[ProductSummary]
    # TODO: AI 모델 연동 시 추가 필드
    # model_version: Optional[str] = None
    # confidence_scores: Optional[List[float]] = None


# ==================== 카테고리/브랜드 응답 ====================

class CategoryInfo(BaseModel):
    """카테고리 정보"""
    category: str
    product_count: int
    description: Optional[str] = None


class BrandInfo(BaseModel):
    """브랜드 정보"""
    brand: str
    product_count: int
    logo_url: Optional[str] = None


class CategoriesResponse(BaseModel):
    """카테고리 목록 응답"""
    success: bool = True
    categories: List[CategoryInfo]


class BrandsResponse(BaseModel):
    """브랜드 목록 응답"""
    success: bool = True
    brands: List[BrandInfo]