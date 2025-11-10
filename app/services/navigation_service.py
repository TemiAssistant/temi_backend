# app/services/navigation_service.py
"""
네비게이션 관련 비즈니스 로직
Temi 로봇 위치 안내 및 경로 계산
"""

from typing import List, Optional, Dict, Any, Tuple
import uuid
from datetime import datetime, timedelta
import logging
import json

from app.core.firebase import firestore_db, realtime_db
from app.models.navigation import (
    Coordinate, Zone, ProductLocation, PathResult, PathNode,
    TemiLocation, TemiStatus, NavigationStatus,
    NavigationGuideRequest, NavigationGuideResponse,
    NavigationStatusResponse, TemiMoveRequest, TemiMoveResponse,
    TemiStopRequest, TemiSpeakRequest,
    NearbyProductsRequest, NearbyProductsResponse,
    StoreLayout, StoreLayoutResponse
)
from app.utils.pathfinding import PathFinder

logger = logging.getLogger(__name__)


class NavigationService:
    """네비게이션 서비스 클래스"""
    
    def __init__(self):
        self.db = firestore_db
        self.rtdb = realtime_db
        
        # 컬렉션
        self.products_collection = "products"
        self.navigation_collection = "navigations"
        self.temi_collection = "temi_robots"
        
        # 매장 레이아웃 (store_config.json에서 로드)
        self.store_layout = self._load_store_layout()
        
        # 경로 탐색기
        self.pathfinder = PathFinder(
            grid_size=(self.store_layout['width'], self.store_layout['height']),
            obstacles=self.store_layout.get('obstacles', [])
        )
        
        # Temi 기본 속도
        self.default_temi_speed = 0.8  # m/s
    
    def _load_store_layout(self) -> dict:
        """매장 레이아웃 로드"""
        try:
            # Firestore에서 매장 설정 로드
            doc = self.db.collection("store_config").document("default").get()
            
            if doc.exists:
                data = doc.to_dict()
                layout = data.get('layout', {})
                logger.info("✅ 매장 레이아웃 로드 완료")
                return {
                    'width': layout.get('width', 50),
                    'height': layout.get('height', 40),
                    'zones': layout.get('zones', []),
                    'obstacles': []
                }
            else:
                logger.warning("⚠️ 매장 설정을 찾을 수 없습니다. 기본값 사용")
                return {
                    'width': 50,
                    'height': 40,
                    'zones': [],
                    'obstacles': []
                }
                
        except Exception as e:
            logger.error(f"매장 레이아웃 로드 실패: {str(e)}")
            return {'width': 50, 'height': 40, 'zones': [], 'obstacles': []}
    
    # ==================== 네비게이션 안내 ====================
    
    async def guide_to_product(
        self,
        request: NavigationGuideRequest
    ) -> NavigationGuideResponse:
        """
        상품 위치로 안내
        
        시나리오 1: 상품 검색 & 안내
        """
        try:
            # 1. 상품 정보 조회
            product_doc = self.db.collection(self.products_collection)\
                                .document(request.product_id).get()
            
            if not product_doc.exists:
                raise Exception(f"상품을 찾을 수 없습니다: {request.product_id}")
            
            product_data = product_doc.to_dict()
            
            # 2. 상품 위치 정보 추출
            location_data = product_data.get('location', {})
            product_location = ProductLocation(
                product_id=request.product_id,
                name=product_data['name'],
                zone=location_data['zone'],
                shelf=location_data['shelf'],
                coordinate=Coordinate(
                    x=location_data['x'],
                    y=location_data['y']
                )
            )
            
            # 3. Temi 현재 위치 조회
            temi_location = await self._get_temi_location(request.temi_id)
            
            if not temi_location:
                # Temi 위치 정보 없으면 기본 위치 (매장 입구)
                temi_coord = Coordinate(x=5, y=5)
            else:
                temi_coord = temi_location.coordinate
            
            # 4. 경로 계산
            start = request.start_location or temi_coord
            end = product_location.coordinate
            
            path_coords, distance, time = self.pathfinder.calculate_path(
                start, end, self.default_temi_speed
            )
            
            # 경로 스무딩
            path_coords = self.pathfinder.smooth_path(path_coords)
            
            path_result = PathResult(
                success=True,
                start=start,
                end=end,
                path=path_coords,
                total_distance=distance,
                estimated_time=time,
                waypoints=[
                    PathNode(
                        coordinate=coord,
                        action="move" if i < len(path_coords) - 1 else "stop",
                        distance_from_start=sum(
                            self.pathfinder._distance(path_coords[j], path_coords[j+1])
                            for j in range(i)
                        ) if i > 0 else 0
                    )
                    for i, coord in enumerate(path_coords)
                ]
            )
            
            # 5. 네비게이션 세션 생성
            navigation_id = self._generate_navigation_id()
            navigation_data = {
                "navigation_id": navigation_id,
                "temi_id": request.temi_id,
                "customer_id": request.customer_id,
                "product_id": request.product_id,
                "product_name": product_data['name'],
                "start_location": start.dict(),
                "destination": end.dict(),
                "path": [coord.dict() for coord in path_coords],
                "status": NavigationStatus.NAVIGATING.value,
                "progress": 0,
                "distance_total": distance,
                "distance_remaining": distance,
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
            
            self.db.collection(self.navigation_collection)\
                  .document(navigation_id).set(navigation_data)
            
            # 6. Realtime DB에 경로 저장 (WebSocket 실시간 전송용)
            if self.rtdb:
                self.rtdb.child(f'navigation/{navigation_id}').set({
                    'temi_id': request.temi_id,
                    'path': [{'x': c.x, 'y': c.y} for c in path_coords],
                    'status': NavigationStatus.NAVIGATING.value,
                    'timestamp': {'.sv': 'timestamp'}
                })
            
            # 7. Temi에게 이동 명령
            await self._send_temi_command(
                temi_id=request.temi_id,
                command_type="goto",
                destination=end,
                path=path_coords
            )
            
            # 8. 예상 도착 시간
            estimated_arrival = datetime.now() + timedelta(seconds=time)
            
            # 9. 안내 메시지 생성
            message = f"'{product_data['name']}'를 찾으셨군요! {location_data['zone']} 구역으로 안내하겠습니다. 따라오세요!"
            
            logger.info(f"✅ 네비게이션 시작: {navigation_id} - {product_data['name']}")
            
            return NavigationGuideResponse(
                success=True,
                navigation_id=navigation_id,
                product=product_location,
                temi_location=start,
                path=path_result,
                estimated_arrival=estimated_arrival,
                message=message
            )
            
        except Exception as e:
            logger.error(f"네비게이션 안내 실패: {str(e)}")
            raise
    
    # ==================== 경로 계산 ====================
    
    async def calculate_path(
        self,
        start: Coordinate,
        end: Coordinate
    ) -> PathResult:
        """경로만 계산 (이동 명령 없이)"""
        try:
            path_coords, distance, time = self.pathfinder.calculate_path(
                start, end, self.default_temi_speed
            )
            
            path_coords = self.pathfinder.smooth_path(path_coords)
            
            return PathResult(
                success=True,
                start=start,
                end=end,
                path=path_coords,
                total_distance=distance,
                estimated_time=time,
                waypoints=[
                    PathNode(coordinate=coord, action="move")
                    for coord in path_coords
                ]
            )
            
        except Exception as e:
            logger.error(f"경로 계산 실패: {str(e)}")
            raise
    
    # ==================== 네비게이션 상태 ====================
    
    async def get_navigation_status(
        self,
        navigation_id: str
    ) -> NavigationStatusResponse:
        """네비게이션 진행 상태 조회"""
        try:
            doc = self.db.collection(self.navigation_collection)\
                        .document(navigation_id).get()
            
            if not doc.exists:
                raise Exception(f"네비게이션을 찾을 수 없습니다: {navigation_id}")
            
            data = doc.to_dict()
            
            current_location = Coordinate(**data.get('current_location', data['start_location']))
            destination = Coordinate(**data['destination'])
            
            return NavigationStatusResponse(
                success=True,
                navigation_id=navigation_id,
                status=NavigationStatus(data['status']),
                current_location=current_location,
                destination=destination,
                progress=data.get('progress', 0),
                distance_remaining=data.get('distance_remaining', 0),
                time_remaining=data.get('time_remaining', 0)
            )
            
        except Exception as e:
            logger.error(f"네비게이션 상태 조회 실패: {str(e)}")
            raise
    
    async def update_navigation_progress(
        self,
        navigation_id: str,
        current_location: Coordinate,
        status: NavigationStatus = None
    ):
        """네비게이션 진행 상황 업데이트"""
        try:
            doc_ref = self.db.collection(self.navigation_collection)\
                            .document(navigation_id)
            
            doc = doc_ref.get()
            if not doc.exists:
                return
            
            data = doc.to_dict()
            destination = Coordinate(**data['destination'])
            
            # 남은 거리 계산
            distance_remaining = self.pathfinder._distance(current_location, destination)
            
            # 진행률 계산
            total_distance = data['distance_total']
            progress = max(0, min(100, (1 - distance_remaining / total_distance) * 100))
            
            # 남은 시간
            time_remaining = distance_remaining / self.default_temi_speed
            
            update_data = {
                "current_location": current_location.dict(),
                "distance_remaining": distance_remaining,
                "progress": progress,
                "time_remaining": time_remaining,
                "updated_at": datetime.now()
            }
            
            if status:
                update_data["status"] = status.value
            
            doc_ref.update(update_data)
            
            # Realtime DB도 업데이트
            if self.rtdb:
                self.rtdb.child(f'navigation/{navigation_id}').update({
                    'current_location': {'x': current_location.x, 'y': current_location.y},
                    'progress': progress,
                    'status': status.value if status else data['status'],
                    'timestamp': {'.sv': 'timestamp'}
                })
            
        except Exception as e:
            logger.error(f"네비게이션 진행 상황 업데이트 실패: {str(e)}")
    
    # ==================== Temi 제어 ====================
    
    async def move_temi(
        self,
        request: TemiMoveRequest
    ) -> TemiMoveResponse:
        """Temi 로봇 이동 명령"""
        try:
            # Temi 현재 위치
            temi_location = await self._get_temi_location(request.temi_id)
            current = temi_location.coordinate if temi_location else Coordinate(x=5, y=5)
            
            # 경로 계산
            path_coords, distance, time = self.pathfinder.calculate_path(
                current, request.destination, request.speed
            )
            
            # 명령 ID 생성
            command_id = self._generate_command_id()
            
            # Temi에게 명령 전송
            await self._send_temi_command(
                temi_id=request.temi_id,
                command_type="goto",
                destination=request.destination,
                path=path_coords,
                speed=request.speed,
                voice_guide=request.voice_guide,
                message=request.message
            )
            
            message = request.message or "목적지로 이동하겠습니다."
            
            return TemiMoveResponse(
                success=True,
                command_id=command_id,
                temi_id=request.temi_id,
                current_location=current,
                destination=request.destination,
                estimated_time=time,
                message=message
            )
            
        except Exception as e:
            logger.error(f"Temi 이동 명령 실패: {str(e)}")
            raise
    
    async def stop_temi(self, request: TemiStopRequest):
        """Temi 정지"""
        try:
            await self._send_temi_command(
                temi_id=request.temi_id,
                command_type="stop",
                parameters={'reason': request.reason}
            )
            
            return {"success": True, "message": "Temi가 정지했습니다."}
            
        except Exception as e:
            logger.error(f"Temi 정지 실패: {str(e)}")
            raise
    
    async def temi_speak(self, request: TemiSpeakRequest):
        """Temi 음성 출력"""
        try:
            await self._send_temi_command(
                temi_id=request.temi_id,
                command_type="speak",
                parameters={
                    'text': request.text,
                    'language': request.language
                }
            )
            
            return {"success": True, "message": "음성 출력 완료"}
            
        except Exception as e:
            logger.error(f"Temi 음성 출력 실패: {str(e)}")
            raise
    
    # ==================== 위치 정보 ====================
    
    async def get_all_locations(self) -> Dict[str, Any]:
        """모든 위치 정보 조회"""
        try:
            # 구역 정보
            zones = [
                Zone(**zone_data)
                for zone_data in self.store_layout['zones']
            ]
            
            # 상품 위치
            products_docs = self.db.collection(self.products_collection)\
                                  .where('is_active', '==', True)\
                                  .stream()
            
            products = []
            for doc in products_docs:
                data = doc.to_dict()
                location = data.get('location', {})
                if location:
                    products.append(ProductLocation(
                        product_id=doc.id,
                        name=data['name'],
                        zone=location['zone'],
                        shelf=location['shelf'],
                        coordinate=Coordinate(x=location['x'], y=location['y'])
                    ))
            
            # Temi 위치
            temi_locations = await self._get_all_temi_locations()
            
            # 충전소
            charging_stations = [
                Coordinate(**station)
                for station in self.store_layout.get('charging_stations', [])
            ]
            
            return {
                "zones": zones,
                "products": products,
                "temi_locations": temi_locations,
                "charging_stations": charging_stations
            }
            
        except Exception as e:
            logger.error(f"위치 정보 조회 실패: {str(e)}")
            raise
    
    async def find_nearby_products(
        self,
        request: NearbyProductsRequest
    ) -> NearbyProductsResponse:
        """주변 상품 검색"""
        try:
            products_docs = self.db.collection(self.products_collection)\
                                  .where('is_active', '==', True)\
                                  .stream()
            
            nearby = []
            for doc in products_docs:
                data = doc.to_dict()
                location = data.get('location', {})
                
                if not location:
                    continue
                
                coord = Coordinate(x=location['x'], y=location['y'])
                distance = self.pathfinder._distance(request.coordinate, coord)
                
                if distance <= request.radius:
                    nearby.append(ProductLocation(
                        product_id=doc.id,
                        name=data['name'],
                        zone=location['zone'],
                        shelf=location['shelf'],
                        coordinate=coord
                    ))
            
            # 거리순 정렬
            nearby.sort(key=lambda p: self.pathfinder._distance(request.coordinate, p.coordinate))
            
            return NearbyProductsResponse(
                success=True,
                center=request.coordinate,
                radius=request.radius,
                products=nearby[:request.limit],
                total=len(nearby)
            )
            
        except Exception as e:
            logger.error(f"주변 상품 검색 실패: {str(e)}")
            raise
    
    async def get_store_layout(self) -> StoreLayoutResponse:
        """매장 레이아웃 정보"""
        zones = [Zone(**z) for z in self.store_layout['zones']]
        charging_stations = [
            Coordinate(**s) for s in self.store_layout.get('charging_stations', [])
        ]
        
        layout = StoreLayout(
            width=self.store_layout['width'],
            height=self.store_layout['height'],
            zones=zones,
            obstacles=self.store_layout.get('obstacles', []),
            charging_stations=charging_stations
        )
        
        return StoreLayoutResponse(success=True, layout=layout)
    
    # ==================== 내부 헬퍼 함수 ====================
    
    async def _get_temi_location(self, temi_id: str) -> Optional[TemiLocation]:
        """Temi 위치 조회"""
        try:
            if self.rtdb:
                data = self.rtdb.child(f'temi/{temi_id}/location').get()
                if data:
                    return TemiLocation(
                        temi_id=temi_id,
                        coordinate=Coordinate(**data.get('coordinate', {'x': 5, 'y': 5})),
                        heading=data.get('heading', 0),
                        battery=data.get('battery', 100),
                        status=TemiStatus(data.get('status', 'AVAILABLE')),
                        last_updated=datetime.fromisoformat(data['last_updated']) if 'last_updated' in data else datetime.now()
                    )
            
            return None
            
        except Exception as e:
            logger.warning(f"Temi 위치 조회 실패: {str(e)}")
            return None
    
    async def _get_all_temi_locations(self) -> List[TemiLocation]:
        """모든 Temi 위치 조회"""
        try:
            if self.rtdb:
                data = self.rtdb.child('temi').get()
                if data:
                    return [
                        TemiLocation(
                            temi_id=temi_id,
                            coordinate=Coordinate(**temi_data['location']['coordinate']),
                            heading=temi_data['location'].get('heading', 0),
                            battery=temi_data['location'].get('battery', 100),
                            status=TemiStatus(temi_data['location'].get('status', 'AVAILABLE')),
                            last_updated=datetime.now()
                        )
                        for temi_id, temi_data in data.items()
                        if 'location' in temi_data
                    ]
            
            return []
            
        except Exception as e:
            logger.warning(f"Temi 위치 목록 조회 실패: {str(e)}")
            return []
    
    async def _send_temi_command(
        self,
        temi_id: str,
        command_type: str,
        destination: Coordinate = None,
        path: List[Coordinate] = None,
        speed: float = None,
        voice_guide: bool = True,
        message: str = None,
        parameters: dict = None
    ):
        """Temi에게 명령 전송 (Realtime DB + WebSocket)"""
        try:
            command_data = {
                'command_id': self._generate_command_id(),
                'temi_id': temi_id,
                'type': command_type,
                'timestamp': {'.sv': 'timestamp'},
                'status': 'pending'
            }
            
            if destination:
                command_data['destination'] = {'x': destination.x, 'y': destination.y}
            
            if path:
                command_data['path'] = [{'x': c.x, 'y': c.y} for c in path]
            
            if speed:
                command_data['speed'] = speed
            
            if voice_guide:
                command_data['voice_guide'] = True
                if message:
                    command_data['message'] = message
            
            if parameters:
                command_data['parameters'] = parameters
            
            # Realtime DB에 명령 저장
            if self.rtdb:
                self.rtdb.child(f'temi_commands/{temi_id}').push(command_data)
                logger.info(f"✅ Temi 명령 전송: {temi_id} - {command_type}")
            
            # TODO: WebSocket으로도 전송 (실시간 통신)
            
        except Exception as e:
            logger.error(f"Temi 명령 전송 실패: {str(e)}")
    
    def _generate_navigation_id(self) -> str:
        """네비게이션 ID 생성"""
        return f"NAV{datetime.now().strftime('%Y%m%d%H%M%S')}{str(uuid.uuid4())[:8].upper()}"
    
    def _generate_command_id(self) -> str:
        """명령 ID 생성"""
        return f"CMD{str(uuid.uuid4()).replace('-', '').upper()[:16]}"


# 싱글톤 인스턴스
navigation_service = NavigationService()