# app/models/payment.py
"""
결제 관련 Pydantic 모델
Toss Payments 연동
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


# ==================== Enums ====================

class PaymentMethod(str, Enum):
    """결제 수단"""
    CARD = "카드"
    TRANSFER = "계좌이체"
    VIRTUAL_ACCOUNT = "가상계좌"
    MOBILE = "휴대폰"
    GIFT_CERTIFICATE = "상품권"
    EASY_PAY = "간편결제"


class PaymentStatus(str, Enum):
    """결제 상태"""
    READY = "READY"              # 결제 준비
    IN_PROGRESS = "IN_PROGRESS"  # 결제 진행중
    WAITING_FOR_DEPOSIT = "WAITING_FOR_DEPOSIT"  # 입금 대기
    DONE = "DONE"                # 결제 완료
    CANCELED = "CANCELED"        # 결제 취소
    PARTIAL_CANCELED = "PARTIAL_CANCELED"  # 부분 취소
    ABORTED = "ABORTED"          # 결제 중단
    EXPIRED = "EXPIRED"          # 결제 만료


class OrderStatus(str, Enum):
    """주문 상태"""
    PENDING = "결제대기"
    PAID = "결제완료"
    PREPARING = "상품준비중"
    SHIPPING = "배송중"
    DELIVERED = "배송완료"
    CANCELED = "주문취소"
    REFUNDED = "환불완료"


# ==================== 결제 요청 모델 ====================

class PaymentItem(BaseModel):
    """결제 상품 항목"""
    product_id: str = Field(..., description="상품 ID")
    name: str = Field(..., description="상품명")
    quantity: int = Field(..., ge=1, description="수량")
    price: int = Field(..., ge=0, description="단가")
    total_price: int = Field(..., ge=0, description="총 가격")


class PaymentInitiateRequest(BaseModel):
    """결제 시작 요청"""
    customer_id: Optional[str] = Field(None, description="고객 ID")
    customer_name: str = Field(..., description="주문자명")
    customer_email: Optional[str] = Field(None, description="주문자 이메일")
    customer_phone: str = Field(..., description="주문자 전화번호")
    items: List[PaymentItem] = Field(..., description="주문 상품 목록")
    total_amount: int = Field(..., ge=0, description="총 결제 금액")
    use_points: int = Field(0, ge=0, description="사용 포인트")
    final_amount: int = Field(..., ge=0, description="최종 결제 금액")


class PaymentInitiateResponse(BaseModel):
    """결제 시작 응답"""
    success: bool = True
    payment_key: str = Field(..., description="결제 키")
    order_id: str = Field(..., description="주문 ID")
    amount: int = Field(..., description="결제 금액")
    order_name: str = Field(..., description="주문명")
    customer_name: str = Field(..., description="주문자명")
    qr_data: str = Field(..., description="QR 코드 데이터")
    checkout_url: str = Field(..., description="결제 페이지 URL")
    created_at: datetime = Field(..., description="생성 시간")


# ==================== 결제 승인 모델 ====================

class PaymentApproveRequest(BaseModel):
    """결제 승인 요청"""
    payment_key: str = Field(..., description="결제 키")
    order_id: str = Field(..., description="주문 ID")
    amount: int = Field(..., description="결제 금액")


class PaymentApproveResponse(BaseModel):
    """결제 승인 응답"""
    success: bool = True
    payment_key: str
    order_id: str
    status: PaymentStatus
    method: Optional[str] = None
    total_amount: int
    balance_amount: int
    supplied_amount: int
    vat: int
    approved_at: datetime
    receipt_url: Optional[str] = None


# ==================== 결제 취소 모델 ====================

class PaymentCancelRequest(BaseModel):
    """결제 취소 요청"""
    payment_key: str = Field(..., description="결제 키")
    cancel_reason: str = Field(..., description="취소 사유")
    cancel_amount: Optional[int] = Field(None, description="취소 금액 (부분 취소)")
    refundable_amount: Optional[int] = Field(None, description="환불 가능 금액")


class PaymentCancelResponse(BaseModel):
    """결제 취소 응답"""
    success: bool = True
    payment_key: str
    order_id: str
    status: PaymentStatus
    canceled_at: datetime
    cancel_amount: int
    cancel_reason: str


# ==================== 주문 모델 ====================

class Order(BaseModel):
    """주문 정보"""
    order_id: str
    customer_id: Optional[str] = None
    customer_name: str
    customer_email: Optional[str] = None
    customer_phone: str
    items: List[PaymentItem]
    total_amount: int
    discount_amount: int
    use_points: int
    final_amount: int
    payment_key: Optional[str] = None
    payment_method: Optional[str] = None
    payment_status: PaymentStatus
    order_status: OrderStatus
    created_at: datetime
    paid_at: Optional[datetime] = None
    canceled_at: Optional[datetime] = None


class OrderResponse(BaseModel):
    """주문 조회 응답"""
    success: bool = True
    order: Order


class OrderListResponse(BaseModel):
    """주문 목록 응답"""
    success: bool = True
    orders: List[Order]
    total: int