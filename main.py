import pygame
import sys
import math
import importlib
import random
import objects
import enemy
import screen
from objects import get_all_boxes_config
from enemy import ENEMY, initialize_enemies, update_enemy_ai
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 960

boxes_config = get_all_boxes_config(SCREEN_WIDTH, SCREEN_HEIGHT)
BOXES = boxes_config  # 모든 박스 설정 리스트

WORLD_SEGMENTS = [
    ((0, 0), (SCREEN_WIDTH, 0)),
    ((SCREEN_WIDTH, 0), (SCREEN_WIDTH, SCREEN_HEIGHT)),
    ((SCREEN_WIDTH, SCREEN_HEIGHT), (0, SCREEN_HEIGHT)),
    ((0, SCREEN_HEIGHT), (0, 0)),
]

VISIBILITY_SEGMENTS = []
for box in BOXES:
    VISIBILITY_SEGMENTS.extend(box["segments"])
VISIBILITY_SEGMENTS.extend(WORLD_SEGMENTS)
RAY_LENGTH = math.hypot(SCREEN_WIDTH, SCREEN_HEIGHT) + 1

white = (255, 255, 255)
black = (0, 0, 0)
red = (104, 54, 55)

pygame.init()
pygame.display.set_caption("Simple PyGame Example")
screen_surface = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))

# 마우스 위치 표시용 폰트
font_small = pygame.font.Font(None, 20)


# ===== 기본 수학/기하학 함수들 =====

# 두 선분(레이/세그먼트) 사이 교차점을 계산한다
def line_intersection(ray_origin, ray_dir, seg_a, seg_b):
    """광선과 선분 사이의 교차점을 계산하여 가시성 판정에 사용"""
    (x1, y1) = ray_origin
    (dx, dy) = ray_dir
    (x3, y3) = seg_a
    (x4, y4) = seg_b
    x2 = x1 + dx
    y2 = y1 + dy
    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(denom) < 1e-6:
        return None

    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
    u = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)) / denom

    if t >= 0 and 0 <= u <= 1:
        return (x1 + t * dx, y1 + t * dy, t)
    return None


# ===== 충돌/물리 함수들 =====

# 원과 사각형 충돌 여부를 판정한다
def circle_rect_collide(cx, cy, radius, rect):
    """플레이어(원)와 박스(사각형) 사이의 충돌을 판정"""
    nearest_x = max(rect.left, min(cx, rect.right))
    nearest_y = max(rect.top, min(cy, rect.bottom))
    dx = cx - nearest_x
    dy = cy - nearest_y
    return dx * dx + dy * dy < radius * radius


# ===== 객체 생성/위치 함수들 =====


# ===== 화면/렌더링 관련 함수들 =====

# 화면 경계와 반직선의 교차점을 계산하는 함수
def get_ray_screen_intersections(start_x, start_y, dir_x, dir_y, screen_width, screen_height):
    """플레이어에서 마우스 방향으로의 반직선과 화면 경계의 교차점을 계산"""
    if dir_x == 0 and dir_y == 0:
        return (start_x, start_y)

    # 교차점들을 저장할 리스트
    intersections = []
    
    # 화면 경계선들과의 교차점 계산
    # 왼쪽 경계 (x = 0)
    if dir_x != 0:
        t = (0 - start_x) / dir_x
        if t > 0:  # 마우스 방향으로만 (t > 0)
            y = start_y + t * dir_y
            if 0 <= y <= screen_height:
                intersections.append((0, y))
    
    # 오른쪽 경계 (x = screen_width)
    if dir_x != 0:
        t = (screen_width - start_x) / dir_x
        if t > 0:  # 마우스 방향으로만 (t > 0)
            y = start_y + t * dir_y
            if 0 <= y <= screen_height:
                intersections.append((screen_width, y))
    
    # 위쪽 경계 (y = 0)
    if dir_y != 0:
        t = (0 - start_y) / dir_y
        if t > 0:  # 마우스 방향으로만 (t > 0)
            x = start_x + t * dir_x
            if 0 <= x <= screen_width:
                intersections.append((x, 0))
    
    # 아래쪽 경계 (y = screen_height)
    if dir_y != 0:
        t = (screen_height - start_y) / dir_y
        if t > 0:  # 마우스 방향으로만 (t > 0)
            x = start_x + t * dir_x
            if 0 <= x <= screen_width:
                intersections.append((x, screen_height))
    
    # 가장 가까운 교차점을 선택 (마우스 방향으로 가장 먼저 만나는 경계)
    if intersections:
        # 시작점에서 가장 가까운 교차점 선택
        distances = [(abs(x - start_x) + abs(y - start_y), (x, y)) for x, y in intersections]
        distances.sort()  # 가까운 순서로 정렬
        return distances[0][1]  # 가장 가까운 교차점
    
    # 이론상 시작점이 화면 내부이고 방향 벡터가 유효하면 반드시 교차점이 존재한다.
    # 수치 오차 등 예외 상황에서는 시작점을 반환하여 튐을 방지한다.
    return (start_x, start_y)


