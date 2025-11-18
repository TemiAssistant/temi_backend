# app/services/product_service.py
"""
상품 관련 비즈니스 로직
Firestore와 상호작용하며 데이터 처리
실제 products.json 구조에 맞춰 수정됨
"""

from typing import List, Optional, Dict, Any
from app.core.firebase import firestore_db
from app.models.product import (
    ProductDetail, ProductSummary, ProductSearchParams,
    RecommendationRequest, SortBy,
    CategoryInfo, SubCategoryInfo, BrandInfo, FilterOptions
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
    
    # ==================== 검색 ====================
    
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
            filtered_products = []
            
            for doc in docs:
                try:
                    data = doc.to_dict()
                    
                    # 검색 키워드 필터링
                    if params.query:
                        query_lower = params.query.lower()
                        if not (
                            query_lower in data.get('name', '').lower() or
                            query_lower in data.get('brand', '').lower() or
                            query_lower in ' '.join(data.get('ingredients', [])).lower()
                        ):
                            continue
                    
                    # 카테고리 필터링
                    if params.category and data.get('category') != params.category:
                        continue
                    
                    # 서브카테고리 필터링
                    if params.sub_category and data.get('sub_category') != params.sub_category:
                        continue
                    
                    # 브랜드 필터링
                    if params.brand and data.get('brand') != params.brand:
                        continue
                    
                    # 가격 범위 필터링
                    price = data.get('price', 0)
                    if params.min_price is not None and price < params.min_price:
                        continue
                    if params.max_price is not None and price > params.max_price:
                        continue
                    
                    # 피부 타입 필터링
                    if params.skin_type:
                        skin_types = data.get('skin_types', [])
                        if params.skin_type not in skin_types and '모든 피부 타입' not in skin_types and '모든피부' not in skin_types:
                            continue
                    
                    # 재고 필터링
                    if params.in_stock:
                        stock = data.get('stock', {})
                        if stock.get('current', 0) <= 0:
                            continue
                    
                    filtered_products.append(ProductSummary(**data))
                    
                except Exception as e:
                    logger.warning(f"상품 필터링 중 오류: {str(e)}")
                    continue
            
            # 3. 정렬
            filtered_products = self._sort_products(filtered_products, params.sort_by)
            
            # 4. 페이징
            total = len(filtered_products)
            total_pages = (total + params.page_size - 1) // params.page_size
            
            start_idx = (params.page - 1) * params.page_size
            end_idx = start_idx + params.page_size
            
            products_page = filtered_products[start_idx:end_idx]
            
            logger.info(f"검색 결과: {total}개 (페이지: {params.page}/{total_pages})")
            
            return {
                'total': total,
                'page': params.page,
                'page_size': params.page_size,
                'total_pages': total_pages,
                'products': products_page
            }
            
        except Exception as e:
            logger.error(f"상품 검색 실패: {str(e)}")
            raise
    
    def _sort_products(self, products: List[ProductSummary], sort_by: SortBy) -> List[ProductSummary]:
        """상품 리스트 정렬"""
        if sort_by == SortBy.PRICE_LOW:
            return sorted(products, key=lambda p: p.price)
        elif sort_by == SortBy.PRICE_HIGH:
            return sorted(products, key=lambda p: p.price, reverse=True)
        elif sort_by == SortBy.DISCOUNT:
            return sorted(products, key=lambda p: p.discount_rate, reverse=True)
        elif sort_by == SortBy.RECENT:
            return sorted(
                products,
                key=lambda p: p.created_at if p.created_at else datetime.min,
                reverse=True
            )
        else:  # POPULARITY (기본)
            # 할인율이 높은 순으로 정렬 (판매량 데이터가 없으므로)
            return sorted(products, key=lambda p: p.discount_rate, reverse=True)
    
    # ==================== 카테고리별 조회 ====================
    
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
                    continue
            
            logger.info(f"카테고리 '{category}' 상품 조회: {len(products)}개")
            return products
            
        except Exception as e:
            logger.error(f"카테고리별 조회 실패: {str(e)}")
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
                    continue
            
            logger.info(f"브랜드 '{brand}' 상품 조회: {len(products)}개")
            return products
            
        except Exception as e:
            logger.error(f"브랜드별 조회 실패: {str(e)}")
            raise
    
    # ==================== 통계 ====================
    
    async def get_product_count(self) -> Dict[str, Any]:
        """상품 개수 통계"""
        try:
            # 전체 상품
            all_docs = list(self.db.collection(self.collection).stream())
            total_count = len(all_docs)
            
            # 활성/비활성 구분
            active_count = sum(1 for doc in all_docs if doc.to_dict().get('is_active', False))
            inactive_count = total_count - active_count
            
            # 카테고리별 개수
            by_category = {}
            for doc in all_docs:
                data = doc.to_dict()
                if data.get('is_active', False):
                    category = data.get('category', '기타')
                    by_category[category] = by_category.get(category, 0) + 1
            
            return {
                'total_count': total_count,
                'active_count': active_count,
                'inactive_count': inactive_count,
                'by_category': by_category
            }
            
        except Exception as e:
            logger.error(f"상품 개수 조회 실패: {str(e)}")
            raise
    
    async def get_categories(self) -> List[CategoryInfo]:
        """카테고리 목록 및 상품 수 조회"""
        try:
            docs = self.db.collection(self.collection)\
                         .where('is_active', '==', True)\
                         .stream()
            
            category_counts = {}
            for doc in docs:
                data = doc.to_dict()
                category = data.get('category', '기타')
                category_counts[category] = category_counts.get(category, 0) + 1
            
            categories = [
                CategoryInfo(category=cat, product_count=count)
                for cat, count in sorted(category_counts.items())
            ]
            
            logger.info(f"카테고리 조회: {len(categories)}개")
            return categories
            
        except Exception as e:
            logger.error(f"카테고리 조회 실패: {str(e)}")
            raise
    
    async def get_sub_categories(self, category: Optional[str] = None) -> List[SubCategoryInfo]:
        """서브카테고리 목록 조회"""
        try:
            query = self.db.collection(self.collection).where('is_active', '==', True)
            
            if category:
                query = query.where('category', '==', category)
            
            docs = query.stream()
            
            sub_category_counts = {}
            for doc in docs:
                data = doc.to_dict()
                sub_cat = data.get('sub_category', '기타')
                sub_category_counts[sub_cat] = sub_category_counts.get(sub_cat, 0) + 1
            
            sub_categories = [
                SubCategoryInfo(sub_category=sub_cat, product_count=count)
                for sub_cat, count in sorted(sub_category_counts.items())
            ]
            
            logger.info(f"서브카테고리 조회: {len(sub_categories)}개")
            return sub_categories
            
        except Exception as e:
            logger.error(f"서브카테고리 조회 실패: {str(e)}")
            raise
    
    async def get_brands(self) -> List[BrandInfo]:
        """브랜드 목록 및 상품 수 조회"""
        try:
            docs = self.db.collection(self.collection)\
                         .where('is_active', '==', True)\
                         .stream()
            
            brand_counts = {}
            for doc in docs:
                data = doc.to_dict()
                brand = data.get('brand', '기타')
                brand_counts[brand] = brand_counts.get(brand, 0) + 1
            
            brands = [
                BrandInfo(brand=brand, product_count=count)
                for brand, count in sorted(brand_counts.items())
            ]
            
            logger.info(f"브랜드 조회: {len(brands)}개")
            return brands
            
        except Exception as e:
            logger.error(f"브랜드 조회 실패: {str(e)}")
            raise
    
    async def get_filter_options(self) -> FilterOptions:
        """필터 옵션 조회"""
        try:
            docs = list(
                self.db.collection(self.collection)
                .where('is_active', '==', True)
                .stream()
            )
            
            brands = set()
            categories = set()
            sub_categories = set()
            skin_types = set()
            min_price = float('inf')
            max_price = 0
            
            for doc in docs:
                data = doc.to_dict()
                brands.add(data.get('brand', ''))
                categories.add(data.get('category', ''))
                sub_categories.add(data.get('sub_category', ''))
                
                for skin_type in data.get('skin_types', []):
                    skin_types.add(skin_type)
                
                price = data.get('price', 0)
                min_price = min(min_price, price)
                max_price = max(max_price, price)
            
            return FilterOptions(
                brands=sorted([b for b in brands if b]),
                categories=sorted([c for c in categories if c]),
                sub_categories=sorted([s for s in sub_categories if s]),
                skin_types=sorted([s for s in skin_types if s]),
                price_range={'min': int(min_price) if min_price != float('inf') else 0, 'max': int(max_price)}
            )
            
        except Exception as e:
            logger.error(f"필터 옵션 조회 실패: {str(e)}")
            raise
    
    # ==================== 추천 ====================
    
    async def get_recommendations(
        self,
        request: RecommendationRequest
    ) -> Dict[str, Any]:
        """상품 추천"""
        try:
            # 1. 기준 상품 기반 추천
            if request.product_id:
                products = await self._get_similar_products(request.product_id, request.limit)
                recommendation_type = "content_based"
            
            # 2. 피부 타입 기반 추천
            elif request.skin_type:
                products = await self._get_products_by_skin_type(request.skin_type, request.limit)
                recommendation_type = "skin_type_based"
            
            # 3. 인기 상품 추천 (기본)
            else:
                products = await self._get_popular_products(request.limit)
                recommendation_type = "popular"
            
            return {
                'recommendation_type': recommendation_type,
                'products': products
            }
            
        except Exception as e:
            logger.error(f"상품 추천 실패: {str(e)}")
            raise
    
    async def _get_similar_products(
        self,
        product_id: str,
        limit: int
    ) -> List[ProductSummary]:
        """유사 상품 추천"""
        try:
            # 기준 상품 조회
            base_product = await self.get_product_by_id(product_id)
            if not base_product:
                return await self._get_popular_products(limit)
            
            # 같은 카테고리의 상품 조회
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
                    
                    # 가격대가 비슷한 상품 우선
                    price_diff = abs(product.price - base_product.price) / base_product.price
                    if price_diff <= 0.3:  # 30% 이내
                        products.append(product)
                    
                except Exception as e:
                    continue
            
            # 가격 차이순 정렬
            products.sort(key=lambda p: abs(p.price - base_product.price))
            
            return products[:limit]
            
        except Exception as e:
            logger.error(f"유사 상품 추천 실패: {str(e)}")
            return []
    
    async def _get_products_by_skin_type(
        self,
        skin_type: str,
        limit: int
    ) -> List[ProductSummary]:
        """피부 타입별 상품 추천"""
        try:
            docs = self.db.collection(self.collection)\
                         .where('is_active', '==', True)\
                         .limit(100)\
                         .stream()
            
            products = []
            for doc in docs:
                try:
                    data = doc.to_dict()
                    skin_types = data.get('skin_types', [])
                    
                    if skin_type in skin_types or '모든 피부 타입' in skin_types or '모든피부' in skin_types:
                        products.append(ProductSummary(**data))
                        
                except Exception as e:
                    continue
            
            # 할인율 순 정렬
            products.sort(key=lambda p: p.discount_rate, reverse=True)
            
            return products[:limit]
            
        except Exception as e:
            logger.error(f"피부 타입별 상품 조회 실패: {str(e)}")
            return []
    
    async def _get_popular_products(self, limit: int) -> List[ProductSummary]:
        """인기 상품 추천 (할인율 높은 순)"""
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
            
            # 할인율 순 정렬
            products.sort(key=lambda p: p.discount_rate, reverse=True)
            
            return products[:limit]
            
        except Exception as e:
            logger.error(f"인기 상품 조회 실패: {str(e)}")
            return []


# 싱글톤 인스턴스
product_service = ProductService()