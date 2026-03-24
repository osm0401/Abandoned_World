# screen.py
# 화면 렌더링 관련 모든 기능을 모아둔 파일

import pygame
import math
import setting as st

# 이미지 캐시 (성능 최적화)
_image_cache = {}
always_see = st.ALWAYS_SEE
def load_image(image_path):
    """이미지를 로드하고 캐시 (중복 로드 방지)"""
    if image_path in _image_cache:
        return _image_cache[image_path]
    
    try:
        image = pygame.image.load(image_path).convert_alpha()
        _image_cache[image_path] = image
        return image
    except pygame.error:
        print(f"이미지 로드 실패: {image_path}")
        return None

def render_game_screen(screen, visible_poly, BOXES, pos_x, pos_y, enemies, bullets, mouse_pos, font_small, SCREEN_WIDTH, SCREEN_HEIGHT, get_ray_screen_intersections, ammo=0, magazine_size=0, reload_timer=0, doors=None):
    """
    게임 화면을 렌더링하는 함수

    Args:
        screen: pygame 화면 객체
        visible_poly: 가시성 폴리곤 좌표 리스트
        BOXES: 박스 설정 리스트
        pos_x, pos_y: 플레이어 위치
        enemies: 적 객체 딕셔너리
        mouse_pos: 마우스 위치
        font_small: 작은 폰트 객체
        SCREEN_WIDTH, SCREEN_HEIGHT: 화면 크기
        get_ray_screen_intersections: 화면 경계 교차점 계산 함수
    """
    # 색상 정의
    black = st.COLOR_BLACK
    white = st.COLOR_WHITE
    red = st.COLOR_RED

    # 화면 초기화
    screen.fill(black)

    # 가시성 영역 그리기
    # 자기교차 폴리곤에서 생기는 검은 삼각형 아티팩트를 피하기 위해
    # 플레이어 중심 기준 삼각형 팬으로 채운다.
    if visible_poly and len(visible_poly) >= 2:
        origin = (int(pos_x), int(pos_y))
        for i in range(len(visible_poly)):
            p1 = visible_poly[i]
            p2 = visible_poly[(i + 1) % len(visible_poly)]
            pygame.draw.polygon(screen, white, [origin, p1, p2])

    # 모든 박스 그리기
    for box in BOXES:
        box_rect = pygame.Rect(*box["rect"])
        
        # 이미지 또는 색상 박스 그리기
        if box.get("image") and box["image"] != "None":
            # 이미지 사용
            image = load_image(box["image"])
            if image:
                # 이미지 크기를 박스 크기에 맞게 조정
                scaled_image = pygame.transform.scale(image, (box_rect.width, box_rect.height))
                screen.blit(scaled_image, box_rect)
            else:
                # 이미지 로드 실패 시 색상 박스로 표시
                pygame.draw.rect(screen, box["color"], box_rect)
        else:
            # 색상 박스
            pygame.draw.rect(screen, box["color"], box_rect)

    # 플레이어 그리기
    pygame.draw.circle(screen, red, (pos_x, pos_y), 20)

    # 플레이어에서 마우스 방향으로 반직선 그리기
    dir_x = mouse_pos[0] - pos_x
    dir_y = mouse_pos[1] - pos_y
    # 방향 벡터 정규화
    length = math.sqrt(dir_x*dir_x + dir_y*dir_y)
    if length > 0:
        dir_x /= length
        dir_y /= length
        # 화면 경계 교차점 찾기
        end_point = get_ray_screen_intersections(pos_x, pos_y, dir_x, dir_y, SCREEN_WIDTH, SCREEN_HEIGHT)
        pygame.draw.line(screen, red, (pos_x, pos_y), end_point, 2)

    # 모든 적 그리기
    for enemy_key, enemy in enemies.items():
        enemy_data = enemy["data"]
        enemy_pos_x = enemy["pos_x"]
        enemy_pos_y = enemy["pos_y"]
        enemy_radius = enemy_data["radius"]
        enemy_hp = enemy.get("hp", enemy_data.get("hp", 100))
        enemy_max_hp = max(1, enemy.get("max_hp", enemy_data.get("max_hp", 100)))
        hp_ratio = max(0.0, min(1.0, enemy_hp / enemy_max_hp))

        # 시야 판정: always_see가 False면 가시 폴리곤 안일 때만 표시
        can_see_enemy = always_see or (visible_poly and point_in_polygon((enemy_pos_x, enemy_pos_y), visible_poly))

        if can_see_enemy:
            pygame.draw.circle(screen, enemy_data["color"], (int(enemy_pos_x), int(enemy_pos_y)), enemy_radius)
            alert_text = font_small.render("!", True, black)
            text_rect = alert_text.get_rect(center=(int(enemy_pos_x), int(enemy_pos_y)))
            screen.blit(alert_text, text_rect)

            # 적 바로 아래 체력바 (적이 보일 때만)
            bar_width = max(24, enemy_radius * 2)
            bar_height = 5
            bar_x = int(enemy_pos_x - bar_width / 2)
            bar_y = int(enemy_pos_y + enemy_radius + 6)
            pygame.draw.rect(screen, st.COLOR_HP_BG, (bar_x, bar_y, bar_width, bar_height))
            pygame.draw.rect(screen, st.COLOR_HP_FILL, (bar_x, bar_y, int(bar_width * hp_ratio), bar_height))
    # 총알 그리기
    for bullet in bullets:
        pygame.draw.circle(screen, bullet["color"], (int(bullet["x"]), int(bullet["y"])), bullet["radius"])

    # 문 그리기 (닫힘: 빨강, 열림: 노랑)
    if doors:
        for door in doors:
            rect = door["rect"]
            color = st.COLOR_DOOR_OPEN if door.get("open", False) else st.COLOR_DOOR_CLOSED
            pygame.draw.rect(screen, color, rect)

    # 마우스 위치 표시
    mouse_text = font_small.render(f"Mouse: {mouse_pos[0]}, {mouse_pos[1]}", True, st.COLOR_UI_RED)
    screen.blit(mouse_text, (10, 10))

    # 탄약 / 재장전 표시
    if reload_timer > 0:
        ammo_text = font_small.render("RELOADING...", True, st.COLOR_UI_RED)
    else:
        ammo_text = font_small.render(f"AMMO  {ammo} / {magazine_size}", True, st.COLOR_UI_RED)
    screen.blit(ammo_text, (10, 25))

    # 화면 업데이트
    pygame.display.update()


def point_in_polygon(point, polygon):
    """
    점이 폴리곤 안에 있는지 확인하는 함수 (screen.py에서 사용)
    """
    x, y = point
    n = len(polygon)
    inside = False

    p1x, p1y = polygon[0]
    for i in range(1, n + 1):
        p2x, p2y = polygon[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y

    return inside