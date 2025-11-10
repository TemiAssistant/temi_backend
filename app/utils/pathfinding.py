# app/utils/pathfinding.py
"""
A* 알고리즘 기반 경로 계산
"""

import math
from typing import List, Tuple, Optional, Set
from app.models.navigation import Coordinate, PathNode
import heapq


class PathFinder:
    """A* 알고리즘 경로 탐색"""
    
    def __init__(self, grid_size: Tuple[float, float], obstacles: List[dict] = None):
        """
        Args:
            grid_size: (width, height) 그리드 크기
            obstacles: 장애물 리스트
        """
        self.width, self.height = grid_size
        self.obstacles = obstacles or []
        self.grid_resolution = 0.5  # 0.5m 단위 그리드
    
    def calculate_path(
        self,
        start: Coordinate,
        end: Coordinate,
        speed: float = 0.8
    ) -> Tuple[List[Coordinate], float, float]:
        """
        A* 알고리즘으로 경로 계산
        
        Args:
            start: 시작 좌표
            end: 목표 좌표
            speed: 이동 속도 (m/s)
        
        Returns:
            (경로, 총 거리, 예상 시간)
        """
        # 간단한 직선 경로 (장애물 없는 경우)
        # TODO: 실제 A* 알고리즘 구현
        
        path = self._calculate_simple_path(start, end)
        distance = self._calculate_total_distance(path)
        time = distance / speed if speed > 0 else 0
        
        return path, distance, time
    
    def _calculate_simple_path(
        self,
        start: Coordinate,
        end: Coordinate
    ) -> List[Coordinate]:
        """
        간단한 경로 계산 (직선 + 중간점)
        실제 환경에서는 A* 알고리즘 적용 필요
        """
        path = [start]
        
        # 중간 경유지 계산 (매 2미터마다)
        distance = self._distance(start, end)
        num_waypoints = max(1, int(distance / 2.0))
        
        for i in range(1, num_waypoints):
            ratio = i / num_waypoints
            mid_x = start.x + (end.x - start.x) * ratio
            mid_y = start.y + (end.y - start.y) * ratio
            path.append(Coordinate(x=mid_x, y=mid_y))
        
        path.append(end)
        return path
    
    def _calculate_total_distance(self, path: List[Coordinate]) -> float:
        """경로의 총 거리 계산"""
        total = 0.0
        for i in range(len(path) - 1):
            total += self._distance(path[i], path[i + 1])
        return total
    
    def _distance(self, a: Coordinate, b: Coordinate) -> float:
        """두 점 사이의 유클리드 거리"""
        return math.sqrt((b.x - a.x) ** 2 + (b.y - a.y) ** 2)
    
    def _heuristic(self, a: Coordinate, b: Coordinate) -> float:
        """A* 휴리스틱 (맨하탄 거리)"""
        return abs(b.x - a.x) + abs(b.y - a.y)
    
    def is_valid_coordinate(self, coord: Coordinate) -> bool:
        """좌표가 유효한지 확인"""
        if coord.x < 0 or coord.x > self.width:
            return False
        if coord.y < 0 or coord.y > self.height:
            return False
        
        # 장애물 체크
        for obstacle in self.obstacles:
            # TODO: 장애물과의 충돌 검사
            pass
        
        return True
    
    def smooth_path(self, path: List[Coordinate]) -> List[Coordinate]:
        """경로 스무딩 (불필요한 점 제거)"""
        if len(path) <= 2:
            return path
        
        smoothed = [path[0]]
        
        for i in range(1, len(path) - 1):
            # 각도 변화가 큰 지점만 포함
            prev = path[i - 1]
            curr = path[i]
            next_point = path[i + 1]
            
            angle_change = self._calculate_angle_change(prev, curr, next_point)
            
            if angle_change > 15:  # 15도 이상 변화
                smoothed.append(curr)
        
        smoothed.append(path[-1])
        return smoothed
    
    def _calculate_angle_change(
        self,
        p1: Coordinate,
        p2: Coordinate,
        p3: Coordinate
    ) -> float:
        """세 점 사이의 각도 변화 계산"""
        angle1 = math.atan2(p2.y - p1.y, p2.x - p1.x)
        angle2 = math.atan2(p3.y - p2.y, p3.x - p2.x)
        
        diff = abs(math.degrees(angle2 - angle1))
        return min(diff, 360 - diff)