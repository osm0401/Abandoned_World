# enemy.py
# 적 오브젝트 설정을 모아두는 파일

import random
import math

ENEMY = {
    "pistol": {
        "name": "pistol",
        "color": (255, 230, 80),
        "image": None,
        "type": "pistol",
        "speed": 2.0,
        "radius": 14,
    },
    "shotgun": {
        "name": "shotgun",
        "color": (255, 140, 0),
        "image": None,
        "type": "shotgun",
        "speed": 1.8,
        "radius": 16,
    },
    "smg": {
        "name": "smg",
        "color": (180, 255, 180),
        "image": None,
        "type": "smg",
        "speed": 2.4,
        "radius": 13,
    },
    "ar": {
        "name": "ar",
        "color": (120, 255, 220),
        "image": None,
        "type": "ar",
        "speed": 2.2,
        "radius": 14,
    },
    "sniper": {
        "name": "sniper",
        "color": (120, 220, 255),
        "image": None,
        "type": "sniper",
        "speed": 1.6,
        "radius": 12,
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
                enemy["chase_timer"] = 300

        # 추적 타이머 감소
        if enemy["chase_timer"] > 0:
            enemy["chase_timer"] -= 1

        # 이동 방향 결정
        if enemy["last_seen_player"] and enemy["chase_timer"] > 0:
            target_x, target_y = enemy["last_seen_player"]
            dx = target_x - enemy_pos_x
            dy = target_y - enemy_pos_y
            distance = math.sqrt(dx*dx + dy*dy)
            if distance > 0:
                enemy_angle = math.atan2(dy, dx)
                enemy["angle"] = enemy_angle
        else:
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