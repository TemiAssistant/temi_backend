"""Business logic for product features backed by Firestore."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

import logging

from app.core.firebase import firestore_db
from app.models.product import (
    BrandInfo,
    CategoryInfo,
    FilterOptions,
    ProductDetail,
    ProductSearchParams,
    ProductSummary,
    RecommendationRequest,
    SortBy,
    SubCategoryInfo,
)

logger = logging.getLogger(__name__)


class ProductService:
    """Encapsulates all product queries against Firestore."""

    def __init__(self) -> None:
        self.db = firestore_db
        self.collection = "products"

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _to_int(self, value: Any) -> int:
        """Convert loosely formatted values into integers."""
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
        if original_price <= 0:
            return 0
        try:
            discount = round((original_price - price) / original_price * 100)
            return max(0, min(100, discount))
        except ZeroDivisionError:
            return 0

    def _normalize_stock(self, stock_value: Any) -> Dict[str, int]:
        stock = {
            "current": 0,
            "threshold": 0,
            "unit_weight": 0,
        }
        if isinstance(stock_value, dict):
            stock["current"] = self._to_int(
                stock_value.get("current")
                or stock_value.get("stock")
                or stock_value.get("quantity")
            )
            stock["threshold"] = self._to_int(stock_value.get("threshold"))
            stock["unit_weight"] = self._to_int(stock_value.get("unit_weight"))
            return stock

        current = self._to_int(stock_value)
        if current:
            stock["current"] = current
        return stock

    def _extract_stock_value(self, stock_value: Any) -> Optional[int]:
        if stock_value is None:
            return None
        if isinstance(stock_value, dict):
            return self._to_int(stock_value.get("current"))
        if isinstance(stock_value, (int, float)):
            return int(stock_value)
        try:
            return int(str(stock_value).strip())
        except (TypeError, ValueError):
            return None

    def _split_to_list(self, value: Any) -> List[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            text = value
            for sep in ["/", "|", "·", ";"]:
                text = text.replace(sep, ",")
            return [part.strip() for part in text.split(",") if part.strip()]
        return []

    def _normalize_skin_types(self, data: Dict[str, Any]) -> List[str]:
        if data.get("skin_types"):
            return self._split_to_list(data["skin_types"])
        if data.get("spec"):
            return self._split_to_list(data["spec"])
        return []

    def _normalize_description(self, data: Dict[str, Any]) -> Dict[str, Optional[str]]:
        usage = None
        caution = None
        description = data.get("description")
        if isinstance(description, dict):
            usage = description.get("usage")
            caution = description.get("caution")
        usage = usage or data.get("usage")
        caution = caution or data.get("caution")
        return {"usage": usage, "caution": caution}

    def _normalize_product_data(
        self, data: Dict[str, Any], doc_id: Optional[str] = None
    ) -> Dict[str, Any]:
        if not data:
            data = {}

        price_value = self._to_int(
            data.get("price") or data.get("price_cur") or data.get("priceCur")
        )
        original_price = self._to_int(
            data.get("original_price")
            or data.get("price_org")
            or data.get("priceOrg")
            or price_value
        )
        if original_price <= 0:
            original_price = price_value

        discount_rate = data.get("discount_rate")
        if discount_rate is None:
            discount_rate = self._calculate_discount_rate(original_price, price_value)
        else:
            discount_rate = self._to_int(discount_rate)

        normalized = {
            "product_id": data.get("product_id")
            or data.get("goodsNo")
            or data.get("goods_no")
            or doc_id
            or "unknown_product",
            "name": data.get("name") or "상품 미정",
            "brand": data.get("brand") or "기타",
            "category": data.get("category") or data.get("first_category") or "기타",
            "sub_category": data.get("sub_category") or data.get("mid_category") or "",
            "price": price_value,
            "original_price": original_price,
            "discount_rate": discount_rate,
            "is_active": data.get("is_active", True),
            "stock": self._normalize_stock(data.get("stock")),
            "description": self._normalize_description(data),
            "ingredients": self._split_to_list(data.get("ingredients")),
            "skin_types": self._normalize_skin_types(data),
            "spec": self._split_to_list(data.get("spec") or data.get("skin_types")),
            "image_url": data.get("image_url") or data.get("image"),
            "created_at": data.get("created_at"),
            "updated_at": data.get("updated_at"),
            "first_category": data.get("first_category") or data.get("category"),
            "mid_category": data.get("mid_category") or data.get("sub_category"),
            "zone": data.get("zone"),
        }
        return normalized

    def _sort_products(
        self, products: List[ProductSummary], sort_by: SortBy
    ) -> List[ProductSummary]:
        if sort_by == SortBy.PRICE_LOW:
            return sorted(products, key=lambda p: p.price)
        if sort_by == SortBy.PRICE_HIGH:
            return sorted(products, key=lambda p: p.price, reverse=True)
        if sort_by == SortBy.DISCOUNT:
            return sorted(products, key=lambda p: p.discount_rate, reverse=True)
        if sort_by == SortBy.RECENT:
            return sorted(
                products,
                key=lambda p: p.created_at if p.created_at else datetime.min,
                reverse=True,
            )
        return sorted(products, key=lambda p: p.discount_rate, reverse=True)

    # ------------------------------------------------------------------ #
    # CRUD helpers
    # ------------------------------------------------------------------ #

    async def get_product_by_id(self, product_id: str) -> Optional[ProductDetail]:
        try:
            doc = self.db.collection(self.collection).document(product_id).get()
            if not doc.exists:
                return None
            data = self._normalize_product_data(doc.to_dict(), doc.id)
            return ProductDetail(**data)
        except Exception as exc:
            logger.error("Failed to fetch product %s: %s", product_id, exc)
            raise

    async def get_all_products(
        self, limit: Optional[int] = None, offset: int = 0
    ) -> List[ProductSummary]:
        try:
            docs = list(self.db.collection(self.collection).stream())
            docs = docs[offset:]
            if limit:
                docs = docs[:limit]

            products: List[ProductSummary] = []
            for doc in docs:
                data = self._normalize_product_data(doc.to_dict(), doc.id)
                if not data.get("is_active", True):
                    continue
                products.append(ProductSummary(**data))
            return products
        except Exception as exc:
            logger.error("Failed to fetch product list: %s", exc)
            raise

    async def get_products_by_category(
        self, category: str, limit: int = 20
    ) -> List[ProductSummary]:
        try:
            docs = (
                self.db.collection(self.collection)
                .where("is_active", "==", True)
                .where("category", "==", category)
                .limit(limit)
                .stream()
            )
            products = []
            for doc in docs:
                data = self._normalize_product_data(doc.to_dict(), doc.id)
                products.append(ProductSummary(**data))
            return products
        except Exception as exc:
            logger.error("Failed to fetch category products: %s", exc)
            raise

    async def get_products_by_brand(
        self, brand: str, limit: int = 20
    ) -> List[ProductSummary]:
        try:
            docs = (
                self.db.collection(self.collection)
                .where("is_active", "==", True)
                .where("brand", "==", brand)
                .limit(limit)
                .stream()
            )
            products = []
            for doc in docs:
                data = self._normalize_product_data(doc.to_dict(), doc.id)
                products.append(ProductSummary(**data))
            return products
        except Exception as exc:
            logger.error("Failed to fetch brand products: %s", exc)
            raise

    # ------------------------------------------------------------------ #
    # Search / filters
    # ------------------------------------------------------------------ #

    async def search_products(self, params: ProductSearchParams) -> Dict[str, Any]:
        try:
            docs = list(self.db.collection(self.collection).stream())
            filtered: List[ProductSummary] = []

            for doc in docs:
                try:
                    data = self._normalize_product_data(doc.to_dict(), doc.id)
                except Exception as convert_error:
                    logger.warning("Failed to normalize %s: %s", doc.id, convert_error)
                    continue

                if params.query:
                    keyword = params.query.lower()
                    name_match = keyword in data.get("name", "").lower()
                    brand_match = keyword in data.get("brand", "").lower()
                    ingredient_match = keyword in " ".join(
                        data.get("ingredients", [])
                    ).lower()
                    if not (name_match or brand_match or ingredient_match):
                        continue

                if params.first_category and data.get("first_category") != params.first_category:
                    continue
                if params.mid_category and data.get("mid_category") != params.mid_category:
                    continue
                if params.brand and data.get("brand") != params.brand:
                    continue

                price = data.get("price", 0)
                if params.min_price is not None and price < params.min_price:
                    continue
                if params.max_price is not None and price > params.max_price:
                    continue

                if params.spec:
                    requested_specs = [
                        spec.strip() for spec in params.spec if isinstance(spec, str) and spec.strip()
                    ]
                    product_specs = [
                        spec.strip() for spec in data.get("spec", []) if isinstance(spec, str) and spec.strip()
                    ]
                    if requested_specs:
                        universal_terms = {"모든 피부 타입", "모든피부", "모든 피부"}
                        product_has_all = any(spec in universal_terms for spec in product_specs)
                        if not product_has_all:
                            request_has_all = any(spec in universal_terms for spec in requested_specs)
                            if request_has_all:
                                match_found = bool(product_specs)
                            else:
                                match_found = any(spec in product_specs for spec in requested_specs)
                            if not match_found:
                                continue

                if params.in_stock:
                    stock_info = data.get("stock", {})
                    if stock_info.get("current", 0) <= 0:
                        continue

                filtered.append(ProductSummary(**data))

            filtered = self._sort_products(filtered, params.sort_by)
            total = len(filtered)
            total_pages = (total + params.page_size - 1) // params.page_size
            start_idx = (params.page - 1) * params.page_size
            end_idx = start_idx + params.page_size
            products_page = filtered[start_idx:end_idx]

            return {
                "total": total,
                "page": params.page,
                "page_size": params.page_size,
                "total_pages": total_pages,
                "products": products_page,
            }
        except Exception as exc:
            logger.error("Product search failed: %s", exc)
            raise

    async def get_filter_options(self) -> FilterOptions:
        try:
            docs = self.db.collection(self.collection).stream()
            brands = set()
            first_categories = set()
            mid_categories = set()
            specs = set()
            min_price = float("inf")
            max_price = 0

            for doc in docs:
                try:
                    data = self._normalize_product_data(doc.to_dict(), doc.id)
                except Exception as convert_error:
                    logger.warning("Failed to normalize filters for %s: %s", doc.id, convert_error)
                    continue

                if data.get("brand"):
                    brands.add(data["brand"])
                if data.get("first_category"):
                    first_categories.add(data["first_category"])
                if data.get("mid_category"):
                    mid_categories.add(data["mid_category"])
                for spec_value in data.get("spec", []):
                    specs.add(spec_value)

                price = data.get("price", 0)
                if price > 0:
                    min_price = min(min_price, price)
                    max_price = max(max_price, price)

            if min_price == float("inf"):
                min_price = 0

            return FilterOptions(
                brands=sorted(brands),
                first_categories=sorted(first_categories),
                mid_categories=sorted(mid_categories),
                spec=sorted(specs),
            )
        except Exception as exc:
            logger.error("Failed to fetch filter options: %s", exc)
            raise

    # ------------------------------------------------------------------ #
    # Statistics and derived data
    # ------------------------------------------------------------------ #

    async def get_product_count(self) -> Dict[str, Any]:
        try:
            docs = list(self.db.collection(self.collection).stream())
            normalized_docs = []
            for doc in docs:
                try:
                    normalized_docs.append(self._normalize_product_data(doc.to_dict(), doc.id))
                except Exception as convert_error:
                    logger.warning("Failed to normalize product for count %s: %s", doc.id, convert_error)

            total_count = len(normalized_docs)
            active_count = sum(1 for data in normalized_docs if data.get("is_active", True))
            inactive_count = total_count - active_count

            by_category: Dict[str, int] = {}
            for data in normalized_docs:
                if data.get("is_active", True):
                    category = data.get("category", "기타")
                    by_category[category] = by_category.get(category, 0) + 1

            return {
                "total_count": total_count,
                "active_count": active_count,
                "inactive_count": inactive_count,
                "by_category": by_category,
            }
        except Exception as exc:
            logger.error("Failed to fetch product count: %s", exc)
            raise


    async def get_categories(self) -> List[CategoryInfo]:
        try:
            docs = (
                self.db.collection(self.collection)
                .where("is_active", "==", True)
                .stream()
            )
            category_counts: Dict[str, int] = {}
            for doc in docs:
                data = self._normalize_product_data(doc.to_dict(), doc.id)
                category = data.get("category", "기타")
                category_counts[category] = category_counts.get(category, 0) + 1

            return [
                CategoryInfo(category=cat, product_count=count)
                for cat, count in sorted(category_counts.items())
            ]
        except Exception as exc:
            logger.error("Failed to fetch categories: %s", exc)
            raise

    async def get_sub_categories(
        self, category: Optional[str] = None
    ) -> List[SubCategoryInfo]:
        try:
            query = self.db.collection(self.collection).where("is_active", "==", True)
            if category:
                query = query.where("category", "==", category)

            docs = query.stream()
            sub_category_counts: Dict[str, int] = {}
            for doc in docs:
                data = self._normalize_product_data(doc.to_dict(), doc.id)
                sub_cat = data.get("sub_category", "기타")
                sub_category_counts[sub_cat] = sub_category_counts.get(sub_cat, 0) + 1

            return [
                SubCategoryInfo(sub_category=sub_cat, product_count=count)
                for sub_cat, count in sorted(sub_category_counts.items())
            ]
        except Exception as exc:
            logger.error("Failed to fetch sub categories: %s", exc)
            raise

    async def get_brands(self) -> List[BrandInfo]:
        try:
            docs = (
                self.db.collection(self.collection)
                .where("is_active", "==", True)
                .stream()
            )
            brand_counts: Dict[str, int] = {}
            for doc in docs:
                data = self._normalize_product_data(doc.to_dict(), doc.id)
                brand = data.get("brand", "기타")
                brand_counts[brand] = brand_counts.get(brand, 0) + 1

            return [
                BrandInfo(brand=brand, product_count=count)
                for brand, count in sorted(brand_counts.items())
            ]
        except Exception as exc:
            logger.error("Failed to fetch brands: %s", exc)
            raise

    # ------------------------------------------------------------------ #
    # Recommendations
    # ------------------------------------------------------------------ #

    async def get_recommendations(
        self, request: RecommendationRequest
    ) -> Dict[str, Any]:
        try:
            if request.product_id:
                products = await self._get_similar_products(request.product_id, request.limit)
                recommendation_type = "content_based"
            elif request.skin_type:
                products = await self._get_products_by_skin_type(request.skin_type, request.limit)
                recommendation_type = "skin_type_based"
            else:
                products = await self._get_popular_products(request.limit)
                recommendation_type = "popular"

            return {"recommendation_type": recommendation_type, "products": products}
        except Exception as exc:
            logger.error("Recommendation failed: %s", exc)
            raise

    async def _get_similar_products(
        self, product_id: str, limit: int
    ) -> List[ProductSummary]:
        base_product = await self.get_product_by_id(product_id)
        if not base_product:
            return await self._get_popular_products(limit)

        docs = (
            self.db.collection(self.collection)
            .where("is_active", "==", True)
            .where("category", "==", base_product.category)
            .limit(limit * 2)
            .stream()
        )
        products: List[ProductSummary] = []
        for doc in docs:
            if doc.id == product_id:
                continue
            try:
                data = self._normalize_product_data(doc.to_dict(), doc.id)
                product = ProductSummary(**data)
                if base_product.price:
                    price_diff = abs(product.price - base_product.price) / base_product.price
                    if price_diff <= 0.3:
                        products.append(product)
            except Exception:
                continue

        products.sort(key=lambda p: abs(p.price - base_product.price))
        return products[:limit]

    async def _get_products_by_skin_type(
        self, skin_type: str, limit: int
    ) -> List[ProductSummary]:
        docs = (
            self.db.collection(self.collection)
            .where("is_active", "==", True)
            .limit(200)
            .stream()
        )
        universal_terms = {"모든 피부 타입", "모든피부", "모든 피부"}
        products: List[ProductSummary] = []
        for doc in docs:
            try:
                data = self._normalize_product_data(doc.to_dict(), doc.id)
                skin_types = data.get("skin_types", [])
                if skin_type in skin_types or any(term in skin_types for term in universal_terms):
                    products.append(ProductSummary(**data))
            except Exception:
                continue

        products.sort(key=lambda p: p.discount_rate, reverse=True)
        return products[:limit]

    async def _get_popular_products(self, limit: int) -> List[ProductSummary]:
        docs = (
            self.db.collection(self.collection)
            .where("is_active", "==", True)
            .limit(200)
            .stream()
        )
        products: List[ProductSummary] = []
        for doc in docs:
            try:
                data = self._normalize_product_data(doc.to_dict(), doc.id)
                products.append(ProductSummary(**data))
            except Exception:
                continue

        products.sort(key=lambda p: p.discount_rate, reverse=True)
        return products[:limit]


product_service = ProductService()
