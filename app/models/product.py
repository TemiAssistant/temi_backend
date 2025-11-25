# app/models/product.py
"""
상품 관련 Pydantic 모델
실제 products.json 구조에 맞춰 수정됨
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict
from datetime import datetime
from enum import Enum


# ==================== Enums ====================

class SortBy(str, Enum):
    """정렬 기준"""
    POPULARITY = "popularity"      # 인기순 (판매량)
    PRICE_LOW = "price_low"        # 낮은 가격순
    PRICE_HIGH = "price_high"      # 높은 가격순
    RECENT = "recent"              # 최신순
    DISCOUNT = "discount"          # 할인율순


# ==================== 기본 모델 ====================

class ProductStock(BaseModel):
    """재고 정보"""
    current: int = Field(0, ge=0, description="현재 재고 수량")
    threshold: int = Field(0, ge=0, description="재고 부족 임계값")
    unit_weight: int = Field(0, ge=0, description="단위 무게 (gram)")


class ProductDescription(BaseModel):
    """상품 설명"""
    usage: Optional[str] = Field(None, description="사용 방법")
    caution: Optional[str] = Field(None, description="주의사항")


# ==================== 상품 응답 모델 ====================

class ProductBase(BaseModel):
    """상품 기본 정보"""
    product_id: str
    name: str
    brand: str
    category: str
    sub_category: str
    price: int = Field(..., ge=0)
    original_price: int = Field(..., ge=0)
    discount_rate: int = Field(0, ge=0, le=100)
    is_active: bool = True


class ProductDetail(ProductBase):
    """상품 상세 정보 (전체 필드)"""
    stock: ProductStock
    description: ProductDescription
    ingredients: List[str] = []
    skin_types: List[str] = []
    image_url: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ProductSummary(ProductBase):
    """상품 요약 정보 (리스트용)"""
    stock: ProductStock
    image_url: Optional[str] = None
    
    class Config:
        from_attributes = True


# ==================== 검색 요청/응답 ====================

class ProductSearchParams(BaseModel):
    """상품 검색 파라미터"""
    query: Optional[str] = Field(None, description="검색 키워드")
    first_category: Optional[str] = Field(None, description="첫번째 카테고리 필터")
    mid_category: Optional[str] = Field(None, description="두 번째 카테고리 필터")
    brand: Optional[str] = Field(None, description="브랜드 필터")
    min_price: Optional[int] = Field(None, ge=0, description="최소 가격")
    max_price: Optional[int] = Field(None, ge=0, description="최대 가격")
    spec: Optional[str] = Field(None, description="피부 타입")
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
    limit: int = Field(5, ge=1, le=20, description="추천 상품 수")


class RecommendationResponse(BaseModel):
    """추천 응답"""
    success: bool = True
    recommendation_type: str = Field(..., description="추천 타입")
    products: List[ProductSummary]


# ==================== 카테고리/브랜드 응답 ====================

class CategoryInfo(BaseModel):
    """카테고리 정보"""
    category: str
    product_count: int


class SubCategoryInfo(BaseModel):
    """서브카테고리 정보"""
    sub_category: str
    product_count: int


class BrandInfo(BaseModel):
    """브랜드 정보"""
    brand: str
    product_count: int


class CategoriesResponse(BaseModel):
    """카테고리 목록 응답"""
    success: bool = True
    categories: List[CategoryInfo]


class SubCategoriesResponse(BaseModel):
    """서브카테고리 목록 응답"""
    success: bool = True
    sub_categories: List[SubCategoryInfo]


class BrandsResponse(BaseModel):
    """브랜드 목록 응답"""
    success: bool = True
    brands: List[BrandInfo]


# ==================== 필터 옵션 응답 ====================

class FilterOptions(BaseModel):
    """검색 필터 옵션"""
    brands: List[str] = Field(..., description="브랜드 목록")
    first_categories: List[str] = Field(..., description="첫번째 카테고리 목록")
    mid_categories: List[str] = Field(..., description="두 번째 카테고리 목록")
    spec: List[str] = Field(..., description="피부타입 목록")


class FilterOptionsResponse(BaseModel):
    """필터 옵션 응답"""
    success: bool = True
    filters: FilterOptions


# ==================== 상품 개수 응답 ====================

class ProductCountResponse(BaseModel):
    """상품 개수 응답"""
    success: bool = True
    total_count: int = Field(..., description="전체 상품 수")
    active_count: int = Field(..., description="활성 상품 수")
    inactive_count: int = Field(..., description="비활성 상품 수")
    by_category: Dict[str, int] = Field(..., description="카테고리별 개수")


class ProductUsageResponse(BaseModel):
    """상품 사용 방법 응답"""
    success: bool = True
    product_id: str
    name: str
    usage: Optional[str] = None


class ProductCautionResponse(BaseModel):
    """상품 주의 사항 응답"""
    success: bool = True
    product_id: str
    name: str
    caution: Optional[str] = None
