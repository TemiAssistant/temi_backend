# temi_backend/test_navigation.py
"""
Navigation API 테스트 스크립트
"""

import httpx
import asyncio
import json

BASE_URL = "http://localhost:8000"


async def test_navigation_api():
    """네비게이션 API 전체 테스트"""
    
    print("="*70)
    print("🧪 Navigation API 테스트 시작")
    print("="*70)
    
    async with httpx.AsyncClient() as client:
        
        # ==================== 1. 매장 레이아웃 조회 ====================
        print("\n1️⃣ 매장 레이아웃 조회...")
        response = await client.get(f"{BASE_URL}/api/navigation/layout")
        
        if response.status_code == 200:
            layout = response.json()
            print("✅ 레이아웃 조회 성공!")
            print(f"   매장 크기: {layout['layout']['width']}m x {layout['layout']['height']}m")
            print(f"   구역 수: {len(layout['layout']['zones'])}개")
            print(f"   충전소: {len(layout['layout']['charging_stations'])}개")
        else:
            print(f"❌ 레이아웃 조회 실패: {response.status_code}")
            return
        
        # ==================== 2. 전체 위치 정보 조회 ====================
        print("\n2️⃣ 전체 위치 정보 조회...")
        response = await client.get(f"{BASE_URL}/api/navigation/locations")
        
        if response.status_code == 200:
            locations = response.json()
            print("✅ 위치 정보 조회 성공!")
            print(f"   구역: {len(locations['zones'])}개")
            print(f"   상품: {len(locations['products'])}개")
            print(f"   Temi: {len(locations['temi_locations'])}대")
            
            # 첫 번째 상품 정보 저장
            if locations['products']:
                first_product = locations['products'][0]
                product_id = first_product['product_id']
                product_name = first_product['name']
                print(f"   테스트 상품: {product_name} ({product_id})")
        else:
            print(f"❌ 위치 정보 조회 실패: {response.status_code}")
            return
        
        # ==================== 3. 상품 위치 조회 ====================
        print(f"\n3️⃣ 상품 위치 조회 ({product_id})...")
        response = await client.get(
            f"{BASE_URL}/api/navigation/products/location/{product_id}"
        )
        
        if response.status_code == 200:
            product_loc = response.json()
            print("✅ 상품 위치 조회 성공!")
            coord = product_loc['product']['coordinate']
            print(f"   상품: {product_loc['product']['name']}")
            print(f"   구역: {product_loc['product']['zone']}")
            print(f"   좌표: ({coord['x']}, {coord['y']})")
        else:
            print(f"❌ 상품 위치 조회 실패: {response.status_code}")
        
        # ==================== 4. 경로 계산 ====================
        print("\n4️⃣ 경로 계산 (입구 → 상품)...")
        response = await client.post(
            f"{BASE_URL}/api/navigation/path",
            params={
                "start_x": 5.0,
                "start_y": 5.0,
                "end_x": coord['x'],
                "end_y": coord['y']
            }
        )
        
        if response.status_code == 200:
            path = response.json()
            print("✅ 경로 계산 성공!")
            print(f"   경로 포인트: {len(path['path'])}개")
            print(f"   총 거리: {path['total_distance']:.2f}m")
            print(f"   예상 시간: {path['estimated_time']:.1f}초")
        else:
            print(f"❌ 경로 계산 실패: {response.status_code}")
        
        # ==================== 5. 상품 위치 안내 ====================
        print(f"\n5️⃣ 상품 위치 안내 시작 ({product_name})...")
        guide_data = {
            "product_id": product_id,
            "temi_id": "temi_001",
            "customer_id": "user_001"
        }
        
        response = await client.post(
            f"{BASE_URL}/api/navigation/guide",
            json=guide_data
        )
        
        if response.status_code == 200:
            guide = response.json()
            print("✅ 네비게이션 시작 성공!")
            print(f"   세션 ID: {guide['navigation_id']}")
            print(f"   상품: {guide['product']['name']}")
            print(f"   구역: {guide['product']['zone']}")
            print(f"   경로 거리: {guide['path']['total_distance']:.2f}m")
            print(f"   예상 시간: {guide['path']['estimated_time']:.1f}초")
            print(f"   안내 메시지: {guide['message']}")
            
            navigation_id = guide['navigation_id']
        else:
            print(f"❌ 네비게이션 시작 실패: {response.status_code}")
            print(response.text)
            return
        
        # ==================== 6. 네비게이션 상태 조회 ====================
        print(f"\n6️⃣ 네비게이션 상태 조회 ({navigation_id})...")
        response = await client.get(
            f"{BASE_URL}/api/navigation/status/{navigation_id}"
        )
        
        if response.status_code == 200:
            status = response.json()
            print("✅ 상태 조회 성공!")
            print(f"   상태: {status['status']}")
            print(f"   진행률: {status['progress']:.1f}%")
            print(f"   남은 거리: {status['distance_remaining']:.2f}m")
            print(f"   남은 시간: {status['time_remaining']:.1f}초")
        else:
            print(f"❌ 상태 조회 실패: {response.status_code}")
        
        # ==================== 7. 진행 상황 업데이트 ====================
        print(f"\n7️⃣ 진행 상황 업데이트...")
        response = await client.post(
            f"{BASE_URL}/api/navigation/status/{navigation_id}/update",
            params={
                "current_x": 7.0,
                "current_y": 7.0,
                "status": "NAVIGATING"
            }
        )
        
        if response.status_code == 200:
            print("✅ 진행 상황 업데이트 성공!")
        else:
            print(f"❌ 진행 상황 업데이트 실패: {response.status_code}")
        
        # ==================== 8. 주변 상품 검색 ====================
        print(f"\n8️⃣ 주변 상품 검색 (반경 5m)...")
        nearby_data = {
            "coordinate": {"x": 10.0, "y": 20.0},
            "radius": 5.0,
            "limit": 5
        }
        
        response = await client.post(
            f"{BASE_URL}/api/navigation/locations/nearby",
            json=nearby_data
        )
        
        if response.status_code == 200:
            nearby = response.json()
            print("✅ 주변 상품 검색 성공!")
            print(f"   반경: {nearby['radius']}m")
            print(f"   발견: {nearby['total']}개")
            print(f"   결과: {len(nearby['products'])}개")
            
            for i, product in enumerate(nearby['products'], 1):
                print(f"   [{i}] {product['name']} - {product['zone']}")
        else:
            print(f"❌ 주변 상품 검색 실패: {response.status_code}")
        
        # ==================== 9. Temi 이동 명령 ====================
        print(f"\n9️⃣ Temi 이동 명령...")
        move_data = {
            "temi_id": "temi_001",
            "destination": {"x": 15.0, "y": 25.0},
            "speed": 0.8,
            "voice_guide": True,
            "message": "충전소로 이동합니다."
        }
        
        response = await client.post(
            f"{BASE_URL}/api/navigation/temi/move",
            json=move_data
        )
        
        if response.status_code == 200:
            move = response.json()
            print("✅ Temi 이동 명령 성공!")
            print(f"   명령 ID: {move['command_id']}")
            print(f"   예상 시간: {move['estimated_time']:.1f}초")
            print(f"   메시지: {move['message']}")
        else:
            print(f"❌ Temi 이동 실패: {response.status_code}")
        
        # ==================== 10. Temi 음성 안내 ====================
        print(f"\n🔟 Temi 음성 안내...")
        speak_data = {
            "temi_id": "temi_001",
            "text": "안녕하세요! 올리브영에 오신 것을 환영합니다.",
            "language": "ko-KR"
        }
        
        response = await client.post(
            f"{BASE_URL}/api/navigation/temi/speak",
            json=speak_data
        )
        
        if response.status_code == 200:
            print("✅ 음성 안내 성공!")
        else:
            print(f"❌ 음성 안내 실패: {response.status_code}")
        
        # ==================== 완료 ====================
        print("\n" + "="*70)
        print("✅ 모든 Navigation API 테스트 완료!")
        print("="*70)
        
        print("\n📝 생성된 데이터:")
        print(f"   네비게이션 세션: {navigation_id}")
        print(f"   테스트 상품: {product_name}")
        
        print("\n💡 Firebase Console에서 확인:")
        print(f"   Firestore → navigations → {navigation_id}")
        print(f"   Realtime DB → navigation/{navigation_id}")
        print(f"   Realtime DB → temi_commands/temi_001")


if __name__ == "__main__":
    asyncio.run(test_navigation_api())