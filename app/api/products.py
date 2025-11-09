# app/api/products.py
"""
상품 관련 API 엔드포인트
"""

from fastapi import APIRouter, HTTPException, Query, Path
from typing import Optional, List
from app.models.product import (
    ProductDetail,
    ProductSummary,
    ProductSearchParams,
    ProductSearchResponse,
    RecommendationRequest,
    RecommendationResponse,
    CategoriesResponse,
    BrandsResponse,
    SortBy
)
from app.services.product_service import product_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/products", tags=["Products"])


# ==================== 카테고리/브랜드 (먼저 정의) ====================

@router.get(
    "/categories",
    response_model=CategoriesResponse,
    summary="카테고리 목록",
    description="전체 카테고리 목록과 상품 수를 조회합니다"
)
async def get_categories():
    """
    카테고리 목록 조회
    
    Returns:
        CategoriesResponse: 카테고리 목록 및 상품 수
    """
    try:
        categories = await product_service.get_categories()
        return CategoriesResponse(success=True, categories=categories)
        
    except Exception as e:
        logger.error(f"카테고리 조회 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="카테고리 조회 중 오류가 발생했습니다"
        )


@router.get(
    "/brands",
    response_model=BrandsResponse,
    summary="브랜드 목록",
    description="전체 브랜드 목록과 상품 수를 조회합니다"
)
async def get_brands():
    """
    브랜드 목록 조회
    
    Returns:
        BrandsResponse: 브랜드 목록 및 상품 수
    """
    try:
        brands = await product_service.get_brands()
        return BrandsResponse(success=True, brands=brands)
        
    except Exception as e:
        logger.error(f"브랜드 조회 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="브랜드 조회 중 오류가 발생했습니다"
        )


# ==================== 검색 (특정 경로) ====================

@router.get(
    "/search/quick",
    response_model=List[ProductSummary],
    summary="빠른 검색",
    description="키워드로 빠르게 상품을 검색합니다 (간단 버전)"
)
async def quick_search(
    q: str = Query(..., min_length=1, description="검색 키워드"),
    limit: int = Query(10, ge=1, le=50, description="결과 개수")
):
    """
    빠른 키워드 검색
    
    - **q**: 검색 키워드
    - **limit**: 결과 개수 (기본: 10)
    
    Returns:
        List[ProductSummary]: 검색 결과
    """
    params = ProductSearchParams(
        query=q,
        page_size=limit,
        page=1
    )
    
    result = await product_service.search_products(params)
    return result['products']


@router.post(
    "/search",
    response_model=ProductSearchResponse,
    summary="상품 검색",
    description="다양한 조건으로 상품을 검색합니다"
)
async def search_products(params: ProductSearchParams):
    """
    상품 검색 (복합 필터링)
    
    **검색 조건:**
    - query: 키워드 검색 (상품명, 브랜드, 태그)
    - category: 카테고리 필터
    - brand: 브랜드 필터
    - min_price, max_price: 가격 범위
    - skin_type: 피부 타입
    - concerns: 피부 고민
    - tags: 태그
    - in_stock: 재고 있는 상품만
    - sort_by: 정렬 기준
    - page, page_size: 페이징
    
    **정렬 옵션:**
    - popularity: 인기순
    - price_low: 낮은 가격순
    - price_high: 높은 가격순
    - rating: 평점순
    - sales: 판매량순
    
    Returns:
        ProductSearchResponse: 검색 결과
    """
    try:
        result = await product_service.search_products(params)
        
        return ProductSearchResponse(
            success=True,
            total=result['total'],
            page=result['page'],
            page_size=result['page_size'],
            total_pages=result['total_pages'],
            products=result['products']
        )
        
    except Exception as e:
        logger.error(f"상품 검색 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"상품 검색 중 오류가 발생했습니다: {str(e)}"
        )


# ==================== 카테고리/브랜드별 조회 ====================

@router.get(
    "/category/{category}",
    response_model=List[ProductSummary],
    summary="카테고리별 상품",
    description="특정 카테고리의 상품을 조회합니다"
)
async def get_products_by_category(
    category: str = Path(..., description="카테고리명"),
    limit: int = Query(20, ge=1, le=100, description="조회할 상품 수")
):
    """
    카테고리별 상품 조회
    
    - **category**: 카테고리명 (예: 스킨케어)
    - **limit**: 조회할 상품 수
    
    Returns:
        List[ProductSummary]: 상품 목록
    """
    products = await product_service.get_products_by_category(category, limit)
    
    if not products:
        raise HTTPException(
            status_code=404,
            detail=f"'{category}' 카테고리의 상품을 찾을 수 없습니다"
        )
    
    return products


