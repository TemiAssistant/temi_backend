# app/api/navigation.py
"""
네비게이션 관련 API 엔드포인트
Temi 로봇 위치 안내 및 경로 계산
"""

from fastapi import APIRouter, HTTPException, Path, Query
from typing import Optional
import logging

from app.models.navigation import (
    Coordinate,
    NavigationGuideRequest,
    NavigationGuideResponse,
    NavigationStatusResponse,
    PathResult,
    TemiMoveRequest,
    TemiMoveResponse,
    TemiStopRequest,
    TemiSpeakRequest,
    NearbyProductsRequest,
    NearbyProductsResponse,
    LocationsResponse,
    StoreLayoutResponse
)
from app.services.navigation_service import navigation_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/navigation", tags=["Navigation"])


# ==================== 상품 위치 안내 ====================

@router.post(
    "/guide",
    response_model=NavigationGuideResponse,
    summary="상품 위치 안내",
    description="고객이 찾는 상품으로 Temi를 안내합니다"
)
async def guide_to_product(request: NavigationGuideRequest):
    """
    상품 위치 안내 (시나리오 1)
    
    **프로세스:**
    1. 상품 위치 조회
    2. Temi 현재 위치 확인
    3. A* 알고리즘으로 경로 계산
    4. Temi에게 이동 명령 전송
    5. 네비게이션 세션 생성
    
    **사용 예시:**
    - 고객: "설화수 에센스 찾아줘"
    - Temi: 상품 검색 → 위치 계산 → "A-05 구역으로 안내하겠습니다. 따라오세요!"
    
    Args:
        request: 네비게이션 안내 요청
    
    Returns:
        NavigationGuideResponse: 안내 정보 및 경로
    """
    try:
        result = await navigation_service.guide_to_product(request)
        return result
        
    except Exception as e:
        logger.error(f"상품 위치 안내 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"위치 안내 중 오류가 발생했습니다: {str(e)}"
        )


@router.get(
    "/status/{navigation_id}",
    response_model=NavigationStatusResponse,
    summary="네비게이션 상태 조회",
    description="진행 중인 네비게이션의 상태를 조회합니다"
)
async def get_navigation_status(
    navigation_id: str = Path(..., description="네비게이션 세션 ID")
):
    """
    네비게이션 진행 상태 조회
    
    **실시간 업데이트:**
    - 현재 위치
    - 진행률 (%)
    - 남은 거리 및 시간
    
    Args:
        navigation_id: 네비게이션 세션 ID
    
    Returns:
        NavigationStatusResponse: 진행 상태
    """
    try:
        status = await navigation_service.get_navigation_status(navigation_id)
        return status
        
    except Exception as e:
        logger.error(f"네비게이션 상태 조회 실패: {str(e)}")
        raise HTTPException(
            status_code=404 if "찾을 수 없습니다" in str(e) else 500,
            detail=str(e)
        )


@router.post(
    "/status/{navigation_id}/update",
    summary="네비게이션 진행 상황 업데이트",
    description="Temi가 이동하면서 위치를 업데이트합니다"
)
async def update_navigation_progress(
    navigation_id: str = Path(..., description="네비게이션 세션 ID"),
    current_x: float = Query(..., description="현재 X 좌표"),
    current_y: float = Query(..., description="현재 Y 좌표"),
    status: Optional[str] = Query(None, description="상태 (IDLE/NAVIGATING/ARRIVED/FAILED/PAUSED)")
):
    """
    네비게이션 진행 상황 업데이트
    
    **호출 주체:** Temi 로봇 (이동 중 주기적으로 호출)
    
    **상태 값:**
    - IDLE: 대기중
    - NAVIGATING: 이동중
    - ARRIVED: 도착
    - FAILED: 실패
    - PAUSED: 일시정지
    
    Args:
        navigation_id: 네비게이션 세션 ID
        current_x: 현재 X 좌표
        current_y: 현재 Y 좌표
        status: 상태 업데이트 (enum name 또는 value)
    
    Returns:
        성공 메시지
    """
    try:
        from app.models.navigation import NavigationStatus
        
        current_location = Coordinate(x=current_x, y=current_y)
        
        # 상태 검증 및 변환
        nav_status = None
        if status:
            status_upper = status.upper()
            try:
                # 1. enum의 name으로 접근 시도 (NAVIGATING → NavigationStatus.NAVIGATING)
                nav_status = NavigationStatus[status_upper]
                logger.debug(f"✅ 상태 변환 성공: {status} → {nav_status.name} (값: {nav_status.value})")
            except KeyError:
                # 2. enum의 value로 검색 시도 (이동중 → NavigationStatus.NAVIGATING)
                try:
                    nav_status = NavigationStatus(status)
                    logger.debug(f"✅ 상태 변환 성공(value): {status} → {nav_status.name}")
                except ValueError:
                    logger.warning(f"⚠️ 잘못된 상태 값: {status} (무시하고 계속)")
                    # 잘못된 상태면 None으로 처리하고 계속 진행
        
        await navigation_service.update_navigation_progress(
            navigation_id=navigation_id,
            current_location=current_location,
            status=nav_status
        )
        
        return {
            "success": True,
            "message": "진행 상황 업데이트 완료",
            "navigation_id": navigation_id,
            "current_location": {"x": current_x, "y": current_y},
            "status": nav_status.name if nav_status else None
        }
        
    except Exception as e:
        logger.error(f"❌ 진행 상황 업데이트 실패: {str(e)}")
        import traceback
        logger.error(f"스택 트레이스:\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"진행 상황 업데이트 중 오류가 발생했습니다: {str(e)}"
        )


