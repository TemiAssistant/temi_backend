# app/api/payments.py
"""
결제 관련 API 엔드포인트
"""

from fastapi import APIRouter, HTTPException, Path, Query
from typing import Optional
import logging

from app.models.payment import (
    PaymentInitiateRequest,
    PaymentInitiateResponse,
    PaymentApproveRequest,
    PaymentApproveResponse,
    PaymentCancelRequest,
    PaymentCancelResponse,
    OrderResponse,
    OrderListResponse
)
from app.services.payment_service import payment_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/payments", tags=["Payments"])


# ==================== 결제 시작 ====================

@router.post(
    "/initiate",
    response_model=PaymentInitiateResponse,
    summary="결제 시작",
    description="결제를 시작하고 QR 코드를 생성합니다"
)
async def initiate_payment(request: PaymentInitiateRequest):
    """
    결제 시작
    
    **프로세스:**
    1. 주문 생성
    2. 결제 키 생성
    3. QR 코드 데이터 생성
    4. 결제 페이지 URL 반환
    
    **Temi에서 사용:**
    - QR 코드를 Temi 화면에 표시
    - 고객이 앱으로 스캔하여 결제
    
    Returns:
        PaymentInitiateResponse: QR 코드 및 결제 정보
    """
    try:
        result = await payment_service.initiate_payment(request)
        return result
        
    except Exception as e:
        logger.error(f"결제 시작 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"결제 시작 중 오류가 발생했습니다: {str(e)}"
        )


# ==================== 결제 승인 ====================

@router.post(
    "/approve",
    response_model=PaymentApproveResponse,
    summary="결제 승인",
    description="Toss Payments로 결제를 승인합니다"
)
async def approve_payment(request: PaymentApproveRequest):
    """
    결제 승인
    
    **호출 시점:**
    - 고객이 결제를 완료한 후
    - 프론트엔드(앱)에서 호출
    
    **프로세스:**
    1. Toss Payments API 호출
    2. 결제 승인
    3. 주문 상태 업데이트
    
    Returns:
        PaymentApproveResponse: 결제 승인 결과
    """
    try:
        result = await payment_service.approve_payment(request)
        return result
        
    except Exception as e:
        logger.error(f"결제 승인 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"결제 승인 중 오류가 발생했습니다: {str(e)}"
        )


# ==================== 결제 취소 ====================

@router.post(
    "/cancel",
    response_model=PaymentCancelResponse,
    summary="결제 취소",
    description="결제를 취소합니다"
)
async def cancel_payment(request: PaymentCancelRequest):
    """
    결제 취소
    
    **사용 시나리오:**
    - 고객이 주문 취소 요청
    - 재고 부족으로 주문 취소
    - 환불 처리
    
    Returns:
        PaymentCancelResponse: 취소 결과
    """
    try:
        result = await payment_service.cancel_payment(request)
        return result
        
    except Exception as e:
        logger.error(f"결제 취소 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"결제 취소 중 오류가 발생했습니다: {str(e)}"
        )


# ==================== 주문 조회 ====================

@router.get(
    "/orders/{order_id}",
    response_model=OrderResponse,
    summary="주문 조회",
    description="주문 ID로 주문 정보를 조회합니다"
)
async def get_order(
    order_id: str = Path(..., description="주문 ID")
):
    """
    주문 조회
    
    Args:
        order_id: 주문 ID
    
    Returns:
        OrderResponse: 주문 정보
    """
    try:
        order = await payment_service.get_order(order_id)
        
        if not order:
            raise HTTPException(
                status_code=404,
                detail=f"주문을 찾을 수 없습니다: {order_id}"
            )
        
        return OrderResponse(success=True, order=order)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"주문 조회 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="주문 조회 중 오류가 발생했습니다"
        )


@router.get(
    "/orders/customer/{customer_id}",
    response_model=OrderListResponse,
    summary="고객별 주문 목록",
    description="고객 ID로 주문 목록을 조회합니다"
)
async def get_customer_orders(
    customer_id: str = Path(..., description="고객 ID"),
    limit: int = Query(20, ge=1, le=100, description="조회할 주문 수")
):
    """
    고객별 주문 목록 조회
    
    Args:
        customer_id: 고객 ID
        limit: 조회할 주문 수
    
    Returns:
        OrderListResponse: 주문 목록
    """
    try:
        orders = await payment_service.get_orders_by_customer(customer_id, limit)
        
        return OrderListResponse(
            success=True,
            orders=orders,
            total=len(orders)
        )
        
    except Exception as e:
        logger.error(f"주문 목록 조회 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="주문 목록 조회 중 오류가 발생했습니다"
        )


# ==================== 웹훅 (선택사항) ====================

@router.post(
    "/webhook",
    summary="Toss Payments 웹훅",
    description="Toss Payments에서 결제 상태 변경 시 호출됩니다"
)
async def toss_webhook(data: dict):
    """
    Toss Payments 웹훅
    
    결제 상태 변경 시 Toss에서 자동 호출
    (예: 가상계좌 입금 완료 시)
    """
    try:
        logger.info(f"Toss 웹훅 수신: {data}")
        
        # TODO: 웹훅 처리 로직
        # 1. 시그니처 검증
        # 2. 상태 업데이트
        
        return {"success": True}
        
    except Exception as e:
        logger.error(f"웹훅 처리 실패: {str(e)}")
        raise HTTPException(status_code=500, detail="웹훅 처리 실패")