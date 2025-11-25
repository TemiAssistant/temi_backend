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
    
    def _to_int(self, value: Any) -> int:
        """숫자로 해석 가능한 값을 안전하게 정수로 변환"""
        if value is None:
            return 0
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, (int, float)):
            return int(value)
        try:
            cleaned = str(value).replace(",", "").strip()
            if not cleaned:
                return 0
            return int(float(cleaned))
        except (ValueError, TypeError):
            return 0
    
    def _calculate_discount_rate(self, original_price: int, price: int) -> int:
        """0~100 범위의 할인율을 계산"""
        if not original_price:
            return 0
        try:
            discount = round((original_price - price) / original_price * 100)
            return max(0, min(100, discount))
        except ZeroDivisionError:
            return 0
    
    def _normalize_stock(self, stock_value: Any) -> Dict[str, int]:
        """ProductStock 스키마에 맞는 재고 정보로 정규화"""
        stock = {
            'current': 0,
            'threshold': 0,
            'unit_weight': 0
        }
        
        if isinstance(stock_value, dict):
            stock['current'] = self._to_int(
                stock_value.get('current') or
                stock_value.get('stock') or
                stock_value.get('quantity')
            )
            stock['threshold'] = self._to_int(stock_value.get('threshold'))
            stock['unit_weight'] = self._to_int(stock_value.get('unit_weight'))
            return stock
        
        current = self._to_int(stock_value)
        if current:
            stock['current'] = current
        return stock
    
    def _split_to_list(self, value: Any) -> List[str]:
        """콤마·슬래시 등으로 구분된 문자열을 리스트로 분리"""
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            text = value
            for sep in ['/', '|', '·', ';']:
                text = text.replace(sep, ',')
            return [part.strip() for part in text.split(',') if part.strip()]
        return []
    
    def _normalize_skin_types(self, data: Dict[str, Any]) -> List[str]:
        """피부 타입 정보를 리스트 형태로 추출"""
        if data.get('skin_types'):
            return self._split_to_list(data['skin_types'])
        if data.get('spec'):
            return self._split_to_list(data['spec'])
        return []
    
    def _normalize_description(self, data: Dict[str, Any]) -> Dict[str, Optional[str]]:
        """기존 usage/caution 필드를 통합"""
        usage = None
        caution = None
        
        description = data.get('description')
        if isinstance(description, dict):
            usage = description.get('usage')
            caution = description.get('caution')
        
        usage = usage or data.get('usage')
        caution = caution or data.get('caution')
        
        return {
            'usage': usage,
            'caution': caution
        }
    
    def _normalize_product_data(
        self,
        data: Dict[str, Any],
        doc_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Firestore 문서를 Product 모델 구조에 맞춰 변환"""
        if not data:
            data = {}
        
        price_value = self._to_int(
            data.get('price') or data.get('price_cur') or data.get('priceCur')
        )
        original_price = self._to_int(
            data.get('original_price') or
            data.get('price_org') or
            data.get('priceOrg') or
            price_value
        )
        if original_price <= 0:
            original_price = price_value
        
        discount_rate = data.get('discount_rate')
        if discount_rate is None:
            discount_rate = self._calculate_discount_rate(original_price, price_value)
        else:
            discount_rate = self._to_int(discount_rate)
        
        normalized = {
            'product_id': data.get('product_id') or
                          data.get('goodsNo') or
                          data.get('goods_no') or
                          doc_id or
                          'unknown_product',
            'name': data.get('name') or '미정 상품',
            'brand': data.get('brand') or '기타',
            'category': data.get('category') or data.get('first_category') or '기타',
            'sub_category': data.get('sub_category') or data.get('mid_category') or '',
            'price': price_value,
            'original_price': original_price,
            'discount_rate': discount_rate,
            'is_active': data.get('is_active', True),
            'stock': self._normalize_stock(data.get('stock')),
            'description': self._normalize_description(data),
            'ingredients': self._split_to_list(data.get('ingredients')),
            'skin_types': self._normalize_skin_types(data),
            'spec': self._split_to_list(data.get('spec') or data.get('skin_types')),
            'image_url': data.get('image_url') or data.get('image'),
            'created_at': data.get('created_at'),
            'updated_at': data.get('updated_at'),
            'first_category': data.get('first_category') or data.get('category'),
            'mid_category': data.get('mid_category') or data.get('sub_category')
        }
        
        return normalized
    
    # ==================== 기본 조회 ====================
    
    async def get_product_by_id(self, product_id: str) -> Optional[ProductDetail]:
        """상품 ID로 상세 정보 조회"""
        try:
            doc = self.db.collection(self.collection).document(product_id).get()
            
            if not doc.exists:
                logger.warning(f"상품을 찾을 수 없음: {product_id}")
                return None
            
            data = self._normalize_product_data(doc.to_dict(), doc.id)
            return ProductDetail(**data)
            
        except Exception as e:
            logger.error(f"상품 조회 실패: {product_id}, 오류: {str(e)}")
            raise
    
    async def get_all_products(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """전체 상품 조회"""
        try:
            print(f"🔍 상품 조회 시작: limit={limit}, offset={offset}")  # 디버그
        
            products_ref = self.db.collection('products')
        
            # offset은 Firestore에서 비효율적이므로 limit만 사용
            if limit:
                products_ref = products_ref.limit(limit)
        
            print(f"📊 쿼리 생성 완료")  # 디버그
        
            docs = list(products_ref.stream())
            print(f"📦 문서 개수: {len(docs)}")  # 디버그
        
            products = []
            for doc in docs:
                try:
                    data = self._normalize_product_data(doc.to_dict(), doc.id)
                    
                    if not data.get('is_active', True):
                        continue
                    products.append(ProductSummary(**data))
                except Exception as convert_error:
                    logger.warning(f"상품 데이터 추출 실패 (ID: {doc.id}): {convert_error}")
                    continue
        
            print(f"✅ 상품 처리 완료: {len(products)}개")  # 디버그
            return products
        
        except Exception as e:
            print(f"❌ 상품 조회 실패: {str(e)}")  # 디버그
            logger.error(f"상품 조회 실패: {str(e)}")
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
            docs = list(self.db.collection(self.collection).stream())
            logger.info(f"검색 대상 상품: {len(docs)}개")
            
            # 2. 메모리에서 필터링
            filtered_products = []
            
            for doc in docs:
                try:
                    data = self._normalize_product_data(doc.to_dict(), doc.id)
                    
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
                    if params.first_category and data.get('first_category') != params.first_category:
                        continue
                    
                    # 서브카테고리 필터링
                    if params.mid_category and data.get('mid_category') != params.mid_category:
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
                    if params.spec:
                        requested_specs = [str(s).strip() for s in params.spec if str(s).strip()]
                        product_specs = [str(s).strip() for s in data.get('spec', []) if str(s).strip()]
                        if requested_specs:
                            has_all = any(spec in ('모든 피부 타입', '모든피부', '모든 피부') for spec in product_specs)
                            if not has_all:
                                # 요청에 '모든 피부 타입'이 포함되어 있으면 모두 허용
                                request_has_all = any(
                                    req in ('모든 피부 타입', '모든피부', '모든 피부') for req in requested_specs
                                )
                                if request_has_all:
                                    pass
                                else:
                                    if not any(req in product_specs for req in requested_specs):
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
        else:  # 인기순(기본)
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
                    data = self._normalize_product_data(doc.to_dict(), doc.id)
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
                    data = self._normalize_product_data(doc.to_dict(), doc.id)
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
            raw_docs = list(self.db.collection(self.collection).stream())
            normalized_docs = []
            for doc in raw_docs:
                try:
                    normalized_docs.append(self._normalize_product_data(doc.to_dict(), doc.id))
                except Exception as convert_error:
                    logger.warning(f"상품 개수 계산용 데이터 변환 실패 (ID: {doc.id}): {convert_error}")
            
            total_count = len(normalized_docs)
            active_count = sum(1 for data in normalized_docs if data.get('is_active', True))
            inactive_count = total_count - active_count
            
            # 카테고리별 개수
            by_category = {}
            for data in normalized_docs:
                if data.get('is_active', True):
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
                data = self._normalize_product_data(doc.to_dict(), doc.id)
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
                data = self._normalize_product_data(doc.to_dict(), doc.id)
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
                data = self._normalize_product_data(doc.to_dict(), doc.id)
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
    
    # app/services/product_service.py

    async def get_filter_options(self) -> Dict[str, Any]:
        """
        필터 옵션 조회
        Firestore의 brand, first_category, mid_category, spec 필드 사용
        """
        try:
            products_ref = self.db.collection(self.collection)
            docs = products_ref.stream()
        
            brands = set()
            first_categories = set()  # ← 변경
            mid_categories = set()    # ← 변경
            specs = set()             # ← 변경 (spec → specs)
        
            min_price = float('inf')
            max_price = 0
        
            for doc in docs:
                try:
                    data = self._normalize_product_data(doc.to_dict(), doc.id)
                except Exception as convert_error:
                    logger.warning(f"필터 옵션 변환 실패 (ID: {doc.id}): {convert_error}")
                    continue
            
            # 브랜드
                if data.get('brand'):
                    brands.add(data['brand'])
            
            # first_category (대분류)
                if data.get('first_category'):
                    first_categories.add(data['first_category'])
            
            # mid_category (중분류)
                if data.get('mid_category'):
                    mid_categories.add(data['mid_category'])
            
            # spec (피부타입)
                for spec_value in data.get('spec', []):
                    specs.add(spec_value)
            
                # 가격 범위
                price = data.get('price', 0)
                if price > 0:
                    min_price = min(min_price, price)
                    max_price = max(max_price, price)
        
            if min_price == float('inf'):
                min_price = 0
        
            return {
                'brands': sorted(list(brands)),
                'first_categories': sorted(list(first_categories)),
                'mid_categories': sorted(list(mid_categories)),
                'spec': sorted(list(specs)),  # 'skin_types' 대신 'spec'
                'price_range': {
                    'min': int(min_price),
                    'max': int(max_price)
                }
            }
        
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
                    data = self._normalize_product_data(doc.to_dict(), doc.id)
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
                    data = self._normalize_product_data(doc.to_dict(), doc.id)
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
                    data = self._normalize_product_data(doc.to_dict(), doc.id)
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