# ==================== 경로 계산 ====================

@router.post(
    "/path",
    response_model=PathResult,
    summary="경로 계산",
    description="두 지점 사이의 최단 경로를 계산합니다"
)
async def calculate_path(
    start_x: float = Query(..., description="시작 X 좌표"),
    start_y: float = Query(..., description="시작 Y 좌표"),
    end_x: float = Query(..., description="목표 X 좌표"),
    end_y: float = Query(..., description="목표 Y 좌표")
):
    """
    경로만 계산 (이동 명령 없이)
    
    **A* 알고리즘 사용:**
    - 장애물 회피
    - 최단 거리
    - 경로 스무딩
    
    Args:
        start_x, start_y: 시작 좌표
        end_x, end_y: 목표 좌표
    
    Returns:
        PathResult: 경로 정보
    """
    try:
        start = Coordinate(x=start_x, y=start_y)
        end = Coordinate(x=end_x, y=end_y)
        
        path = await navigation_service.calculate_path(start, end)
        return path
        
    except Exception as e:
        logger.error(f"경로 계산 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="경로 계산 중 오류가 발생했습니다"
        )


# ==================== Temi 제어 ====================

@router.post(
    "/temi/move",
    response_model=TemiMoveResponse,
    summary="Temi 이동",
    description="Temi를 특정 위치로 이동시킵니다"
)
async def move_temi(request: TemiMoveRequest):
    """
    Temi 로봇 이동 명령
    
    **사용 예시:**
    - 충전소로 복귀
    - 특정 구역으로 이동
    - 고객 따라가기
    
    Args:
        request: Temi 이동 요청
    
    Returns:
        TemiMoveResponse: 이동 명령 결과
    """
    try:
        result = await navigation_service.move_temi(request)
        return result
        
    except Exception as e:
        logger.error(f"Temi 이동 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Temi 이동 중 오류가 발생했습니다: {str(e)}"
        )


@router.post(
    "/temi/stop",
    summary="Temi 정지",
    description="Temi의 이동을 정지시킵니다"
)
async def stop_temi(request: TemiStopRequest):
    """
    Temi 정지
    
    **긴급 정지:**
    - 장애물 감지
    - 배터리 부족
    - 수동 정지
    
    Args:
        request: Temi 정지 요청
    
    Returns:
        성공 메시지
    """
    try:
        result = await navigation_service.stop_temi(request)
        return result
        
    except Exception as e:
        logger.error(f"Temi 정지 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Temi 정지 중 오류가 발생했습니다"
        )


@router.post(
    "/temi/speak",
    summary="Temi 음성 출력",
    description="Temi가 텍스트를 음성으로 출력합니다"
)
async def temi_speak(request: TemiSpeakRequest):
    """
    Temi 음성 안내
    
    **TTS (Text-to-Speech):**
    - 상품 정보 안내
    - 프로모션 안내
    - 환영 메시지
    
    Args:
        request: 음성 출력 요청
    
    Returns:
        성공 메시지
    """
    try:
        result = await navigation_service.temi_speak(request)
        return result
        
    except Exception as e:
        logger.error(f"음성 출력 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="음성 출력 중 오류가 발생했습니다"
        )