@router.get(
    "/brand/{brand}",
    response_model=List[ProductSummary],
    summary="브랜드별 상품",
    description="특정 브랜드의 상품을 조회합니다"
)
async def get_products_by_brand(
    brand: str = Path(..., description="브랜드명"),
    limit: int = Query(20, ge=1, le=100, description="조회할 상품 수")
):
    """
    브랜드별 상품 조회
    
    - **brand**: 브랜드명 (예: 설화수)
    - **limit**: 조회할 상품 수
    
    Returns:
        List[ProductSummary]: 상품 목록
    """
    products = await product_service.get_products_by_brand(brand, limit)
    
    if not products:
        raise HTTPException(
            status_code=404,
            detail=f"'{brand}' 브랜드의 상품을 찾을 수 없습니다"
        )
    
    return products


# ==================== 추천 ====================

@router.get(
    "/recommendations/popular",
    response_model=List[ProductSummary],
    summary="인기 상품",
    description="인기 상품을 조회합니다 (판매량 기준)"
)
async def get_popular_products(
    limit: int = Query(10, ge=1, le=50, description="조회할 상품 수")
):
    """
    인기 상품 조회
    
    - **limit**: 조회할 상품 수 (기본: 10)
    
    Returns:
        List[ProductSummary]: 인기 상품 목록
    """
    request = RecommendationRequest(limit=limit)
    result = await product_service.get_recommendations(request)
    return result['products']


@router.post(
    "/recommendations",
    response_model=RecommendationResponse,
    summary="상품 추천",
    description="다양한 기준으로 상품을 추천합니다"
)
async def get_recommendations(request: RecommendationRequest):
    """
    상품 추천
    
    **추천 방식:**
    1. **product_id 제공**: 유사 상품 추천 (Content-Based)
    2. **customer_id 제공**: 고객 기반 추천 (Collaborative Filtering)
    3. **skin_type/concerns 제공**: 프로필 기반 추천
    4. **아무것도 없음**: 인기 상품 추천
    
    **AI 모델 연동 계획:**
    - 현재: 규칙 기반 추천
    - 향후: BentoML 기반 딥러닝 추천 모델
    
    Args:
        request: 추천 요청 파라미터
    
    Returns:
        RecommendationResponse: 추천 상품 목록
    """
    try:
        result = await product_service.get_recommendations(request)
        
        return RecommendationResponse(
            success=True,
            recommendation_type=result['recommendation_type'],
            products=result['products']
        )
        
    except Exception as e:
        logger.error(f"상품 추천 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"상품 추천 중 오류가 발생했습니다: {str(e)}"
        )


# ==================== 상품 조회 (마지막에 정의) ====================

@router.get(
    "",
    response_model=List[ProductSummary],
    summary="상품 목록 조회",
    description="전체 상품 목록을 페이징하여 조회합니다"
)
async def get_products(
    limit: int = Query(20, ge=1, le=100, description="조회할 상품 수"),
    offset: int = Query(0, ge=0, description="시작 위치")
):
    """
    전체 상품 목록 조회
    
    - **limit**: 조회할 상품 수 (기본: 20, 최대: 100)
    - **offset**: 시작 위치 (기본: 0)
    
    Returns:
        List[ProductSummary]: 상품 요약 정보 리스트
    """
    products = await product_service.get_all_products(limit=limit, offset=offset)
    return products


@router.get(
    "/{product_id}",
    response_model=ProductDetail,
    summary="상품 상세 조회",
    description="상품 ID로 상세 정보를 조회합니다"
)
async def get_product(
    product_id: str = Path(..., description="상품 ID (예: prod_001)")
):
    """
    상품 상세 정보 조회
    
    - **product_id**: 상품 고유 ID
    
    Returns:
        ProductDetail: 상품 상세 정보
    """
    product = await product_service.get_product_by_id(product_id)
    
    if not product:
        raise HTTPException(
            status_code=404,
            detail=f"상품을 찾을 수 없습니다: {product_id}"
        )
    
    return product