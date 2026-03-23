# enemy.py
# 적 오브젝트 설정을 모아두는 파일

import random
import math

# 적 오브젝트 정의
# ENEMY 딕셔너리에 적을 추가하면 자동으로 게임에 적용됩니다
# 각 적은 다음과 같은 속성을 가질 수 있습니다:
# - name: 적의 이름 (고유 식별자)
# - color: RGB 색상 튜플 (255, 255, 0) 또는 None
# - image: 이미지 파일 경로 또는 None (색상 사용)
# - type: 적 타입
#   * "random_walker": 무작위로 돌아다니는 적
#   * "chaser": 플레이어를 보면 추적하는 적 (마지막 본 위치로 이동)
# - speed: 이동 속도 (숫자)
# - radius: 적의 크기 (반지름)
ENEMY = {
    "yellow_dot": {
        "name": "yellow_dot",     # 적 이름
        "color": (255, 255, 0),  # 노란색
        "image": None,           # 이미지 경로 또는 None
        "type": "random_walker", # 무작위로 돌아다니는 적
        "speed": 2,              # 이동 속도
        "radius": 15,            # 반지름
    },
    "red_chaser": {
        "name": "red_chaser",    # 적 이름
        "color": (255, 0, 0),    # 빨간색
        "image": None,           # 이미지 경로 또는 None
        "type": "chaser",        # 플레이어를 보면 추적하는 적
        "speed": 1.8,            # 이동 속도
        "radius": 12,            # 반지름 (작음)
    },
    "purple_chaser": {
        "name": "purple_chaser", # 적 이름
        "color": (128, 0, 128),  # 보라색
        "image": None,           # 이미지 경로 또는 None
        "type": "chaser",        # 플레이어를 보면 추적하는 적
        "speed": 2.2,            # 빠른 추적자
        "radius": 14,            # 반지름
    },
}


# ===== 적 관련 함수들 =====

def get_random_enemy_position(boxes, enemy_radius, screen_width, screen_height):
    """적의 랜덤 시작 위치를 생성 (박스와 충돌하지 않는 위치)"""
    max_attempts = 100  # 최대 시도 횟수
    for _ in range(max_attempts):
        x = random.randint(enemy_radius, screen_width - enemy_radius)
        y = random.randint(enemy_radius, screen_height - enemy_radius)

        # 박스와 충돌하는지 확인
        collision = False
        for box in boxes:
            box_rect = pygame.Rect(*box["rect"])
            if circle_rect_collide(x, y, enemy_radius, box_rect):
                collision = True
                break

        if not collision:
            return x, y

    # 실패 시 기본 위치 반환
    return screen_width // 2, screen_height // 2


def initialize_enemies(BOXES, SCREEN_WIDTH, SCREEN_HEIGHT):
    """ENEMY 딕셔너리에서 모든 적을 초기화하여 반환"""
    enemies = {}
    for enemy_key, enemy_data in ENEMY.items():
        enemy_radius = enemy_data["radius"]
        enemy_pos_x, enemy_pos_y = get_random_enemy_position(BOXES, enemy_radius, SCREEN_WIDTH, SCREEN_HEIGHT)
        max_hp = int(enemy_data.get("max_hp", 100))
        enemies[enemy_key] = {
            "pos_x": enemy_pos_x,
            "pos_y": enemy_pos_y,
            "angle": random.uniform(0, 2 * math.pi),  # 무작위 초기 방향
            "data": enemy_data,  # ENEMY 데이터 참조
            "hp": max_hp,
            "max_hp": max_hp,
            "last_seen_player": None,  # 마지막으로 본 플레이어 위치 (x, y)
            "chase_timer": 0,  # 추적 유지 시간
        }
    return enemies


