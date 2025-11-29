# app/api/products.py
"""
상품 관련 API 엔드포인트
실제 products.json 구조에 맞춰 수정됨
"""

from fastapi import APIRouter, HTTPException, Query, Path
from typing import Optional, List, Union
from app.models.product import (
    ProductDetail,
    ProductDescription,
    ProductSummary,
    ProductSearchParams,
    ProductSearchResponse,
    RecommendationRequest,
    RecommendationResponse,
    CategoriesResponse,
    SubCategoriesResponse,
    BrandsResponse,
    FilterOptionsResponse,
    ProductCountResponse,
    ProductUsageResponse,
    ProductCautionResponse,
    SortBy
)
from app.services.product_service import product_service
import logging

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/products", tags=["Products"])


# ==================== 상품 개수 조회 ====================

@router.get(
    "/count",
    response_model=ProductCountResponse,
    summary="전체 상품 개수 조회",
    description="Firestore에 저장된 전체 상품 개수를 조회합니다"
)
async def get_product_count():
    """
    전체 상품 개수 조회
    
    Returns:
        ProductCountResponse: 상품 개수 통계
    """
    try:
        count_data = await product_service.get_product_count()
        return ProductCountResponse(
            success=True,
            **count_data
        )
    except Exception as e:
        logger.error(f"상품 개수 조회 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="상품 개수 조회 중 오류가 발생했습니다"
        )


# ==================== 필터 옵션 조회 ====================

@router.get(
    "/filters/options",
    response_model=FilterOptionsResponse,
    summary="필터 옵션 조회",
    description="검색 필터에 사용할 필터를 조회합니다"
)
async def get_filter_options():
    """
    필터 옵션 조회
    
    Returns:
        FilterOptionsResponse: 필터 옵션 목록
    """
    try:
        filter_options = await product_service.get_filter_options()
        return FilterOptionsResponse(
            success=True,
            filters=filter_options
        )
    except Exception as e:
        logger.error(f"필터 옵션 조회 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="필터 옵션 조회 중 오류가 발생했습니다"
        )


