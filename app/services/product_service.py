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
            
            logger.info(f"상품 조회 완료 - {len(products)}개 (limit: {limit}, offset: {offset})")
            return products
            
        except Exception as e:
            logger.error(f"전체 상품 조회 실패: {str(e)}")
            raise
    
    # ==================== 👇 검색 개선 ====================
    
    async def search_products(
        self,
        params: ProductSearchParams
    ) -> Dict[str, Any]:
        """
        상품 검색 (복합 필터링)
        Firestore 제한을 피하기 위해 전체 로드 후 메모리에서 필터링
        """
        try:
            # 1. 활성 상품 전체 로드
            query = self.db.collection(self.collection)\
                          .where('is_active', '==', True)
            
            docs = list(query.stream())
            logger.info(f"검색 대상 상품: {len(docs)}개")
            
            # 2. 메모리에서 필터링
            products = []
            for doc in docs:
                try:
                    data = doc.to_dict()
                    
                    # 재고 필터
                    if params.in_stock and data.get('stock', {}).get('current', 0) <= 0:
                        continue
                    
                    # 키워드 검색 (이름, 브랜드, 태그, 카테고리, 서브카테고리)
                    if params.query:
                        query_lower = params.query.lower().strip()
                        
                        # 검색 대상 필드
                        name = data.get('name', '').lower()
                        brand = data.get('brand', '').lower()
                        category = data.get('category', '').lower()
                        sub_category = data.get('sub_category', '').lower()
                        tags = [tag.lower() for tag in data.get('tags', [])]
                        
                        # 하나라도 매칭되면 포함
                        name_match = query_lower in name
                        brand_match = query_lower in brand
                        category_match = query_lower in category
                        sub_category_match = query_lower in sub_category
                        tag_match = any(query_lower in tag for tag in tags)
                        
                        if not (name_match or brand_match or category_match or 
                                sub_category_match or tag_match):
                            continue
                    
                    # 카테고리 필터
                    if params.category:
                        if data.get('category', '') != params.category:
                            continue
                    
                    # 브랜드 필터
                    if params.brand:
                        if data.get('brand', '') != params.brand:
                            continue
                    
                    # 가격 필터
                    product_price = data.get('price', 0)
                    if params.min_price is not None and product_price < params.min_price:
                        continue
                    if params.max_price is not None and product_price > params.max_price:
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
                    
                    products.append(ProductSummary(**data))
                    
                except Exception as e:
                    logger.warning(f"상품 파싱 실패: {doc.id}, 오류: {str(e)}")
                    continue
            
            logger.info(f"필터링 후 상품: {len(products)}개")
            
            # 3. 정렬
            products = self._sort_products(products, params.sort_by)
            
            # 4. 페이징
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
            return products
        
        return products
    
    # ==================== 상품 개수 조회 ====================
    
    async def get_product_count(self) -> Dict[str, int]:
        try:
            # 전체 상품 수
            all_docs = self.db.collection(self.collection).stream()
            total_count = sum(1 for _ in all_docs)
            
            # 활성 상품 수
            active_docs = self.db.collection(self.collection)\
                                .where('is_active', '==', True)\
                                .stream()
            active_count = sum(1 for _ in active_docs)
            
            # 비활성 상품 수
            inactive_count = total_count - active_count
            
            logger.info(f"상품 개수 조회 완료 - 전체: {total_count}, 활성: {active_count}, 비활성: {inactive_count}")
            
            return {
                "total_count": total_count,
                "active_count": active_count,
                "inactive_count": inactive_count
            }
            
        except Exception as e:
            logger.error(f"상품 개수 조회 실패: {str(e)}")
            raise
    
    # ==================== 필터 옵션 조회 ====================
    
    async def get_filter_options(self) -> Dict[str, List[str]]:
        """
        필터 옵션 조회 (브랜드, 카테고리, 서브카테고리, 태그)
        
        Returns:
            Dict: {
                "brands": 브랜드 목록,
                "categories": 카테고리 목록,
                "sub_categories": 서브카테고리 목록,
                "tags": 태그 목록
            }
        """
        try:
            docs = self.db.collection(self.collection)\
                         .where('is_active', '==', True)\
                         .stream()
            
            brands_set = set()
            categories_set = set()
            sub_categories_set = set()
            tags_set = set()
            
            for doc in docs:
                data = doc.to_dict()
                
                # 브랜드
                if data.get('brand'):
                    brands_set.add(data['brand'])
                
                # 카테고리
                if data.get('category'):
                    categories_set.add(data['category'])
                
                # 서브카테고리
                if data.get('sub_category'):
                    sub_categories_set.add(data['sub_category'])
                
                # 태그
                if data.get('tags'):
                    tags_set.update(data['tags'])
            
            return {
                "brands": sorted(list(brands_set)),
                "categories": sorted(list(categories_set)),
                "sub_categories": sorted(list(sub_categories_set)),
                "tags": sorted(list(tags_set))
            }
            
        except Exception as e:
            logger.error(f"필터 옵션 조회 실패: {str(e)}")
            raise
    
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
                    "description": None
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
                    "logo_url": None
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
        
        if request.product_id:
            recommendation_type = "content_based"
            products = await self._get_similar_products(request.product_id, request.limit)
        
        elif request.customer_id:
            recommendation_type = "collaborative"
            products = await self._get_popular_products(request.limit)
        
        elif request.skin_type or request.concerns:
            recommendation_type = "content_based"
            products = await self._get_products_by_profile(
                request.skin_type,
                request.concerns,
                request.limit
            )
        
        else:
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
        """유사 상품 추천"""
        try:
            base_product = await self.get_product_by_id(product_id)
            if not base_product:
                return []
            
            docs = self.db.collection(self.collection)\
                         .where('is_active', '==', True)\
                         .where('category', '==', base_product.category)\
                         .limit(limit * 2)\
                         .stream()
            
            products = []
            for doc in docs:
                if doc.id == product_id:
                    continue
                
                try:
                    data = doc.to_dict()
                    product = ProductSummary(**data)
                    
                    price_diff = abs(product.price - base_product.price) / base_product.price
                    if price_diff <= 0.3:
                        products.append(product)
                    
                except Exception as e:
                    continue
            
            products.sort(key=lambda p: abs(p.price - base_product.price))
            
            return products[:limit]
            
        except Exception as e:
            logger.error(f"유사 상품 추천 실패: {str(e)}")
            return []
    
    async def _get_popular_products(self, limit: int) -> List[ProductSummary]:
        """인기 상품 추천"""
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
                    
                    if skin_type:
                        skin_types = data.get('skin_types', [])
                        if skin_type not in skin_types and '전체' not in skin_types:
                            continue
                    
                    if concerns:
                        product_concerns = data.get('concerns', [])
                        match_count = sum(1 for c in concerns if c in product_concerns)
                        if match_count == 0:
                            continue
                        
                        data['_match_score'] = match_count
                    
                    products.append(ProductSummary(**data))
                    
                except Exception as e:
                    continue
            
            if concerns:
                products.sort(
                    key=lambda p: p.__dict__.get('_match_score', 0),
                    reverse=True
                )
            else:
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