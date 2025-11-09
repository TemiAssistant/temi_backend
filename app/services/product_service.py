# app/services/product_service.py
"""
상품 관련 비즈니스 로직
Firestore와 상호작용하며 데이터 처리
"""

from typing import List, Optional, Dict, Any
from app.core.firebase import firestore_db
from app.models.product import (
    ProductDetail, ProductSummary, ProductSearchParams,
    RecommendationRequest, SortBy
)
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ProductService:
    """상품 서비스 클래스"""
    
    def __init__(self):
        self.db = firestore_db
        self.collection = "products"
    
    # ==================== 기본 조회 ====================
    
    async def get_product_by_id(self, product_id: str) -> Optional[ProductDetail]:
        """상품 ID로 상세 정보 조회"""
        try:
            doc = self.db.collection(self.collection).document(product_id).get()
            
            if not doc.exists:
                logger.warning(f"상품을 찾을 수 없음: {product_id}")
                return None
            
            data = doc.to_dict()
            return ProductDetail(**data)
            
        except Exception as e:
            logger.error(f"상품 조회 실패: {product_id}, 오류: {str(e)}")
            raise
    
    async def get_all_products(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[ProductSummary]:
        """전체 상품 조회 (페이징)"""
        try:
            query = self.db.collection(self.collection)\
                          .where('is_active', '==', True)\
                          .limit(limit)\
                          .offset(offset)
            
            docs = query.stream()
            
            products = []
            for doc in docs:
                try:
                    data = doc.to_dict()
                    products.append(ProductSummary(**data))
                except Exception as e:
                    logger.warning(f"상품 파싱 실패: {doc.id}, 오류: {str(e)}")
                    continue
            
            return products
            
        except Exception as e:
            logger.error(f"전체 상품 조회 실패: {str(e)}")
            raise
    
    # ==================== 검색 ====================
    
    async def search_products(
        self,
        params: ProductSearchParams
    ) -> Dict[str, Any]:
        """상품 검색 (복합 필터링)"""
        try:
            # 기본 쿼리 (활성 상품만)
            query = self.db.collection(self.collection)\
                          .where('is_active', '==', True)
            
            # 1. 카테고리 필터
            if params.category:
                query = query.where('category', '==', params.category)
            
            # 2. 브랜드 필터
            if params.brand:
                query = query.where('brand', '==', params.brand)
            
            # 3. 가격 필터
            if params.min_price is not None:
                query = query.where('price', '>=', params.min_price)
            if params.max_price is not None:
                query = query.where('price', '<=', params.max_price)
            
            # 쿼리 실행
            docs = list(query.stream())
            
            # 4. 메모리에서 추가 필터링
            products = []
            for doc in docs:
                data = doc.to_dict()
                
                # 재고 필터
                if params.in_stock and data.get('stock', {}).get('current', 0) <= 0:
                    continue
                
                # 키워드 검색 (이름, 브랜드, 태그)
                if params.query:
                    query_lower = params.query.lower()
                    name_match = query_lower in data.get('name', '').lower()
                    brand_match = query_lower in data.get('brand', '').lower()
                    tag_match = any(query_lower in tag.lower() for tag in data.get('tags', []))
                    
                    if not (name_match or brand_match or tag_match):
                        continue
                
                # 피부 타입 필터
                if params.skin_type:
                    skin_types = data.get('skin_types', [])
                    if params.skin_type not in skin_types and '전체' not in skin_types:
                        continue
                
                # 피부 고민 필터
                if params.concerns:
                    product_concerns = data.get('concerns', [])
                    if not any(concern in product_concerns for concern in params.concerns):
                        continue
                
                # 태그 필터
                if params.tags:
                    product_tags = data.get('tags', [])
                    if not any(tag in product_tags for tag in params.tags):
                        continue
                
                try:
                    products.append(ProductSummary(**data))
                except Exception as e:
                    logger.warning(f"상품 파싱 실패: {doc.id}, 오류: {str(e)}")
                    continue
            
            # 5. 정렬
            products = self._sort_products(products, params.sort_by)
            
            # 6. 페이징
            total = len(products)
            start = (params.page - 1) * params.page_size
            end = start + params.page_size
            paginated_products = products[start:end]
            
            return {
                "total": total,
                "page": params.page,
                "page_size": params.page_size,
                "total_pages": (total + params.page_size - 1) // params.page_size,
                "products": paginated_products
            }
            
        except Exception as e:
            logger.error(f"상품 검색 실패: {str(e)}")
            raise
    
    def _sort_products(
        self,
        products: List[ProductSummary],
        sort_by: SortBy
    ) -> List[ProductSummary]:
        """상품 정렬"""
        if sort_by == SortBy.POPULARITY:
            # 판매량 기준 (데이터 없으면 0)
            return sorted(
                products,
                key=lambda p: getattr(p.sales, 'monthly_sold', 0) if p.sales else 0,
                reverse=True
            )
        elif sort_by == SortBy.PRICE_LOW:
            return sorted(products, key=lambda p: p.price)
        elif sort_by == SortBy.PRICE_HIGH:
            return sorted(products, key=lambda p: p.price, reverse=True)
        elif sort_by == SortBy.RATING:
            return sorted(
                products,
                key=lambda p: getattr(p.rating, 'average', 0) if p.rating else 0,
                reverse=True
            )
        elif sort_by == SortBy.SALES:
            return sorted(
                products,
                key=lambda p: getattr(p.sales, 'total_sold', 0) if p.sales else 0,
                reverse=True
            )
        elif sort_by == SortBy.RECENT:
            # created_at은 summary에 없으므로 일단 순서 유지
            return products
        
        return products
    
    # ==================== 카테고리/브랜드 ====================
    
    async def get_categories(self) -> List[Dict[str, Any]]:
        """카테고리 목록 및 상품 수 조회"""
        try:
            docs = self.db.collection(self.collection)\
                         .where('is_active', '==', True)\
                         .stream()
            
            category_count = {}
            for doc in docs:
                data = doc.to_dict()
                category = data.get('category')
                if category:
                    category_count[category] = category_count.get(category, 0) + 1
            
            categories = [
                {
                    "category": cat,
                    "product_count": count,
                    "description": None  # TODO: 카테고리 설명 추가
                }
                for cat, count in sorted(category_count.items())
            ]
            
            return categories
            
        except Exception as e:
            logger.error(f"카테고리 조회 실패: {str(e)}")
            raise
    
    async def get_brands(self) -> List[Dict[str, Any]]:
        """브랜드 목록 및 상품 수 조회"""
        try:
            docs = self.db.collection(self.collection)\
                         .where('is_active', '==', True)\
                         .stream()
            
            brand_count = {}
            for doc in docs:
                data = doc.to_dict()
                brand = data.get('brand')
                if brand:
                    brand_count[brand] = brand_count.get(brand, 0) + 1
            
            brands = [
                {
                    "brand": brand,
                    "product_count": count,
                    "logo_url": None  # TODO: 브랜드 로고 추가
                }
                for brand, count in sorted(brand_count.items())
            ]
            
            return brands
            
        except Exception as e:
            logger.error(f"브랜드 조회 실패: {str(e)}")
            raise
    
    async def get_products_by_category(
        self,
        category: str,
        limit: int = 20
    ) -> List[ProductSummary]:
        """카테고리별 상품 조회"""
        try:
            docs = self.db.collection(self.collection)\
                         .where('is_active', '==', True)\
                         .where('category', '==', category)\
                         .limit(limit)\
                         .stream()
            
            products = []
            for doc in docs:
                try:
                    data = doc.to_dict()
                    products.append(ProductSummary(**data))
                except Exception as e:
                    logger.warning(f"상품 파싱 실패: {doc.id}")
                    continue
            
            return products
            
        except Exception as e:
            logger.error(f"카테고리별 상품 조회 실패: {category}, 오류: {str(e)}")
            raise
    
    async def get_products_by_brand(
        self,
        brand: str,
        limit: int = 20
    ) -> List[ProductSummary]:
        """브랜드별 상품 조회"""
        try:
            docs = self.db.collection(self.collection)\
                         .where('is_active', '==', True)\
                         .where('brand', '==', brand)\
                         .limit(limit)\
                         .stream()
            
            products = []
            for doc in docs:
                try:
                    data = doc.to_dict()
                    products.append(ProductSummary(**data))
                except Exception as e:
                    logger.warning(f"상품 파싱 실패: {doc.id}")
                    continue
            
            return products
            
        except Exception as e:
            logger.error(f"브랜드별 상품 조회 실패: {brand}, 오류: {str(e)}")
            raise
    
    # ==================== 추천 ====================
    
    async def get_recommendations(
        self,
        request: RecommendationRequest
    ) -> Dict[str, Any]:
        """상품 추천"""
        
        # TODO: BentoML AI 모델 연동
        # recommendation_type = "ai_model"
        # products = await self._get_ai_recommendations(request)
        
        # 현재는 규칙 기반 추천 사용
        if request.product_id:
            # 유사 상품 추천 (같은 카테고리 + 비슷한 가격대)
            recommendation_type = "content_based"
            products = await self._get_similar_products(request.product_id, request.limit)
        
        elif request.customer_id:
            # 고객 기반 추천 (구매 이력 기반)
            # TODO: 고객 구매 이력 분석
            recommendation_type = "collaborative"
            products = await self._get_popular_products(request.limit)
        
        elif request.skin_type or request.concerns:
            # 피부 타입/고민 기반 추천
            recommendation_type = "content_based"
            products = await self._get_products_by_profile(
                request.skin_type,
                request.concerns,
                request.limit
            )
        
        else:
            # 인기 상품 추천
            recommendation_type = "popular"
            products = await self._get_popular_products(request.limit)
        
        return {
            "recommendation_type": recommendation_type,
            "products": products
        }
    
    async def _get_similar_products(
        self,
        product_id: str,
        limit: int
    ) -> List[ProductSummary]:
        """유사 상품 추천 (같은 카테고리 + 비슷한 가격대)"""
        try:
            # 기준 상품 조회
            base_product = await self.get_product_by_id(product_id)
            if not base_product:
                return []
            
            # 같은 카테고리 상품 조회
            docs = self.db.collection(self.collection)\
                         .where('is_active', '==', True)\
                         .where('category', '==', base_product.category)\
                         .limit(limit * 2)\
                         .stream()
            
            products = []
            for doc in docs:
                if doc.id == product_id:  # 자기 자신 제외
                    continue
                
                try:
                    data = doc.to_dict()
                    product = ProductSummary(**data)
                    
                    # 가격대 유사도 계산 (±30% 이내)
                    price_diff = abs(product.price - base_product.price) / base_product.price
                    if price_diff <= 0.3:
                        products.append(product)
                    
                except Exception as e:
                    continue
            
            # 가격 차이 순으로 정렬
            products.sort(key=lambda p: abs(p.price - base_product.price))
            
            return products[:limit]
            
        except Exception as e:
            logger.error(f"유사 상품 추천 실패: {str(e)}")
            return []
    
    async def _get_popular_products(self, limit: int) -> List[ProductSummary]:
        """인기 상품 추천 (판매량 기준)"""
        try:
            docs = self.db.collection(self.collection)\
                         .where('is_active', '==', True)\
                         .limit(100)\
                         .stream()
            
            products = []
            for doc in docs:
                try:
                    data = doc.to_dict()
                    products.append(ProductSummary(**data))
                except Exception as e:
                    continue
            
            # 판매량 기준 정렬
            products = self._sort_products(products, SortBy.SALES)
            
            return products[:limit]
            
        except Exception as e:
            logger.error(f"인기 상품 조회 실패: {str(e)}")
            return []
    
    async def _get_products_by_profile(
        self,
        skin_type: Optional[str],
        concerns: Optional[List[str]],
        limit: int
    ) -> List[ProductSummary]:
        """피부 타입/고민 기반 상품 추천"""
        try:
            docs = self.db.collection(self.collection)\
                         .where('is_active', '==', True)\
                         .limit(100)\
                         .stream()
            
            products = []
            for doc in docs:
                try:
                    data = doc.to_dict()
                    
                    # 피부 타입 매칭
                    if skin_type:
                        skin_types = data.get('skin_types', [])
                        if skin_type not in skin_types and '전체' not in skin_types:
                            continue
                    
                    # 피부 고민 매칭
                    if concerns:
                        product_concerns = data.get('concerns', [])
                        match_count = sum(1 for c in concerns if c in product_concerns)
                        if match_count == 0:
                            continue
                        
                        # 매칭도 저장
                        data['_match_score'] = match_count
                    
                    products.append(ProductSummary(**data))
                    
                except Exception as e:
                    continue
            
            # 매칭도 순으로 정렬 (있으면)
            if concerns:
                products.sort(
                    key=lambda p: p.__dict__.get('_match_score', 0),
                    reverse=True
                )
            else:
                # 평점 순으로 정렬
                products = self._sort_products(products, SortBy.RATING)
            
            return products[:limit]
            
        except Exception as e:
            logger.error(f"프로필 기반 추천 실패: {str(e)}")
            return []
    
    # ==================== AI 모델 연동 (TODO) ====================
    
    # TODO: BentoML 연동 시 구현
    # async def _get_ai_recommendations(
    #     self,
    #     request: RecommendationRequest
    # ) -> List[ProductSummary]:
    #     """AI 모델 기반 추천"""
    #     try:
    #         # BentoML 서버에 요청
    #         response = await bentoml_client.predict({
    #             "customer_id": request.customer_id,
    #             "product_id": request.product_id,
    #             "limit": request.limit
    #         })
    #         
    #         product_ids = response['recommended_product_ids']
    #         
    #         # 추천된 상품 조회
    #         products = []
    #         for product_id in product_ids:
    #             product = await self.get_product_by_id(product_id)
    #             if product:
    #                 products.append(ProductSummary(**product.dict()))
    #         
    #         return products
    #         
    #     except Exception as e:
    #         logger.error(f"AI 추천 실패: {str(e)}")
    #         # Fallback: 인기 상품 반환
    #         return await self._get_popular_products(request.limit)


# 싱글톤 인스턴스
product_service = ProductService()