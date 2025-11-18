# app/services/navigation_service.py
"""
네비게이션 관련 비즈니스 로직
Temi 로봇 위치 안내 및 경로 계산

매장 설정(store_config) 기능은 제거되었습니다.
기본 매장 레이아웃을 사용합니다.
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
        
        # 기본 매장 레이아웃 (하드코딩)
        self.store_layout = self._get_default_store_layout()
        
        # 경로 탐색기
        self.pathfinder = PathFinder(
            grid_size=(self.store_layout['width'], self.store_layout['height']),
            obstacles=self.store_layout.get('obstacles', [])
        )
        
        # Temi 기본 속도
        self.default_temi_speed = 0.8  # m/s
        
        # Realtime DB 연결 확인
        if self.rtdb:
            logger.info("✅ Realtime DB 연결됨")
        else:
            logger.warning("⚠️ Realtime DB 미연결 (Firestore만 사용)")
    
    def _get_default_store_layout(self) -> dict:
        """기본 매장 레이아웃 반환"""
        return {
            'width': 50,
            'height': 40,
            'zones': [
                {
                    'zone_id': 'zone_skincare',
                    'name': '스킨케어',
                    'bounds': {
                        'x_min': 5,
                        'y_min': 5,
                        'x_max': 20,
                        'y_max': 15
                    }
                },
                {
                    'zone_id': 'zone_makeup',
                    'name': '메이크업',
                    'bounds': {
                        'x_min': 25,
                        'y_min': 5,
                        'x_max': 40,
                        'y_max': 15
                    }
                },
                {
                    'zone_id': 'zone_bodycare',
                    'name': '바디케어',
                    'bounds': {
                        'x_min': 5,
                        'y_min': 20,
                        'x_max': 20,
                        'y_max': 35
                    }
                },
                {
                    'zone_id': 'zone_haircare',
                    'name': '헤어케어',
                    'bounds': {
                        'x_min': 25,
                        'y_min': 20,
                        'x_max': 40,
                        'y_max': 35
                    }
                }
            ],
            'obstacles': [],
            'charging_stations': [
                {'x': 2, 'y': 2},
                {'x': 45, 'y': 2}
            ]
        }
    
    # ==================== 네비게이션 안내 ====================
    
    async def guide_to_product(
        self, 
        request: NavigationGuideRequest
    ) -> NavigationGuideResponse:
        """
        상품 위치로 안내
        
        Args:
            request: 안내 요청 (상품 ID, Temi ID)
            
        Returns:
            NavigationGuideResponse: 안내 정보 (경로, 예상 시간 등)
        """
        try:
            # 1. 상품 위치 조회
            product_location = await self._get_product_location(request.product_id)
            if not product_location:
                return NavigationGuideResponse(
                    success=False,
                    message=f"상품 위치를 찾을 수 없습니다: {request.product_id}",
                    navigation_id=None,
                    path=[],
                    estimated_time=0,
                    distance=0
                )
            
            # 2. Temi 현재 위치 조회
            temi_location = await self._get_temi_location(request.temi_id)
            if not temi_location:
                # 기본 위치 사용
                start = Coordinate(x=5, y=5)
            else:
                start = temi_location.coordinate
            
            # 3. 경로 계산
            path_result = await self._calculate_path(
                start=start,
                end=product_location.coordinate
            )
            
            if not path_result.success:
                return NavigationGuideResponse(
                    success=False,
                    message="경로를 찾을 수 없습니다",
                    navigation_id=None,
                    path=[],
                    estimated_time=0,
                    distance=0
                )
            
            # 4. 네비게이션 세션 생성
            navigation_id = str(uuid.uuid4())
            await self._create_navigation_session(
                navigation_id=navigation_id,
                temi_id=request.temi_id,
                product_id=request.product_id,
                path=path_result.path,
                estimated_time=path_result.estimated_time
            )
            
            # 5. 응답 생성
            return NavigationGuideResponse(
                success=True,
                message="경로 안내를 시작합니다",
                navigation_id=navigation_id,
                product_location=product_location,
                path=path_result.path,
                estimated_time=path_result.estimated_time,
                distance=path_result.distance
            )
            
        except Exception as e:
            logger.error(f"상품 안내 실패: {str(e)}")
            raise
    
    async def get_navigation_status(
        self, 
        navigation_id: str
    ) -> NavigationStatusResponse:
        """네비게이션 진행 상태 조회"""
        try:
            doc = self.db.collection(self.navigation_collection)\
                        .document(navigation_id).get()
            
            if not doc.exists:
                return NavigationStatusResponse(
                    success=False,
                    message="네비게이션 세션을 찾을 수 없습니다",
                    navigation_id=navigation_id,
                    status=NavigationStatus.CANCELLED,
                    current_position=None,
                    remaining_distance=0,
                    remaining_time=0
                )
            
            data = doc.to_dict()
            
            # Temi 현재 위치 조회
            temi_location = await self._get_temi_location(data['temi_id'])
            current_position = temi_location.coordinate if temi_location else None
            
            # 남은 거리/시간 계산
            if current_position and data['status'] == 'IN_PROGRESS':
                remaining_path = await self._calculate_path(
                    start=current_position,
                    end=Coordinate(**data['destination'])
                )
                remaining_distance = remaining_path.distance
                remaining_time = remaining_path.estimated_time
            else:
                remaining_distance = 0
                remaining_time = 0
            
            return NavigationStatusResponse(
                success=True,
                message="네비게이션 상태 조회 완료",
                navigation_id=navigation_id,
                status=NavigationStatus(data['status']),
                current_position=current_position,
                destination=Coordinate(**data['destination']),
                remaining_distance=remaining_distance,
                remaining_time=remaining_time,
                progress_percent=data.get('progress_percent', 0)
            )
            
        except Exception as e:
            logger.error(f"네비게이션 상태 조회 실패: {str(e)}")
            raise
    
    # ==================== Temi 제어 ====================
    
    async def move_temi(self, request: TemiMoveRequest) -> TemiMoveResponse:
        """
        Temi를 특정 위치로 이동
        
        Args:
            request: 이동 요청 (Temi ID, 목적지)
            
        Returns:
            TemiMoveResponse: 이동 명령 결과
        """
        try:
            # 1. Temi 위치 조회
            temi_location = await self._get_temi_location(request.temi_id)
            if not temi_location:
                start = Coordinate(x=5, y=5)
            else:
                start = temi_location.coordinate
            
            # 2. 경로 계산
            path_result = await self._calculate_path(
                start=start,
                end=request.destination
            )
            
            if not path_result.success:
                return TemiMoveResponse(
                    success=False,
                    message="경로를 찾을 수 없습니다",
                    temi_id=request.temi_id,
                    destination=request.destination,
                    estimated_time=0
                )
            
            # 3. Realtime DB에 이동 명령 전송
            if self.rtdb:
                try:
                    command_data = {
                        'command': 'MOVE',
                        'destination': {
                            'x': request.destination.x,
                            'y': request.destination.y
                        },
                        'path': [
                            {'x': p.coordinate.x, 'y': p.coordinate.y} 
                            for p in path_result.path
                        ],
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    self.rtdb.child(f'temi/{request.temi_id}/commands')\
                            .child(str(uuid.uuid4()))\
                            .set(command_data)
                    
                    logger.info(f"✅ Temi 이동 명령 전송 완료: {request.temi_id}")
                except Exception as e:
                    logger.warning(f"⚠️ Realtime DB 명령 전송 실패: {str(e)}")
            
            return TemiMoveResponse(
                success=True,
                message="이동 명령이 전송되었습니다",
                temi_id=request.temi_id,
                destination=request.destination,
                path=path_result.path,
                estimated_time=path_result.estimated_time
            )
            
        except Exception as e:
            logger.error(f"Temi 이동 실패: {str(e)}")
            raise
    
    async def stop_temi(self, request: TemiStopRequest) -> dict:
        """Temi 정지"""
        try:
            if self.rtdb:
                try:
                    command_data = {
                        'command': 'STOP',
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    self.rtdb.child(f'temi/{request.temi_id}/commands')\
                            .child(str(uuid.uuid4()))\
                            .set(command_data)
                    
                    logger.info(f"✅ Temi 정지 명령 전송 완료: {request.temi_id}")
                except Exception as e:
                    logger.warning(f"⚠️ Realtime DB 명령 전송 실패: {str(e)}")
            
            return {
                "success": True,
                "message": "정지 명령이 전송되었습니다",
                "temi_id": request.temi_id
            }
            
        except Exception as e:
            logger.error(f"Temi 정지 실패: {str(e)}")
            raise
    
    async def speak_temi(self, request: TemiSpeakRequest) -> dict:
        """Temi 음성 출력"""
        try:
            if self.rtdb:
                try:
                    command_data = {
                        'command': 'SPEAK',
                        'text': request.text,
                        'language': request.language,
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    self.rtdb.child(f'temi/{request.temi_id}/commands')\
                            .child(str(uuid.uuid4()))\
                            .set(command_data)
                    
                    logger.info(f"✅ Temi 음성 출력 명령 전송 완료: {request.temi_id}")
                except Exception as e:
                    logger.warning(f"⚠️ Realtime DB 명령 전송 실패: {str(e)}")
            
            return {
                "success": True,
                "message": "음성 출력 명령이 전송되었습니다",
                "temi_id": request.temi_id,
                "text": request.text
            }
            
        except Exception as e:
            logger.error(f"Temi 음성 출력 실패: {str(e)}")
            raise
    
    # ==================== 주변 상품 조회 ====================
    
    async def get_nearby_products(
        self, 
        request: NearbyProductsRequest
    ) -> NearbyProductsResponse:
        """주변 상품 조회"""
        try:
            # 모든 상품 조회
            docs = self.db.collection(self.products_collection)\
                         .where('is_active', '==', True)\
                         .stream()
            
            nearby_products = []
            
            for doc in docs:
                data = doc.to_dict()
                
                # 상품 위치 정보가 있는 경우만
                if 'location' in data:
                    location = Coordinate(**data['location'])
                    
                    # 거리 계산
                    distance = self._calculate_distance(
                        request.current_location, 
                        location
                    )
                    
                    # 반경 내에 있는 상품
                    if distance <= request.radius:
                        nearby_products.append({
                            'product_id': data['product_id'],
                            'name': data['name'],
                            'category': data.get('category'),
                            'price': data.get('price'),
                            'location': location,
                            'distance': round(distance, 2)
                        })
            
            # 거리순 정렬
            nearby_products.sort(key=lambda x: x['distance'])
            
            # 최대 개수 제한
            if request.limit:
                nearby_products = nearby_products[:request.limit]
            
            return NearbyProductsResponse(
                success=True,
                message=f"{len(nearby_products)}개의 주변 상품을 찾았습니다",
                products=nearby_products,
                total_count=len(nearby_products)
            )
            
        except Exception as e:
            logger.error(f"주변 상품 조회 실패: {str(e)}")
            raise
    
    # ==================== 매장 레이아웃 ====================
    
    async def get_store_layout(self) -> StoreLayoutResponse:
        """매장 레이아웃 정보"""
        try:
            zones = [Zone(**z) for z in self.store_layout['zones']]
            
            charging_stations_data = self.store_layout.get('charging_stations', [])
            charging_stations = []
            
            for station in charging_stations_data:
                if isinstance(station, dict) and 'x' in station and 'y' in station:
                    charging_stations.append(Coordinate(**station))
            
            layout = StoreLayout(
                width=self.store_layout['width'],
                height=self.store_layout['height'],
                zones=zones,
                obstacles=self.store_layout.get('obstacles', []),
                charging_stations=charging_stations
            )
            
            return StoreLayoutResponse(success=True, layout=layout)
            
        except Exception as e:
            logger.error(f"매장 레이아웃 조회 실패: {str(e)}")
            raise
    
    # ==================== 내부 헬퍼 함수 ====================
    
    async def _get_temi_location(self, temi_id: str) -> Optional[TemiLocation]:
        """Temi 위치 조회"""
        try:
            # Realtime DB에서 조회 시도
            if self.rtdb:
                try:
                    data = self.rtdb.child(f'temi/{temi_id}/location').get()
                    if data:
                        return TemiLocation(
                            temi_id=temi_id,
                            coordinate=Coordinate(**data.get('coordinate', {'x': 5, 'y': 5})),
                            heading=data.get('heading', 0),
                            battery=data.get('battery', 100),
                            status=TemiStatus(data.get('status', 'AVAILABLE')),
                            last_updated=datetime.now()
                        )
                except Exception as e:
                    logger.warning(f"⚠️ Realtime DB에서 Temi 위치 조회 실패: {str(e)}")
            
            # Firestore에서 조회
            try:
                doc = self.db.collection("temi_robots").document(temi_id).get()
                if doc.exists:
                    data = doc.to_dict()
                    return TemiLocation(
                        temi_id=temi_id,
                        coordinate=Coordinate(**data.get('location', {'x': 5, 'y': 5})),
                        heading=data.get('heading', 0),
                        battery=data.get('battery', 100),
                        status=TemiStatus(data.get('status', 'AVAILABLE')),
                        last_updated=datetime.fromisoformat(data.get('last_updated', datetime.now().isoformat()))
                    )
            except Exception as e:
                logger.warning(f"⚠️ Firestore에서 Temi 위치 조회 실패: {str(e)}")
            
            return None
            
        except Exception as e:
            logger.error(f"Temi 위치 조회 실패: {str(e)}")
            return None
    
    async def _get_product_location(self, product_id: str) -> Optional[ProductLocation]:
        """상품 위치 조회"""
        try:
            doc = self.db.collection(self.products_collection)\
                        .document(product_id).get()
            
            if not doc.exists:
                return None
            
            data = doc.to_dict()
            
            # location 정보가 있는 경우
            if 'location' in data:
                return ProductLocation(
                    product_id=product_id,
                    product_name=data.get('name'),
                    coordinate=Coordinate(**data['location']),
                    zone_id=data.get('zone_id'),
                    shelf_id=data.get('shelf_id')
                )
            
            # location 정보가 없는 경우 기본 위치 사용 (카테고리 기반)
            category = data.get('category', '').lower()
            default_locations = {
                '스킨케어': Coordinate(x=12, y=10),
                '메이크업': Coordinate(x=32, y=10),
                '바디케어': Coordinate(x=12, y=27),
                '헤어케어': Coordinate(x=32, y=27)
            }
            
            coordinate = default_locations.get(
                data.get('category'),
                Coordinate(x=25, y=20)  # 기본 중앙 위치
            )
            
            return ProductLocation(
                product_id=product_id,
                product_name=data.get('name'),
                coordinate=coordinate,
                zone_id=f"zone_{category}",
                shelf_id=None
            )
            
        except Exception as e:
            logger.error(f"상품 위치 조회 실패: {str(e)}")
            return None
    
    async def _calculate_path(
        self, 
        start: Coordinate, 
        end: Coordinate
    ) -> PathResult:
        """경로 계산"""
        try:
            # A* 알고리즘으로 경로 탐색
            path = self.pathfinder.find_path(
                start=(start.x, start.y),
                end=(end.x, end.y)
            )
            
            if not path:
                return PathResult(
                    success=False,
                    path=[],
                    distance=0,
                    estimated_time=0
                )
            
            # PathNode 리스트 생성
            path_nodes = []
            total_distance = 0
            
            for i, (x, y) in enumerate(path):
                node = PathNode(
                    sequence=i,
                    coordinate=Coordinate(x=x, y=y),
                    action="MOVE"
                )
                path_nodes.append(node)
                
                # 거리 계산
                if i > 0:
                    prev_x, prev_y = path[i-1]
                    total_distance += ((x - prev_x)**2 + (y - prev_y)**2) ** 0.5
            
            # 예상 시간 계산 (속도 기반)
            estimated_time = int(total_distance / self.default_temi_speed)
            
            return PathResult(
                success=True,
                path=path_nodes,
                distance=round(total_distance, 2),
                estimated_time=estimated_time
            )
            
        except Exception as e:
            logger.error(f"경로 계산 실패: {str(e)}")
            return PathResult(
                success=False,
                path=[],
                distance=0,
                estimated_time=0
            )
    
    async def _create_navigation_session(
        self,
        navigation_id: str,
        temi_id: str,
        product_id: str,
        path: List[PathNode],
        estimated_time: int
    ):
        """네비게이션 세션 생성"""
        try:
            session_data = {
                'navigation_id': navigation_id,
                'temi_id': temi_id,
                'product_id': product_id,
                'status': 'IN_PROGRESS',
                'destination': {
                    'x': path[-1].coordinate.x,
                    'y': path[-1].coordinate.y
                },
                'path': [
                    {'x': p.coordinate.x, 'y': p.coordinate.y} 
                    for p in path
                ],
                'estimated_time': estimated_time,
                'progress_percent': 0,
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            }
            
            self.db.collection(self.navigation_collection)\
                  .document(navigation_id)\
                  .set(session_data)
            
            logger.info(f"✅ 네비게이션 세션 생성 완료: {navigation_id}")
            
        except Exception as e:
            logger.error(f"네비게이션 세션 생성 실패: {str(e)}")
            raise
    
    def _calculate_distance(self, coord1: Coordinate, coord2: Coordinate) -> float:
        """두 좌표 간 유클리드 거리 계산"""
        return ((coord1.x - coord2.x)**2 + (coord1.y - coord2.y)**2) ** 0.5


# 싱글톤 인스턴스
navigation_service = NavigationService()