# ==================== 카테고리/브랜드 ====================

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
        CategoriesResponse: 카테고리 목록
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
    "/sub-categories",
    response_model=SubCategoriesResponse,
    summary="서브카테고리 목록",
    description="서브카테고리 목록과 상품 수를 조회합니다"
)
async def get_sub_categories(
    category: Optional[str] = Query(None, description="카테고리로 필터링")
):
    """
    서브카테고리 목록 조회
    
    Args:
        category: 특정 카테고리의 서브카테고리만 조회
    
    Returns:
        SubCategoriesResponse: 서브카테고리 목록
    """
    try:
        sub_categories = await product_service.get_sub_categories(category)
        return SubCategoriesResponse(success=True, sub_categories=sub_categories)
        
    except Exception as e:
        logger.error(f"서브카테고리 조회 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="서브카테고리 조회 중 오류가 발생했습니다"
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
        BrandsResponse: 브랜드 목록
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


# ==================== 검색 ====================

@router.get(
    "/search",
    response_model=ProductSearchResponse,
    summary="상품 검색",
    description="다양한 조건으로 상품을 검색합니다"
)
async def search_products(
    query: Optional[str] = Query(None, description="검색 키워드"),
    category: Optional[str] = Query(None, description="카테고리 필터"),
    sub_category: Optional[str] = Query(None, description="서브카테고리 필터"),
    brand: Optional[str] = Query(None, description="브랜드 필터"),
    min_price: Optional[int] = Query(None, ge=0, description="최소 가격"),
    max_price: Optional[int] = Query(None, ge=0, description="최대 가격"),
    skin_type: Optional[Union[str, List[str]]] = Query(None, description="피부 타입"),
    in_stock: Optional[bool] = Query(True, description="재고 있는 상품만"),
    sort_by: SortBy = Query(SortBy.POPULARITY, description="정렬 기준"),
    page: int = Query(1, ge=1, description="페이지 번호"),
    page_size: int = Query(20, ge=1, le=100, description="페이지 크기")
):
    """
    상품 검색
    
    **필터링 옵션:**
    - query: 상품명, 브랜드, 성분에서 검색
    - category: 카테고리 필터
    - sub_category: 서브카테고리 필터
    - brand: 브랜드 필터
    - min_price, max_price: 가격 범위
    - skin_type: 피부 타입
    - in_stock: 재고 있는 상품만
    
    **정렬 옵션:**
    - popularity: 인기순 (할인율)
    - price_low: 낮은 가격순
    - price_high: 높은 가격순
    - recent: 최신순
    - discount: 할인율순
    
    Returns:
        ProductSearchResponse: 검색 결과
    """
    try:
        # 피부 타입 파라미터 정규화 (문자열/다중 값 모두 지원)
        def normalize_skin_types(value: Optional[Union[str, List[str]]]) -> Optional[List[str]]:
            if value is None:
                return None
            if isinstance(value, list):
                cleaned = [v.strip() for v in value if isinstance(v, str) and v.strip()]
                return cleaned or None
            if isinstance(value, str):
                parts = [part.strip() for part in value.split(',')]
                cleaned = [part for part in parts if part]
                return cleaned or None
            return None
        
        params = ProductSearchParams(
            query=query,
            first_category=category,
            mid_category=sub_category,
            brand=brand,
            min_price=min_price,
            max_price=max_price,
            spec=normalize_skin_types(skin_type),
            in_stock=in_stock,
            sort_by=sort_by,
            page=page,
            page_size=page_size
        )
        
        result = await product_service.search_products(params)
        
        return ProductSearchResponse(
            success=True,
            **result
        )
        
    except Exception as e:
        logger.error(f"상품 검색 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"상품 검색 중 오류가 발생했습니다: {str(e)}"
        )


@router.get(
    "/search/quick",
    response_model=List[ProductSummary],
    summary="빠른 검색",
    description="키워드로 빠르게 상품을 검색합니다"
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
        page=1,
        page_size=limit
    )
    
    result = await product_service.search_products(params)
    return result['products']


# ==================== 카테고리별/브랜드별 조회 ====================

@router.get(
    "/category/{category}",
    response_model=List[ProductSummary],
    summary="카테고리별 상품",
    description="특정 카테고리의 상품을 조회합니다"
)
async def get_products_by_category(
    category: str = Path(..., description="카테고리명"),
    limit: int = Query(20, ge=1, le=200, description="조회할 상품 수")
):
    """
    카테고리별 상품 조회
    
    - **category**: 카테고리명 (예: 대_스킨케어)
    - **limit**: 조회할 상품 수
    
    Returns:
        List[ProductSummary]: 상품 목록
    """
    products = await product_service.get_products_by_category(category, limit)
    
    if not products:
        logger.info(f"카테고리 '{category}' 결과 없음")
        return []
    
    return products


@router.get(
    "/brand/{brand}",
    response_model=List[ProductSummary],
    summary="브랜드별 상품",
    description="특정 브랜드의 상품을 조회합니다"
)
async def get_products_by_brand(
    brand: str = Path(..., description="브랜드명"),
    limit: int = Query(20, ge=1, le=200, description="조회할 상품 수")
):
    """
    브랜드별 상품 조회
    
    - **brand**: 브랜드명 (예: 토리든)
    - **limit**: 조회할 상품 수
    
    Returns:
        List[ProductSummary]: 상품 목록
    """
    products = await product_service.get_products_by_brand(brand, limit)
    
    if not products:
        logger.info(f"브랜드 '{brand}' 결과 없음")
        return []
    
    return products


# ==================== 추천 ====================

@router.get(
    "/recommendations/popular",
    response_model=List[ProductSummary],
    summary="인기 상품",
    description="인기 상품을 조회합니다 (할인율 기준)"
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
    1. **product_id 제공**: 유사 상품 추천
    2. **skin_type 제공**: 피부 타입별 추천
    3. **아무것도 없음**: 인기 상품 추천 (할인율 기준)
    
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


# ==================== 상품 조회 ====================

@router.get(
    "",
    response_model=List[ProductSummary],
    summary="상품 목록 조회",
    description="전체 상품 목록을 페이징하여 조회합니다"
)
async def get_products(
    limit: Optional[int] = Query(
        None,
        ge=1,
        le=1000,
        description="조회할 상품 수 (미지정 시 전체)"
    ),
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
    product_id: str = Path(..., description="상품 ID (예: prod_1)")
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


@router.get(
    "/instructions/usage/{product_id}",
    response_model=ProductUsageResponse,
    summary="상품 사용 방법 조회",
    description="상품의 사용 방법만 별도로 조회합니다"
)
async def get_product_usage(
    product_id: str = Path(..., description="상품 ID (예: prod_1)")
):
    product = await product_service.get_product_by_id(product_id)

    if not product:
        raise HTTPException(
            status_code=404,
            detail=f"상품을 찾을 수 없습니다: {product_id}"
        )

    description = product.description or ProductDescription()
    return ProductUsageResponse(
        success=True,
        product_id=product.product_id,
        name=product.name,
        usage=description.usage
    )


@router.get(
    "/instructions/caution/{product_id}",
    response_model=ProductCautionResponse,
    summary="상품 주의 사항 조회",
    description="상품의 주의 사항만 별도로 조회합니다"
)
async def get_product_caution(
    product_id: str = Path(..., description="상품 ID (예: prod_1)")
):
    product = await product_service.get_product_by_id(product_id)

    if not product:
        raise HTTPException(
            status_code=404,
            detail=f"상품을 찾을 수 없습니다: {product_id}"
        )

    description = product.description or ProductDescription()
    return ProductCautionResponse(
        success=True,
        product_id=product.product_id,
        name=product.name,
        caution=description.caution
    )