# 현재 위치에서 가시 범위를 폴리곤 형태로 계산한다
def get_visibility_polygon(origin, segments):
    """레이 캐스팅을 사용하여 플레이어의 가시 범위를 계산"""
    px, py = origin
    angles = set()
    for seg in segments:
        for vx, vy in seg:
            base = math.atan2(vy - py, vx - px)
            angles.update((base - 0.0001, base, base + 0.0001))

    points = []
    for angle in sorted(angles):
        ray_dir = (math.cos(angle) * RAY_LENGTH, math.sin(angle) * RAY_LENGTH)
        closest = None
        for seg in segments:
            hit = line_intersection((px, py), ray_dir, seg[0], seg[1])
            if hit and (closest is None or hit[2] < closest[2]):
                closest = hit
        if closest:
            points.append((angle, closest[0], closest[1]))

    return [(p[1], p[2]) for p in points]

# 플레이어 초기 위치 설정
pos_x = objects.OBJECTS["player"].get("start_x", 0)
pos_y = objects.OBJECTS["player"].get("start_y", 0)

# 적 초기화 (ENEMY 딕셔너리에서 모든 적 생성)
enemies = initialize_enemies(BOXES, SCREEN_WIDTH, SCREEN_HEIGHT)

clock = pygame.time.Clock()
while True:
    clock.tick(60)
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            sys.exit()
        # R키: 모든 코드 재로드
        if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
            import objects
            import enemy
            import screen
            importlib.reload(objects)
            importlib.reload(enemy)
            importlib.reload(screen)
            boxes_config = objects.get_all_boxes_config(SCREEN_WIDTH, SCREEN_HEIGHT)
            BOXES = boxes_config
            VISIBILITY_SEGMENTS = []
            for box in BOXES:
                VISIBILITY_SEGMENTS.extend(box["segments"])
            VISIBILITY_SEGMENTS.extend(WORLD_SEGMENTS)
            # 플레이어 시작 위치도 재설정
            pos_x = objects.OBJECTS["player"].get("start_x", 200)
            pos_y = objects.OBJECTS["player"].get("start_y", 200)
            # 적 시작 위치 재설정 (랜덤)
            enemies = initialize_enemies(BOXES, SCREEN_WIDTH, SCREEN_HEIGHT)
            print("[Reloaded] 모든 설정이 다시 로드되었습니다")

    key_event = pygame.key.get_pressed()
    speed = 3

    # 이동량 분리 (슬라이딩 처리)
    move_x = 0
    move_y = 0
    if key_event[pygame.K_a]:
        move_x -= speed
    if key_event[pygame.K_d]:
        move_x += speed
    if key_event[pygame.K_w]:
        move_y -= speed
    if key_event[pygame.K_s]:
        move_y += speed

    # x축 이동 & 충돌 체크
    new_x = pos_x + move_x
    new_y = pos_y
    can_move_x = True
    for box in BOXES:
        box_rect = pygame.Rect(*box["rect"])
        if circle_rect_collide(new_x, new_y, 20, box_rect):
            can_move_x = False
            break
    if can_move_x:
        pos_x = new_x

    # y축 이동 & 충돌 체크
    new_x = pos_x
    new_y = pos_y + move_y
    can_move_y = True
    for box in BOXES:
        box_rect = pygame.Rect(*box["rect"])
        if circle_rect_collide(new_x, new_y, 20, box_rect):
            can_move_y = False
            break
    if can_move_y:
        pos_y = new_y

    # 화면 경계 제한
    if pos_x < 20:
        pos_x = 20
    if pos_x > SCREEN_WIDTH - 20:
        pos_x = SCREEN_WIDTH - 20
    if pos_y < 20:
        pos_y = 20
    if pos_y > SCREEN_HEIGHT - 20:
        pos_y = SCREEN_HEIGHT - 20

    # 가시영역 계산
    visible_poly = get_visibility_polygon((pos_x, pos_y), VISIBILITY_SEGMENTS)

    # 모든 적 이동 로직
    update_enemy_ai(enemies, pos_x, pos_y, visible_poly, BOXES, SCREEN_WIDTH, SCREEN_HEIGHT, screen.point_in_polygon)

    # 화면 렌더링
    mouse_pos = pygame.mouse.get_pos()
    screen.render_game_screen(screen_surface, visible_poly, BOXES, pos_x, pos_y, enemies, mouse_pos, font_small, SCREEN_WIDTH, SCREEN_HEIGHT, get_ray_screen_intersections)
print("sus")