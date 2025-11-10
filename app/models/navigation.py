# app/models/navigation.py
"""
네비게이션 관련 Pydantic 모델
Temi 로봇 위치 안내 및 경로 계산
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Tuple
from datetime import datetime
from enum import Enum


# ==================== Enums ====================

class NavigationStatus(str, Enum):
    """네비게이션 상태"""
    IDLE = "대기중"
    NAVIGATING = "이동중"
    ARRIVED = "도착"
    FAILED = "실패"
    PAUSED = "일시정지"


class TemiStatus(str, Enum):
    """Temi 로봇 상태"""
    AVAILABLE = "사용가능"
    BUSY = "사용중"
    CHARGING = "충전중"
    ERROR = "오류"
    OFFLINE = "오프라인"


# ==================== 좌표 및 위치 ====================

class Coordinate(BaseModel):
    """2D 좌표"""
    x: float = Field(..., description="X 좌표 (미터)")
    y: float = Field(..., description="Y 좌표 (미터)")


class Zone(BaseModel):
    """매장 구역"""
    zone_id: str = Field(..., description="구역 ID (예: A-05)")
    name: str = Field(..., description="구역 이름")
    x1: float = Field(..., description="좌상단 X")
    y1: float = Field(..., description="좌상단 Y")
    x2: float = Field(..., description="우하단 X")
    y2: float = Field(..., description="우하단 Y")
    center: Optional[Coordinate] = None
    
    def get_center(self) -> Coordinate:
        """구역 중심점 계산"""
        return Coordinate(
            x=(self.x1 + self.x2) / 2,
            y=(self.y1 + self.y2) / 2
        )


class ProductLocation(BaseModel):
    """상품 위치 정보"""
    product_id: str
    name: str
    zone: str
    shelf: int
    coordinate: Coordinate


# ==================== 경로 ====================

class PathNode(BaseModel):
    """경로 노드"""
    coordinate: Coordinate
    action: Optional[str] = Field(None, description="동작 (move, turn, stop)")
    distance_from_start: float = Field(0, description="시작점으로부터 거리")


class PathResult(BaseModel):
    """경로 계산 결과"""
    success: bool = True
    start: Coordinate
    end: Coordinate
    path: List[Coordinate] = Field(..., description="경로 좌표 리스트")
    total_distance: float = Field(..., description="총 거리 (미터)")
    estimated_time: float = Field(..., description="예상 시간 (초)")
    waypoints: List[PathNode] = Field(default_factory=list, description="경유지")


# ==================== Temi 관련 ====================

class TemiLocation(BaseModel):
    """Temi 위치 정보"""
    temi_id: str
    coordinate: Coordinate
    heading: float = Field(..., ge=0, lt=360, description="방향 (0-360도)")
    battery: int = Field(..., ge=0, le=100, description="배터리 (%)")
    status: TemiStatus
    last_updated: datetime


class TemiCommand(BaseModel):
    """Temi 명령"""
    command_id: str
    temi_id: str
    command_type: str = Field(..., description="명령 타입 (goto, stop, speak)")
    destination: Optional[Coordinate] = None
    parameters: Optional[dict] = None
    created_at: datetime


# ==================== 네비게이션 요청/응답 ====================

class NavigationGuideRequest(BaseModel):
    """네비게이션 안내 요청"""
    product_id: str = Field(..., description="안내할 상품 ID")
    temi_id: str = Field("temi_001", description="사용할 Temi ID")
    customer_id: Optional[str] = Field(None, description="고객 ID")
    start_location: Optional[Coordinate] = Field(None, description="시작 위치 (없으면 현재 Temi 위치)")


class NavigationGuideResponse(BaseModel):
    """네비게이션 안내 응답"""
    success: bool = True
    navigation_id: str = Field(..., description="네비게이션 세션 ID")
    product: ProductLocation
    temi_location: Coordinate
    path: PathResult
    estimated_arrival: datetime
    message: str = Field(..., description="안내 메시지")


class NavigationStatusResponse(BaseModel):
    """네비게이션 상태 응답"""
    success: bool = True
    navigation_id: str
    status: NavigationStatus
    current_location: Coordinate
    destination: Coordinate
    progress: float = Field(..., ge=0, le=100, description="진행률 (%)")
    distance_remaining: float = Field(..., description="남은 거리 (미터)")
    time_remaining: float = Field(..., description="남은 시간 (초)")


# ==================== 위치 조회 ====================

class LocationsResponse(BaseModel):
    """위치 정보 응답"""
    success: bool = True
    zones: List[Zone]
    products: List[ProductLocation]
    temi_locations: List[TemiLocation]
    charging_stations: List[Coordinate]


class NearbyProductsRequest(BaseModel):
    """주변 상품 검색 요청"""
    coordinate: Coordinate
    radius: float = Field(5.0, description="반경 (미터)")
    limit: int = Field(10, ge=1, le=50, description="최대 결과 수")


class NearbyProductsResponse(BaseModel):
    """주변 상품 응답"""
    success: bool = True
    center: Coordinate
    radius: float
    products: List[ProductLocation]
    total: int


# ==================== Temi 제어 ====================

class TemiMoveRequest(BaseModel):
    """Temi 이동 요청"""
    temi_id: str
    destination: Coordinate
    speed: float = Field(0.8, ge=0.1, le=1.0, description="이동 속도 (0.1-1.0)")
    voice_guide: bool = Field(True, description="음성 안내 여부")
    message: Optional[str] = Field(None, description="안내 메시지")


class TemiMoveResponse(BaseModel):
    """Temi 이동 응답"""
    success: bool = True
    command_id: str
    temi_id: str
    current_location: Coordinate
    destination: Coordinate
    estimated_time: float
    message: str


class TemiStopRequest(BaseModel):
    """Temi 정지 요청"""
    temi_id: str
    reason: Optional[str] = Field(None, description="정지 사유")


class TemiSpeakRequest(BaseModel):
    """Temi 음성 출력 요청"""
    temi_id: str
    text: str = Field(..., description="출력할 텍스트")
    language: str = Field("ko-KR", description="언어 코드")


# ==================== 매장 레이아웃 ====================

class StoreLayout(BaseModel):
    """매장 레이아웃"""
    width: float = Field(..., description="매장 가로 길이 (미터)")
    height: float = Field(..., description="매장 세로 길이 (미터)")
    zones: List[Zone]
    obstacles: List[dict] = Field(default_factory=list, description="장애물 위치")
    charging_stations: List[Coordinate]


class StoreLayoutResponse(BaseModel):
    """매장 레이아웃 응답"""
    success: bool = True
    layout: StoreLayout