# temi_backend/test_payment.py
import httpx
import asyncio
import json

BASE_URL = "http://localhost:8000"

async def test_payment_flow():
    """결제 플로우 테스트"""
    
    print("="*60)
    print("🧪 결제 시스템 테스트 시작")
    print("="*60)
    
    async with httpx.AsyncClient() as client:
        # 1. 결제 시작
        print("\n1️⃣ 결제 시작...")
        payment_data = {
            "customer_id": "user_001",
            "customer_name": "홍길동",
            "customer_email": "hong@example.com",
            "customer_phone": "010-1234-5678",
            "items": [
                {
                    "product_id": "prod_001",
                    "name": "설화수 자음생 에센스",
                    "quantity": 1,
                    "price": 85000,
                    "total_price": 85000
                },
                {
                    "product_id": "prod_006",
                    "name": "라운드랩 버치 주스 선크림",
                    "quantity": 2,
                    "price": 16500,
                    "total_price": 33000
                }
            ],
            "total_amount": 118000,
            "use_points": 0,
            "final_amount": 118000
        }
        
        response = await client.post(
            f"{BASE_URL}/api/payments/initiate",
            json=payment_data,
            timeout=30.0
        )
        
        if response.status_code != 200:
            print(f"❌ 결제 시작 실패: {response.status_code}")
            print(response.text)
            return
        
        result = response.json()
        print("✅ 결제 시작 성공!")
        print(f"   주문 ID: {result['order_id']}")
        print(f"   결제 키: {result['payment_key']}")
        print(f"   금액: {result['amount']:,}원")
        print(f"   주문명: {result['order_name']}")
        print(f"   QR 데이터: {result['qr_data']}")
        
        payment_key = result['payment_key']
        order_id = result['order_id']
        amount = result['amount']
        
        # 2. 주문 조회
        print(f"\n2️⃣ 주문 조회 (주문 ID: {order_id})...")
        response = await client.get(
            f"{BASE_URL}/api/payments/orders/{order_id}",
            timeout=30.0
        )
        
        if response.status_code != 200:
            print(f"❌ 주문 조회 실패: {response.status_code}")
            return
        
        order_result = response.json()
        print("✅ 주문 조회 성공!")
        print(f"   고객명: {order_result['order']['customer_name']}")
        print(f"   상품 수: {len(order_result['order']['items'])}개")
        print(f"   결제 상태: {order_result['order']['payment_status']}")
        print(f"   주문 상태: {order_result['order']['order_status']}")
        
        # 3. 고객별 주문 목록 조회
        print(f"\n3️⃣ 고객별 주문 목록 조회...")
        response = await client.get(
            f"{BASE_URL}/api/payments/orders/customer/user_001",
            timeout=30.0
        )
        
        if response.status_code != 200:
            print(f"❌ 주문 목록 조회 실패: {response.status_code}")
            return
        
        orders_result = response.json()
        print("✅ 주문 목록 조회 성공!")
        print(f"   총 주문 수: {orders_result['total']}개")
        
        for i, order in enumerate(orders_result['orders'], 1):
            print(f"   [{i}] {order['order_id']} - {order['final_amount']:,}원 - {order['order_status']}")
        
        print("\n" + "="*60)
        print("✅ 모든 테스트 완료!")
        print("="*60)
        
        print(f"\n📝 생성된 주문 정보:")
        print(f"   주문 ID: {order_id}")
        print(f"   결제 키: {payment_key}")
        print(f"   금액: {amount:,}원")
        print(f"\n💡 Firebase Console에서 확인:")
        print(f"   Firestore → orders → {order_id}")
        print(f"   Firestore → payments → {payment_key}")

if __name__ == "__main__":
    asyncio.run(test_payment_flow())