def update_enemy_ai(enemies, pos_x, pos_y, visible_poly, BOXES, SCREEN_WIDTH, SCREEN_HEIGHT, point_in_polygon_func, box_rects=None):
    """모든 적의 AI와 이동을 업데이트한다.

    box_rects가 전달되면 매 프레임 Rect 생성을 피해서 성능을 개선한다.
    """
    if box_rects is None:
        box_rects = [pygame.Rect(*box["rect"]) for box in BOXES]

    for enemy_key, enemy in enemies.items():
        enemy_data = enemy["data"]
        enemy_type = enemy_data["type"]
        enemy_speed = enemy_data["speed"]
        enemy_radius = enemy_data["radius"]
        enemy_pos_x = enemy["pos_x"]
        enemy_pos_y = enemy["pos_y"]
        enemy_angle = enemy["angle"]

        # 플레이어 시야 폴리곤 안에 적이 있는지 확인 (가림 여부를 동일 기준으로 사용)
        can_see_player = False
        if visible_poly:
            can_see_player = point_in_polygon_func((enemy_pos_x, enemy_pos_y), visible_poly)
            if can_see_player:
                enemy["last_seen_player"] = (pos_x, pos_y)
                # 적 타입별 추적 시간 설정
                if enemy_type == "chaser":
                    enemy["chase_timer"] = 300  # 5초간 추적 유지
                else:
                    enemy["chase_timer"] = 120  # 다른 타입은 2초만 추적

        # 추적 타이머 감소
        if enemy["chase_timer"] > 0:
            enemy["chase_timer"] -= 1

        # 이동 방향 결정
        if enemy_type == "chaser" and enemy["last_seen_player"] and enemy["chase_timer"] > 0:
            # 플레이어 추적
            target_x, target_y = enemy["last_seen_player"]
            dx = target_x - enemy_pos_x
            dy = target_y - enemy_pos_y
            distance = math.sqrt(dx*dx + dy*dy)
            if distance > 0:
                enemy_angle = math.atan2(dy, dx)
                enemy["angle"] = enemy_angle
        else:
            # 무작위 이동 (random_walker)
            enemy_angle += random.uniform(-0.1, 0.1)
            enemy["angle"] = enemy_angle

        # 이동 계산
        enemy_move_x = math.cos(enemy_angle) * enemy_speed
        enemy_move_y = math.sin(enemy_angle) * enemy_speed

        # 적 x축 이동 & 충돌 체크
        new_enemy_x = enemy["pos_x"] + enemy_move_x
        new_enemy_y = enemy["pos_y"]
        can_enemy_move_x = True
        for box_rect in box_rects:
            if circle_rect_collide(new_enemy_x, new_enemy_y, enemy_radius, box_rect):
                can_enemy_move_x = False
                break
        if can_enemy_move_x:
            enemy["pos_x"] = new_enemy_x

        # 적 y축 이동 & 충돌 체크
        new_enemy_x = enemy["pos_x"]
        new_enemy_y = enemy["pos_y"] + enemy_move_y
        can_enemy_move_y = True
        for box_rect in box_rects:
            if circle_rect_collide(new_enemy_x, new_enemy_y, enemy_radius, box_rect):
                can_enemy_move_y = False
                break
        if can_enemy_move_y:
            enemy["pos_y"] = new_enemy_y

        # 적 화면 경계 제한
        if enemy["pos_x"] < enemy_radius:
            enemy["pos_x"] = enemy_radius
            enemy["angle"] = random.uniform(0, math.pi)  # 방향 변경
        if enemy["pos_x"] > SCREEN_WIDTH - enemy_radius:
            enemy["pos_x"] = SCREEN_WIDTH - enemy_radius
            enemy["angle"] = random.uniform(math.pi, 2 * math.pi)  # 방향 변경
        if enemy["pos_y"] < enemy_radius:
            enemy["pos_y"] = enemy_radius
            enemy["angle"] = random.uniform(math.pi/2, 3*math.pi/2)  # 방향 변경
        if enemy["pos_y"] > SCREEN_HEIGHT - enemy_radius:
            enemy["pos_y"] = SCREEN_HEIGHT - enemy_radius
            enemy["angle"] = random.uniform(-math.pi/2, math.pi/2)  # 방향 변경


# ===== 필요한 외부 함수들 (임시) =====
# 이 함수들은 python.py에서 가져와야 함

def circle_rect_collide(cx, cy, radius, rect):
    """원과 사각형 충돌 여부를 판정"""
    nearest_x = max(rect.left, min(cx, rect.right))
    nearest_y = max(rect.top, min(cy, rect.bottom))
    dx = cx - nearest_x
    dy = cy - nearest_y
    return dx * dx + dy * dy < radius * radius

# pygame 임포트 (충돌 판정에 필요)
try:
    import pygame
except ImportError:
    pygame = None