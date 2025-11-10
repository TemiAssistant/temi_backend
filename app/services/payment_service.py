# app/services/payment_service.py
"""
결제 관련 비즈니스 로직
Toss Payments API 연동
"""

from typing import Optional, Dict, Any, List
import httpx
import base64
import os
import uuid
from datetime import datetime
from dotenv import load_dotenv
import logging
import json

from app.core.firebase import firestore_db
from app.models.payment import (
    PaymentInitiateRequest,
    PaymentInitiateResponse,
    PaymentApproveRequest,
    PaymentApproveResponse,
    PaymentCancelRequest,
    PaymentCancelResponse,
    PaymentStatus,
    OrderStatus,
    Order,
    PaymentItem
)

load_dotenv()
logger = logging.getLogger(__name__)


class PaymentService:
    """결제 서비스 클래스"""
    
    def __init__(self):
        self.db = firestore_db
        self.orders_collection = "orders"
        self.payments_collection = "payments"
        
        # Toss Payments 설정
        self.client_key = os.getenv("TOSS_CLIENT_KEY")
        self.secret_key = os.getenv("TOSS_SECRET_KEY")
        self.success_url = os.getenv("TOSS_SUCCESS_URL", "http://localhost:3000/payment/success")
        self.fail_url = os.getenv("TOSS_FAIL_URL", "http://localhost:3000/payment/fail")
        
        # Toss API URL
        self.api_base_url = "https://api.tosspayments.com/v1"
        
        # 인증 헤더
        credentials = f"{self.secret_key}:"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        self.auth_headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/json"
        }
    
    # ==================== 결제 시작 ====================
    
    async def initiate_payment(
        self,
        request: PaymentInitiateRequest
    ) -> PaymentInitiateResponse:
        """
        결제 시작
        
        1. 주문 생성
        2. Toss Payment Key 생성
        3. QR 코드 데이터 생성
        """
        try:
            # 1. 주문 ID 생성
            order_id = self._generate_order_id()
            payment_key = self._generate_payment_key()
            
            # 2. 주문명 생성
            order_name = self._generate_order_name(request.items)
            
            # 3. Firestore에 주문 저장
            order_data = {
                "order_id": order_id,
                "customer_id": request.customer_id,
                "customer_name": request.customer_name,
                "customer_email": request.customer_email,
                "customer_phone": request.customer_phone,
                "items": [item.dict() for item in request.items],
                "total_amount": request.total_amount,
                "discount_amount": request.total_amount - request.final_amount,
                "use_points": request.use_points,
                "final_amount": request.final_amount,
                "payment_key": payment_key,
                "payment_method": None,
                "payment_status": PaymentStatus.READY.value,
                "order_status": OrderStatus.PENDING.value,
                "created_at": datetime.now(),
                "paid_at": None,
                "canceled_at": None
            }
            
            self.db.collection(self.orders_collection).document(order_id).set(order_data)
            logger.info(f"주문 생성 완료: {order_id}")
            
            # 4. 결제 정보 저장
            payment_data = {
                "payment_key": payment_key,
                "order_id": order_id,
                "amount": request.final_amount,
                "order_name": order_name,
                "customer_name": request.customer_name,
                "status": PaymentStatus.READY.value,
                "created_at": datetime.now()
            }
            
            self.db.collection(self.payments_collection).document(payment_key).set(payment_data)
            logger.info(f"결제 정보 저장 완료: {payment_key}")
            
            # 5. 결제 페이지 URL 생성
            checkout_url = self._generate_checkout_url(
                payment_key=payment_key,
                order_id=order_id,
                amount=request.final_amount,
                order_name=order_name,
                customer_name=request.customer_name
            )
            
            # 6. QR 코드 데이터 (결제 페이지 URL)
            qr_data = checkout_url
            
            return PaymentInitiateResponse(
                success=True,
                payment_key=payment_key,
                order_id=order_id,
                amount=request.final_amount,
                order_name=order_name,
                customer_name=request.customer_name,
                qr_data=qr_data,
                checkout_url=checkout_url,
                created_at=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"결제 시작 실패: {str(e)}")
            raise
    
    # ==================== 결제 승인 ====================
    
    async def approve_payment(
        self,
        request: PaymentApproveRequest
    ) -> PaymentApproveResponse:
        """
        결제 승인 (Toss Payments API 호출)
        
        사용자가 결제를 완료하면 프론트엔드에서 이 API 호출
        """
        try:
            # 1. Toss Payments 승인 API 호출
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_base_url}/payments/confirm",
                    headers=self.auth_headers,
                    json={
                        "paymentKey": request.payment_key,
                        "orderId": request.order_id,
                        "amount": request.amount
                    },
                    timeout=30.0
                )
                
                if response.status_code != 200:
                    error_data = response.json()
                    logger.error(f"Toss 결제 승인 실패: {error_data}")
                    raise Exception(f"결제 승인 실패: {error_data.get('message', 'Unknown error')}")
                
                toss_response = response.json()
                logger.info(f"Toss 결제 승인 성공: {toss_response}")
            
            # 2. Firestore 업데이트
            approved_at = datetime.fromisoformat(toss_response['approvedAt'].replace('Z', '+00:00'))
            
            # 주문 상태 업데이트
            order_ref = self.db.collection(self.orders_collection).document(request.order_id)
            order_ref.update({
                "payment_status": PaymentStatus.DONE.value,
                "order_status": OrderStatus.PAID.value,
                "payment_method": toss_response.get('method'),
                "paid_at": approved_at
            })
            
            # 결제 정보 업데이트
            payment_ref = self.db.collection(self.payments_collection).document(request.payment_key)
            payment_ref.update({
                "status": PaymentStatus.DONE.value,
                "approved_at": approved_at,
                "toss_response": toss_response
            })
            
            logger.info(f"결제 승인 완료: {request.payment_key}")
            
            return PaymentApproveResponse(
                success=True,
                payment_key=request.payment_key,
                order_id=request.order_id,
                status=PaymentStatus.DONE,
                method=toss_response.get('method'),
                total_amount=toss_response['totalAmount'],
                balance_amount=toss_response['balanceAmount'],
                supplied_amount=toss_response['suppliedAmount'],
                vat=toss_response['vat'],
                approved_at=approved_at,
                receipt_url=toss_response.get('receipt', {}).get('url')
            )
            
        except Exception as e:
            logger.error(f"결제 승인 실패: {str(e)}")
            raise
    
    # ==================== 결제 취소 ====================
    
    async def cancel_payment(
        self,
        request: PaymentCancelRequest
    ) -> PaymentCancelResponse:
        """결제 취소"""
        try:
            # 1. Toss Payments 취소 API 호출
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_base_url}/payments/{request.payment_key}/cancel",
                    headers=self.auth_headers,
                    json={
                        "cancelReason": request.cancel_reason,
                        "cancelAmount": request.cancel_amount
                    },
                    timeout=30.0
                )
                
                if response.status_code != 200:
                    error_data = response.json()
                    logger.error(f"Toss 결제 취소 실패: {error_data}")
                    raise Exception(f"결제 취소 실패: {error_data.get('message', 'Unknown error')}")
                
                toss_response = response.json()
                logger.info(f"Toss 결제 취소 성공: {toss_response}")
            
            # 2. Firestore 업데이트
            payment_ref = self.db.collection(self.payments_collection).document(request.payment_key)
            payment_doc = payment_ref.get()
            
            if not payment_doc.exists:
                raise Exception("결제 정보를 찾을 수 없습니다")
            
            payment_data = payment_doc.to_dict()
            order_id = payment_data['order_id']
            
            # 주문 상태 업데이트
            order_ref = self.db.collection(self.orders_collection).document(order_id)
            order_ref.update({
                "payment_status": PaymentStatus.CANCELED.value,
                "order_status": OrderStatus.CANCELED.value,
                "canceled_at": datetime.now()
            })
            
            # 결제 정보 업데이트
            payment_ref.update({
                "status": PaymentStatus.CANCELED.value,
                "canceled_at": datetime.now(),
                "cancel_reason": request.cancel_reason,
                "toss_cancel_response": toss_response
            })
            
            logger.info(f"결제 취소 완료: {request.payment_key}")
            
            return PaymentCancelResponse(
                success=True,
                payment_key=request.payment_key,
                order_id=order_id,
                status=PaymentStatus.CANCELED,
                canceled_at=datetime.now(),
                cancel_amount=request.cancel_amount or toss_response['totalAmount'],
                cancel_reason=request.cancel_reason
            )
            
        except Exception as e:
            logger.error(f"결제 취소 실패: {str(e)}")
            raise
    
    # ==================== 주문 조회 ====================
    
    async def get_order(self, order_id: str) -> Optional[Order]:
        """주문 조회"""
        try:
            doc = self.db.collection(self.orders_collection).document(order_id).get()
            
            if not doc.exists:
                logger.warning(f"주문을 찾을 수 없음: {order_id}")
                return None
            
            data = doc.to_dict()
            
            # PaymentItem 변환
            items = [PaymentItem(**item) for item in data.get('items', [])]
            data['items'] = items
            
            return Order(**data)
            
        except Exception as e:
            logger.error(f"주문 조회 실패: {order_id}, 오류: {str(e)}")
            raise
    
    async def get_orders_by_customer(
        self,
        customer_id: str,
        limit: int = 20
    ) -> List[Order]:
        """고객별 주문 목록 조회"""
        try:
            docs = self.db.collection(self.orders_collection)\
                         .where('customer_id', '==', customer_id)\
                         .order_by('created_at', direction='DESCENDING')\
                         .limit(limit)\
                         .stream()
            
            orders = []
            for doc in docs:
                try:
                    data = doc.to_dict()
                    items = [PaymentItem(**item) for item in data.get('items', [])]
                    data['items'] = items
                    orders.append(Order(**data))
                except Exception as e:
                    logger.warning(f"주문 파싱 실패: {doc.id}")
                    continue
            
            return orders
            
        except Exception as e:
            logger.error(f"주문 목록 조회 실패: {customer_id}, 오류: {str(e)}")
            raise
    
    # ==================== 헬퍼 함수 ====================
    
    def _generate_order_id(self) -> str:
        """주문 ID 생성"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        random_str = str(uuid.uuid4())[:8].upper()
        return f"ORD{timestamp}{random_str}"
    
    def _generate_payment_key(self) -> str:
        """결제 키 생성"""
        return f"PAY{str(uuid.uuid4()).replace('-', '').upper()}"
    
    def _generate_order_name(self, items: List[PaymentItem]) -> str:
        """주문명 생성"""
        if len(items) == 0:
            return "빈 주문"
        elif len(items) == 1:
            return items[0].name
        else:
            return f"{items[0].name} 외 {len(items) - 1}건"
    
    def _generate_checkout_url(
        self,
        payment_key: str,
        order_id: str,
        amount: int,
        order_name: str,
        customer_name: str
    ) -> str:
        """결제 페이지 URL 생성"""
        # Toss Payments 결제 페이지 URL
        # 실제 프론트엔드에서 Toss SDK를 사용하여 결제 진행
        base_url = "https://api.tosspayments.com/v1/payments"
        
        # 또는 자체 결제 페이지 URL
        checkout_url = f"{self.success_url.rsplit('/', 1)[0]}/checkout?paymentKey={payment_key}&orderId={order_id}&amount={amount}"
        
        return checkout_url


# 싱글톤 인스턴스
payment_service = PaymentService()