# ==================== 위치 정보 ====================

@router.get(
    "/locations",
    response_model=LocationsResponse,
    summary="전체 위치 정보",
    description="매장의 모든 위치 정보를 조회합니다"
)
async def get_all_locations():
    """
    전체 위치 정보 조회
    
    **포함 정보:**
    - 구역(Zone) 정보
    - 상품 위치
    - Temi 위치
    - 충전소 위치
    
    Returns:
        LocationsResponse: 위치 정보
    """
    try:
        locations = await navigation_service.get_all_locations()
        return LocationsResponse(success=True, **locations)
        
    except Exception as e:
        logger.error(f"위치 정보 조회 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="위치 정보 조회 중 오류가 발생했습니다"
        )


@router.post(
    "/locations/nearby",
    response_model=NearbyProductsResponse,
    summary="주변 상품 검색",
    description="특정 좌표 주변의 상품을 검색합니다"
)
async def find_nearby_products(request: NearbyProductsRequest):
    """
    주변 상품 검색
    
    **사용 예시:**
    - 고객 현재 위치 주변 상품
    - 특정 구역 내 상품
    - 반경 내 추천 상품
    
    Args:
        request: 주변 상품 검색 요청
    
    Returns:
        NearbyProductsResponse: 주변 상품 목록
    """
    try:
        result = await navigation_service.find_nearby_products(request)
        return result
        
    except Exception as e:
        logger.error(f"주변 상품 검색 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="주변 상품 검색 중 오류가 발생했습니다"
        )


@router.get(
    "/layout",
    response_model=StoreLayoutResponse,
    summary="매장 레이아웃",
    description="매장의 구조 및 레이아웃 정보를 조회합니다"
)
async def get_store_layout():
    """
    매장 레이아웃 정보
    
    **포함 정보:**
    - 매장 크기 (width, height)
    - 구역 정보
    - 장애물 위치
    - 충전소 위치
    
    Returns:
        StoreLayoutResponse: 레이아웃 정보
    """
    try:
        layout = await navigation_service.get_store_layout()
        return layout
        
    except Exception as e:
        logger.error(f"레이아웃 조회 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="레이아웃 조회 중 오류가 발생했습니다"
        )


# ==================== 유틸리티 ====================

@router.get(
    "/zones",
    summary="구역 목록",
    description="매장의 모든 구역 정보를 조회합니다"
)
async def get_zones():
    """
    구역 목록 조회
    
    **구역 정보:**
    - 구역 ID (예: A-05)
    - 구역 이름 (예: 프리미엄 스킨케어)
    - 좌표 범위
    
    Returns:
        구역 목록
    """
    try:
        layout = await navigation_service.get_store_layout()
        return {
            "success": True,
            "zones": [zone.dict() for zone in layout.layout.zones]
        }
        
    except Exception as e:
        logger.error(f"구역 목록 조회 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="구역 목록 조회 중 오류가 발생했습니다"
        )


@router.get(
    "/products/location/{product_id}",
    summary="상품 위치 조회",
    description="특정 상품의 위치를 조회합니다"
)
async def get_product_location(
    product_id: str = Path(..., description="상품 ID")
):
    """
    상품 위치 조회
    
    Args:
        product_id: 상품 ID
    
    Returns:
        상품 위치 정보
    """
    try:
        from app.core.firebase import firestore_db
        from app.models.navigation import ProductLocation
        
        doc = firestore_db.collection("products").document(product_id).get()
        
        if not doc.exists:
            raise HTTPException(
                status_code=404,
                detail=f"상품을 찾을 수 없습니다: {product_id}"
            )
        
        data = doc.to_dict()
        location = data.get('location', {})
        
        if not location:
            raise HTTPException(
                status_code=404,
                detail="상품 위치 정보가 없습니다"
            )
        
        product_location = ProductLocation(
            product_id=product_id,
            name=data['name'],
            zone=location['zone'],
            shelf=location['shelf'],
            coordinate=Coordinate(x=location['x'], y=location['y'])
        )
        
        return {
            "success": True,
            "product": product_location.dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"상품 위치 조회 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="상품 위치 조회 중 오류가 발생했습니다"
        )