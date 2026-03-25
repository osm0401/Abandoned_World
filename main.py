import pygame
import sys
import math
import json
import os
import random
import queue
import threading
import tkinter as tk
import objects
import enemy
import screen
import gun
import setting as st
from objects import get_all_boxes_config
from enemy import initialize_enemies, update_enemy_ai
from gun import GUNS, make_bullets
SCREEN_WIDTH = st.SCREEN_WIDTH
SCREEN_HEIGHT = st.SCREEN_HEIGHT
PLAYER_RADIUS = st.PLAYER_RADIUS
PLAYER_SPEED = st.PLAYER_SPEED
TARGET_FPS = st.TARGET_FPS
DOOR_THICKNESS = st.DOOR_THICKNESS

# 맵 순환 목록: normal_a -> normal_z
MAP_CYCLE_FILES = [f"maps/normal_{chr(code)}.json" for code in range(ord("a"), ord("z") + 1)]
MAP_INDEX = 0
MAP_FILE = MAP_CYCLE_FILES[MAP_INDEX]
CURRENT_MAP_FILE = MAP_FILE

SIDE_TO_DOOR_ID = {
    "top": "door_top",
    "bottom": "door_bottom",
    "left": "door_left",
    "right": "door_center",
}
OPPOSITE_SIDE = {
    "top": "bottom",
    "bottom": "top",
    "left": "right",
    "right": "left",
}
SIDE_DELTAS = {
    "top": (0, -1),
    "bottom": (0, 1),
    "left": (-1, 0),
    "right": (1, 0),
}

# 맵 연결 그래프: {"maps/normal_a.json": {"right": "maps/normal_b.json", ...}, ...}
MAP_CONNECTIONS = {MAP_FILE: {}}
VISITED_MAPS = {MAP_FILE}
CLEARED_MAPS = set()
MAP_POSITIONS = {MAP_FILE: (0, 0)}
POSITION_TO_MAP = {(0, 0): MAP_FILE}

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
RAY_ORIGIN_BIAS = st.RAY_ORIGIN_BIAS

pygame.init()
pygame.display.set_caption(st.WINDOW_TITLE)
screen_surface = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))

# 마우스 위치 표시용 폰트
font_small = pygame.font.Font(None, st.FONT_SMALL_SIZE)
DEBUG_COMMAND_QUEUE = queue.Queue()


def queue_debug_command(command_name, payload=None):
    """디버그 창 명령을 메인 루프로 전달"""
    DEBUG_COMMAND_QUEUE.put((command_name, payload))


def start_debug_window():
    """별도 디버그 제어 창을 실행"""
    def run_debug_window():
        try:
            root = tk.Tk()
            root.title("debug")
            root.geometry("420x340")
            root.resizable(False, False)

            gun_var = tk.StringVar(value=gun.CURRENT_GUN)
            x_var = tk.StringVar(value=str(SCREEN_WIDTH // 2))
            y_var = tk.StringVar(value=str(SCREEN_HEIGHT // 2))
            status_var = tk.StringVar(value="ready")

            frame = tk.Frame(root, padx=18, pady=18)
            frame.pack(fill="both", expand=True)

            tk.Button(frame, text="kill_all", command=lambda: queue_debug_command("kill_all")).pack(fill="x")

            tk.Label(frame, text="teleport x").pack(anchor="w", pady=(10, 0))
            tk.Entry(frame, textvariable=x_var).pack(fill="x")
            tk.Label(frame, text="teleport y").pack(anchor="w", pady=(6, 0))
            tk.Entry(frame, textvariable=y_var).pack(fill="x")

            def send_teleport():
                try:
                    target_x = float(x_var.get())
                    target_y = float(y_var.get())
                except ValueError:
                    status_var.set("teleport: invalid")
                    return
                queue_debug_command("teleport", (target_x, target_y))
                status_var.set("teleport queued")

            tk.Button(frame, text="teleport", command=send_teleport).pack(fill="x", pady=(8, 0))

            tk.Label(frame, text="switch_gun").pack(anchor="w", pady=(10, 0))
            tk.OptionMenu(frame, gun_var, *sorted(GUNS.keys())).pack(fill="x")

            def send_switch_gun():
                queue_debug_command("switch_gun", gun_var.get())
                status_var.set(f"switch_gun: {gun_var.get()}")

            tk.Button(frame, text="apply gun", command=send_switch_gun).pack(fill="x", pady=(8, 0))
            tk.Label(frame, textvariable=status_var, anchor="w").pack(fill="x", pady=(12, 0))

            root.mainloop()
        except Exception as ex:
            print(f"[Debug Window Failed] {ex}")

    threading.Thread(target=run_debug_window, daemon=True).start()


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


def build_box_segments(left, top, width, height):
    """박스 사각형으로 월드 좌표 선분을 생성"""
    return [
        ((left, top), (left + width, top)),
        ((left + width, top), (left + width, top + height)),
        ((left + width, top + height), (left, top + height)),
        ((left, top + height), (left, top)),
    ]


def build_visibility_segments(boxes):
    """현재 박스 목록으로 가시성 선분 리스트를 재생성"""
    segments = []
    for box in boxes:
        segments.extend(box["segments"])
    segments.extend(WORLD_SEGMENTS)
    return segments


def create_box_entry(name, left, top, width, height, color, image=None):
    """사각형 정보를 게임 박스 엔트리로 변환"""
    return {
        "name": name,
        "width": width,
        "height": height,
        "left": left,
        "top": top,
        "rect": (left, top, width, height),
        "segments": build_box_segments(left, top, width, height),
        "image": image,
        "color": color,
    }


def create_room_config(screen_width, screen_height):
    """문 잠금 해제 조건에 사용할 중앙 방 영역을 생성"""
    room_w = st.ROOM_WIDTH
    room_h = st.ROOM_HEIGHT
    room_left = screen_width // 2 - room_w // 2
    room_top = screen_height // 2 - room_h // 2
    return pygame.Rect(room_left, room_top, room_w, room_h)


def create_room_doors(screen_width, screen_height):
    """요청한 4개 문(위/아래/왼쪽/가운데) 정의를 생성"""
    room_rect = create_room_config(screen_width, screen_height)
    door_w = st.DOOR_WIDTH
    door_h = st.DOOR_HEIGHT

    # 화면 끝 기준으로 문을 배치한다.
    top_rect = pygame.Rect(screen_width // 2 - door_w // 2, 0, door_w, DOOR_THICKNESS)
    bottom_rect = pygame.Rect(screen_width // 2 - door_w // 2, screen_height - DOOR_THICKNESS, door_w, DOOR_THICKNESS)
    left_rect = pygame.Rect(0, screen_height // 2 - door_h // 2, DOOR_THICKNESS, door_h)
    # "가운데 쪽" 문은 오른쪽 화면 중앙에 배치
    center_rect = pygame.Rect(screen_width - DOOR_THICKNESS, screen_height // 2 - door_h // 2, DOOR_THICKNESS, door_h)

    doors = [
        {"id": "door_top", "rect": top_rect, "open": False, "room": room_rect},
        {"id": "door_bottom", "rect": bottom_rect, "open": False, "room": room_rect},
        {"id": "door_left", "rect": left_rect, "open": False, "room": room_rect},
        {"id": "door_center", "rect": center_rect, "open": False, "room": room_rect},
    ]
    return doors, room_rect


def compose_world_boxes(base_boxes, doors):
    """기본 박스 + 닫힌 문을 합쳐 충돌/시야 계산용 박스 목록 생성"""
    combined = list(base_boxes)
    for door in doors:
        if door["open"]:
            continue
        rect = door["rect"]
        combined.append(
            create_box_entry(
                name=door["id"],
                left=rect.x,
                top=rect.y,
                width=rect.width,
                height=rect.height,
                color=st.COLOR_DOOR_CLOSED,
                image=None,
            )
        )
    return combined


def collect_room_enemy_keys(enemies, room_rect):
    """방 영역 안에 있는 적 키를 모아 잠금 해제 조건으로 사용"""
    keys = set()
    for enemy_key, enemy_obj in enemies.items():
        if room_rect.collidepoint(enemy_obj["pos_x"], enemy_obj["pos_y"]):
            keys.add(enemy_key)
    return keys


def build_box_rects(boxes):
    """박스 충돌 판정용 Rect 캐시를 생성"""
    return [pygame.Rect(*box["rect"]) for box in boxes]


def collides_with_any_box(x, y, radius, box_rects):
    """원 좌표가 박스들 중 하나와 충돌하는지 판정"""
    for box_rect in box_rects:
        if circle_rect_collide(x, y, radius, box_rect):
            return True
    return False


def find_valid_enemy_spawn(x, y, radius, screen_width, screen_height, box_rects):
    """벽과 겹치지 않는 안전한 적 스폰 좌표를 반환"""
    def clamp(value, low, high):
        return max(low, min(value, high))

    # 먼저 화면 내부로 보정
    x = clamp(float(x), radius, screen_width - radius)
    y = clamp(float(y), radius, screen_height - radius)

    if not collides_with_any_box(x, y, radius, box_rects):
        return x, y

    # 근거리 탐색: 원본 위치 주변에서 가장 먼저 가능한 위치를 찾는다.
    step = max(8, radius)
    offsets = [
        (1, 0), (-1, 0), (0, 1), (0, -1),
        (1, 1), (1, -1), (-1, 1), (-1, -1),
    ]
    for dist in range(step, 301, step):
        for ox, oy in offsets:
            nx = clamp(x + ox * dist, radius, screen_width - radius)
            ny = clamp(y + oy * dist, radius, screen_height - radius)
            if not collides_with_any_box(nx, ny, radius, box_rects):
                return nx, ny

    # 최종 fallback: 랜덤 샘플로 안전 위치를 찾는다.
    for _ in range(120):
        nx = random.randint(radius, screen_width - radius)
        ny = random.randint(radius, screen_height - radius)
        if not collides_with_any_box(nx, ny, radius, box_rects):
            return float(nx), float(ny)

    # 최악의 경우 원본(보정) 좌표 반환
    return x, y


def build_map_enemies(map_enemies, screen_width, screen_height, box_rects):
    """맵 JSON 적 데이터를 런타임 enemy 상태로 변환"""
    legacy_type_map = {
        "random_walker": "pistol",
        "chaser": "ar",
    }
    type_colors = {
        "pistol": (255, 230, 80),
        "shotgun": (255, 140, 0),
        "smg": (180, 255, 180),
        "ar": (120, 255, 220),
        "sniper": (120, 220, 255),
    }
    enemies_from_map = {}
    for idx, data in enumerate(map_enemies):
        enemy_type = data.get("type", data.get("name", "pistol"))
        enemy_type = legacy_type_map.get(enemy_type, enemy_type)
        radius = int(data.get("radius", 12))
        enemy_pos_x = float(data.get("x", screen_width // 2))
        enemy_pos_y = float(data.get("y", screen_height // 2))
        enemy_pos_x, enemy_pos_y = find_valid_enemy_spawn(
            enemy_pos_x,
            enemy_pos_y,
            radius,
            screen_width,
            screen_height,
            box_rects,
        )
        max_hp = int(data.get("max_hp", data.get("hp", 100)))
        enemy_state = {
            "pos_x": enemy_pos_x,
            "pos_y": enemy_pos_y,
            "angle": random.uniform(0, 2 * math.pi),
            "data": {
                "name": legacy_type_map.get(data.get("name", enemy_type), data.get("name", enemy_type)),
                "color": tuple(data.get("color", type_colors.get(enemy_type, (255, 255, 0)))),
                "image": data.get("image", None),
                "type": enemy_type,
                "speed": float(data.get("speed", 2.0)),
                "radius": radius,
            },
            "hp": int(data.get("hp", max_hp)),
            "max_hp": max_hp,
            "last_seen_player": None,
            "chase_timer": 0,
        }
        enemies_from_map[f"map_enemy_{idx}"] = enemy_state
    return enemies_from_map


def load_map_config(map_file_path, screen_width, screen_height):
    """맵 JSON 파일을 읽어 BOXES/스폰/적 데이터를 반환"""
    if not os.path.exists(map_file_path):
        return None

    try:
        # PowerShell에서 저장된 UTF-8 BOM 파일도 안전하게 읽는다.
        with open(map_file_path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except Exception as ex:
        print(f"[Map Load Failed] {map_file_path}: {ex}")
        return None

    boxes = []
    for i, item in enumerate(data.get("boxes", [])):
        left = int(item.get("x", 0))
        top = int(item.get("y", 0))
        width = int(item.get("w", 0))
        height = int(item.get("h", 0))
        if width <= 0 or height <= 0:
            continue
        boxes.append({
            "name": item.get("name", f"map_box_{i}"),
            "width": width,
            "height": height,
            "left": left,
            "top": top,
            "rect": (left, top, width, height),
            "segments": build_box_segments(left, top, width, height),
            "image": item.get("image"),
            "color": tuple(item.get("color", (0, 128, 255))),
        })

    spawn = data.get("player_spawn")
    spawn_pos = None
    if isinstance(spawn, dict):
        sx = int(spawn.get("x", 0))
        sy = int(spawn.get("y", 0))
        spawn_pos = (sx, sy)

    box_rects = build_box_rects(boxes)
    map_enemies = build_map_enemies(data.get("enemies", []), screen_width, screen_height, box_rects)

    return {
        "boxes": boxes,
        "spawn": spawn_pos,
        "enemies": map_enemies,
    }


def load_runtime_world_state(map_file_path, screen_width, screen_height, default_spawn):
    """맵 파일 또는 기본 오브젝트 설정으로 런타임 월드 상태를 구성"""
    map_config = load_map_config(map_file_path, screen_width, screen_height)
    if map_config is not None:
        boxes = map_config["boxes"]
        visibility_segments = build_visibility_segments(boxes)
        box_rects = build_box_rects(boxes)
        if map_config["spawn"] is not None:
            spawn = map_config["spawn"]
        else:
            spawn = default_spawn
        enemies = map_config["enemies"]
        return {
            "source": "map",
            "boxes": boxes,
            "box_rects": box_rects,
            "visibility_segments": visibility_segments,
            "spawn": spawn,
            "enemies": enemies,
        }

    boxes = get_all_boxes_config(screen_width, screen_height)
    visibility_segments = build_visibility_segments(boxes)
    box_rects = build_box_rects(boxes)
    enemies = initialize_enemies(boxes, screen_width, screen_height)
    return {
        "source": "default",
        "boxes": boxes,
        "box_rects": box_rects,
        "visibility_segments": visibility_segments,
        "spawn": default_spawn,
        "enemies": enemies,
    }


def get_edge_spawn(entry_side):
    """다른 맵에서 진입했을 때 방향별 시작 위치를 반환"""
    mid_x = SCREEN_WIDTH // 2
    mid_y = SCREEN_HEIGHT // 2
    # 닫힌 문 두께를 넘어선 위치에서 시작해야 문 박스와 겹치지 않는다.
    margin = DOOR_THICKNESS + PLAYER_RADIUS + 8
    if entry_side == "left":
        return (margin, mid_y)
    if entry_side == "right":
        return (SCREEN_WIDTH - margin, mid_y)
    if entry_side == "top":
        return (mid_x, margin)
    if entry_side == "bottom":
        return (mid_x, SCREEN_HEIGHT - margin)
    return None


def is_door_open_for_side(side, doors):
    """해당 방향 문이 열린 상태인지 확인"""
    door_id = SIDE_TO_DOOR_ID[side]
    for door in doors:
        if door["id"] == door_id:
            return door.get("open", False)
    return False


def get_neighbor_position(map_file_path, side):
    """현재 맵의 격자 좌표에서 방향별 이웃 좌표를 계산"""
    base_x, base_y = MAP_POSITIONS.setdefault(map_file_path, (0, 0))
    delta_x, delta_y = SIDE_DELTAS[side]
    return (base_x + delta_x, base_y + delta_y)


def register_map_at_position(map_file_path, position):
    """맵 파일을 월드 격자 좌표에 등록"""
    MAP_POSITIONS[map_file_path] = position
    POSITION_TO_MAP[position] = map_file_path


def ensure_map_has_position(map_file_path):
    """좌표가 없는 맵에 디버그용 고유 좌표를 부여"""
    if map_file_path in MAP_POSITIONS:
        return MAP_POSITIONS[map_file_path]

    candidate_x = 0
    while (candidate_x, 0) in POSITION_TO_MAP:
        candidate_x += 1
    register_map_at_position(map_file_path, (candidate_x, 0))
    return MAP_POSITIONS[map_file_path]


def connect_maps(from_map_file, exit_side, to_map_file):
    """양방향 맵 연결을 일관되게 기록"""
    MAP_CONNECTIONS.setdefault(from_map_file, {})[exit_side] = to_map_file
    reverse_side = OPPOSITE_SIDE[exit_side]
    MAP_CONNECTIONS.setdefault(to_map_file, {})[reverse_side] = from_map_file

    target_position = get_neighbor_position(from_map_file, exit_side)
    register_map_at_position(to_map_file, target_position)


def choose_connected_map(current_map_file, exit_side):
    """현재 맵 + 출구 방향으로 연결될 맵을 좌표 일관성 있게 반환"""
    edge_map = MAP_CONNECTIONS.setdefault(current_map_file, {})
    if exit_side in edge_map:
        return edge_map[exit_side], True

    target_position = get_neighbor_position(current_map_file, exit_side)
    mapped_target = POSITION_TO_MAP.get(target_position)
    if mapped_target is not None:
        connect_maps(current_map_file, exit_side, mapped_target)
        return mapped_target, True

    # 아직 방문하지 않은 normal 맵을 우선 연결
    candidates = [
        m for m in MAP_CYCLE_FILES
        if m not in VISITED_MAPS and m != current_map_file and m not in MAP_POSITIONS
    ]
    if not candidates:
        candidates = [m for m in MAP_CYCLE_FILES if m != current_map_file and m not in MAP_POSITIONS]
    if not candidates:
        candidates = [current_map_file]

    target = random.choice(candidates)
    connect_maps(current_map_file, exit_side, target)
    return target, False


def build_runtime_from_map(map_file_path, default_spawn, entry_side=None):
    """맵 파일을 로드하고 런타임 상태를 반환"""
    world_state = load_runtime_world_state(map_file_path, SCREEN_WIDTH, SCREEN_HEIGHT, default_spawn)
    base_boxes = world_state["boxes"]
    doors, room_rect = create_room_doors(SCREEN_WIDTH, SCREEN_HEIGHT)
    spawn = world_state["spawn"]
    if entry_side is not None:
        edge_spawn = get_edge_spawn(entry_side)
        if edge_spawn is not None:
            spawn = edge_spawn
    enemies_local = world_state["enemies"]
    if map_file_path in CLEARED_MAPS:
        enemies_local = {}
    room_enemy_keys = collect_room_enemy_keys(enemies_local, room_rect)
    boxes = compose_world_boxes(base_boxes, doors)
    box_rects = build_box_rects(boxes)
    visibility_segments = build_visibility_segments(boxes)

    if map_file_path in CLEARED_MAPS:
        for door in doors:
            door["open"] = True
        room_enemy_keys = set()
        boxes = compose_world_boxes(base_boxes, doors)
        box_rects = build_box_rects(boxes)
        visibility_segments = build_visibility_segments(boxes)

    spawn = find_valid_enemy_spawn(
        spawn[0],
        spawn[1],
        PLAYER_RADIUS,
        SCREEN_WIDTH,
        SCREEN_HEIGHT,
        box_rects,
    )

    return {
        "source": world_state["source"],
        "base_boxes": base_boxes,
        "doors": doors,
        "room_rect": room_rect,
        "spawn": spawn,
        "enemies": enemies_local,
        "room_enemy_keys": room_enemy_keys,
        "boxes": boxes,
        "box_rects": box_rects,
        "visibility_segments": visibility_segments,
    }


def apply_runtime_state(runtime):
    """런타임 월드 상태 딕셔너리를 현재 전역 상태에 반영"""
    global BASE_BOXES, DOORS, ROOM_RECT, pos_x, pos_y, enemies, ROOM_ENEMY_KEYS, BOXES, BOX_RECTS, VISIBILITY_SEGMENTS

    BASE_BOXES = runtime["base_boxes"]
    DOORS = runtime["doors"]
    ROOM_RECT = runtime["room_rect"]
    pos_x, pos_y = runtime["spawn"]
    enemies = runtime["enemies"]
    ROOM_ENEMY_KEYS = runtime["room_enemy_keys"]
    BOXES = runtime["boxes"]
    BOX_RECTS = runtime["box_rects"]
    VISIBILITY_SEGMENTS = runtime["visibility_segments"]


def clear_current_map_state():
    """현재 맵을 클리어 상태로 반영"""
    enemies.clear()
    ROOM_ENEMY_KEYS.clear()
    CLEARED_MAPS.add(CURRENT_MAP_FILE)
    for door in DOORS:
        door["open"] = True

    refreshed_boxes = compose_world_boxes(BASE_BOXES, DOORS)
    refreshed_box_rects = build_box_rects(refreshed_boxes)
    refreshed_visibility_segments = build_visibility_segments(refreshed_boxes)

    return refreshed_boxes, refreshed_box_rects, refreshed_visibility_segments


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
    angle_eps = st.RAY_ANGLE_EPSILON
    angles = set()
    for seg in segments:
        for vx, vy in seg:
            base = math.atan2(vy - py, vx - px)
            angles.update((base - angle_eps, base, base + angle_eps))

    points = []
    for angle in sorted(angles):
        ray_dir = (math.cos(angle) * RAY_LENGTH, math.sin(angle) * RAY_LENGTH)
        ray_origin = (
            px + math.cos(angle) * RAY_ORIGIN_BIAS,
            py + math.sin(angle) * RAY_ORIGIN_BIAS,
        )
        closest = None
        for seg in segments:
            hit = line_intersection(ray_origin, ray_dir, seg[0], seg[1])
            if hit and (closest is None or hit[2] < closest[2]):
                closest = hit
        if closest:
            points.append((angle, closest[0], closest[1]))

    # 바로 인접한 중복 점을 제거해 면 찢김을 줄인다.
    output = []
    for _, x, y in points:
        if not output:
            output.append((x, y))
            continue
        px0, py0 = output[-1]
        if (x - px0) * (x - px0) + (y - py0) * (y - py0) > 0.01:
            output.append((x, y))

    return output

# 플레이어 초기 위치 설정
initial_spawn = (
    objects.OBJECTS["player"].get("start_x", 0),
    objects.OBJECTS["player"].get("start_y", 0),
)
runtime = build_runtime_from_map(MAP_FILE, initial_spawn)
apply_runtime_state(runtime)
if runtime["source"] == "map":
    print(f"[Map Loaded] {MAP_FILE}")
start_debug_window()

# 총알 리스트
bullets = []

# 총기 상태
current_gun_name = gun.CURRENT_GUN
gun_cfg = GUNS[current_gun_name]
ammo = gun_cfg["magazine_size"]        # 현재 탄약
reload_timer = 0                       # 재장전 카운트다운 (0 = 완료)
fire_timer = 0                         # 발사 딜레이 카운트다운

clock = pygame.time.Clock()
while True:
    clock.tick(TARGET_FPS)
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            sys.exit()

        # R 키 외 별도: F 키로 수동 재장전
        if event.type == pygame.KEYDOWN and event.key == pygame.K_f:
            if ammo < gun_cfg["magazine_size"] and reload_timer == 0:
                reload_timer = gun_cfg["reload_time"]

        # 반자동 총: 클릭 이벤트에서 발사
        if not gun_cfg["auto_fire"]:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if ammo > 0 and reload_timer == 0 and fire_timer == 0:
                    mx, my = pygame.mouse.get_pos()
                    dx = mx - pos_x
                    dy = my - pos_y
                    dist = math.sqrt(dx * dx + dy * dy)
                    if dist > 0:
                        bullets.extend(make_bullets(current_gun_name, pos_x, pos_y, dx / dist, dy / dist))
                        ammo -= 1
                        fire_timer = gun_cfg["fire_rate"]
                        if ammo == 0:
                            reload_timer = gun_cfg["reload_time"]

    while not DEBUG_COMMAND_QUEUE.empty():
        command_name, payload = DEBUG_COMMAND_QUEUE.get()

        if command_name == "kill_all":
            BOXES, BOX_RECTS, VISIBILITY_SEGMENTS = clear_current_map_state()
            print("[Debug] kill_all executed")
        elif command_name == "teleport":
            target_x, target_y = payload
            pos_x, pos_y = find_valid_enemy_spawn(
                target_x,
                target_y,
                PLAYER_RADIUS,
                SCREEN_WIDTH,
                SCREEN_HEIGHT,
                BOX_RECTS,
            )
            print(f"[Debug] teleport -> ({int(pos_x)}, {int(pos_y)})")
        elif command_name == "switch_gun" and payload in GUNS:
            current_gun_name = payload
            gun.CURRENT_GUN = current_gun_name
            gun_cfg = GUNS[current_gun_name]
            ammo = gun_cfg["magazine_size"]
            reload_timer = 0
            fire_timer = 0
            bullets = []
            print(f"[Debug] switch_gun -> {current_gun_name}")

    key_event = pygame.key.get_pressed()

    # 자동 연사 총: 매 프레임 버튼 상태 체크
    if gun_cfg["auto_fire"] and pygame.mouse.get_pressed()[0]:
        if ammo > 0 and reload_timer == 0 and fire_timer == 0:
            mx, my = pygame.mouse.get_pos()
            dx = mx - pos_x
            dy = my - pos_y
            dist = math.sqrt(dx * dx + dy * dy)
            if dist > 0:
                bullets.extend(make_bullets(current_gun_name, pos_x, pos_y, dx / dist, dy / dist))
                ammo -= 1
                fire_timer = gun_cfg["fire_rate"]
                if ammo == 0:
                    reload_timer = gun_cfg["reload_time"]

    # 타이머 감소
    if fire_timer > 0:
        fire_timer -= 1
    if reload_timer > 0:
        reload_timer -= 1
        if reload_timer == 0:
            ammo = gun_cfg["magazine_size"]
    speed = PLAYER_SPEED

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
    if not collides_with_any_box(new_x, new_y, PLAYER_RADIUS, BOX_RECTS):
        pos_x = new_x

    # y축 이동 & 충돌 체크
    new_x = pos_x
    new_y = pos_y + move_y
    if not collides_with_any_box(new_x, new_y, PLAYER_RADIUS, BOX_RECTS):
        pos_y = new_y

    # 화면 경계 제한
    if pos_x < PLAYER_RADIUS:
        pos_x = PLAYER_RADIUS
    if pos_x > SCREEN_WIDTH - PLAYER_RADIUS:
        pos_x = SCREEN_WIDTH - PLAYER_RADIUS
    if pos_y < PLAYER_RADIUS:
        pos_y = PLAYER_RADIUS
    if pos_y > SCREEN_HEIGHT - PLAYER_RADIUS:
        pos_y = SCREEN_HEIGHT - PLAYER_RADIUS

    # 벽(화면 끝) 접촉 시 방향별 맵 연결 이동
    transition_side = None
    if move_x < 0 and pos_x <= PLAYER_RADIUS:
        transition_side = "left"
    elif move_x > 0 and pos_x >= SCREEN_WIDTH - PLAYER_RADIUS:
        transition_side = "right"
    elif move_y < 0 and pos_y <= PLAYER_RADIUS:
        transition_side = "top"
    elif move_y > 0 and pos_y >= SCREEN_HEIGHT - PLAYER_RADIUS:
        transition_side = "bottom"

    if transition_side and is_door_open_for_side(transition_side, DOORS):
        target_map, was_existing = choose_connected_map(CURRENT_MAP_FILE, transition_side)
        entry_side = OPPOSITE_SIDE[transition_side]
        transition_spawn = (
            objects.OBJECTS["player"].get("start_x", 200),
            objects.OBJECTS["player"].get("start_y", 200),
        )
        runtime = build_runtime_from_map(target_map, transition_spawn, entry_side)

        MAP_FILE = target_map
        CURRENT_MAP_FILE = target_map
        VISITED_MAPS.add(target_map)

        apply_runtime_state(runtime)
        bullets = []

        if runtime["source"] == "map":
            if was_existing:
                print(f"[Map Move] existing link -> {MAP_FILE}")
            else:
                print(f"[Map Move] new link -> {MAP_FILE}")
        else:
            print(f"[Map Move Failed] {MAP_FILE} not found, fallback map loaded")
        continue

    # 가시영역 계산
    visible_poly = get_visibility_polygon((pos_x, pos_y), VISIBILITY_SEGMENTS)

    # 모든 적 이동 로직
    update_enemy_ai(
        enemies,
        pos_x,
        pos_y,
        visible_poly,
        BOXES,
        SCREEN_WIDTH,
        SCREEN_HEIGHT,
        screen.point_in_polygon,
        BOX_RECTS,
    )

    # 총알 이동 및 충돌 처리
    next_bullets = []
    dead_enemy_keys = set()
    for bullet in bullets:
        bullet["x"] += bullet["dx"]
        bullet["y"] += bullet["dy"]
        bx, by = bullet["x"], bullet["y"]
        # 화면 밖 제거
        if bx < 0 or bx > SCREEN_WIDTH or by < 0 or by > SCREEN_HEIGHT:
            continue
        # 수명 처리
        if bullet["lifetime"] != -1:
            bullet["lifetime"] -= 1
            if bullet["lifetime"] <= 0:
                continue
        # 벽 충돌 (관통 총알은 통과)
        if not bullet["penetrate"]:
            wall_hit = False
            for box_rect in BOX_RECTS:
                if circle_rect_collide(bx, by, bullet["radius"], box_rect):
                    wall_hit = True
                    break
            if wall_hit:
                continue

        # 적 충돌: 총알 데미지만큼 체력 감소
        enemy_hit = False
        for enemy_key, enemy_obj in enemies.items():
            if enemy_key in dead_enemy_keys:
                continue
            ex = enemy_obj["pos_x"]
            ey = enemy_obj["pos_y"]
            er = enemy_obj["data"]["radius"]
            dx = bx - ex
            dy = by - ey
            hit_dist = bullet["radius"] + er
            if dx * dx + dy * dy <= hit_dist * hit_dist:
                damage = bullet.get("damage", 0)
                current_hp = enemy_obj.get("hp", enemy_obj.get("max_hp", 100))
                enemy_obj["hp"] = current_hp - damage
                enemy_hit = True
                if enemy_obj["hp"] <= 0:
                    dead_enemy_keys.add(enemy_key)
                # 비관통 총알은 첫 충돌 시 소멸
                if not bullet["penetrate"]:
                    break

        if enemy_hit and not bullet["penetrate"]:
            continue

        next_bullets.append(bullet)
    bullets = next_bullets

    # 체력이 0 이하인 적 제거
    for dead_key in dead_enemy_keys:
        if dead_key in enemies:
            del enemies[dead_key]

    # 문 해제 조건:
    # 1) 방 내부 적 목록이 있으면 그 적들이 전멸했을 때
    # 2) 방 내부 적 목록이 비어 있으면 전체 적이 전멸했을 때
    if any(not door["open"] for door in DOORS):
        if ROOM_ENEMY_KEYS:
            should_open_doors = not any(enemy_key in enemies for enemy_key in ROOM_ENEMY_KEYS)
            open_reason = "방 안의 적을 모두 처치"
        else:
            should_open_doors = len(enemies) == 0
            open_reason = "전체 적을 모두 처치"

        if should_open_doors:
            for door in DOORS:
                door["open"] = True
            CLEARED_MAPS.add(CURRENT_MAP_FILE)
            ROOM_ENEMY_KEYS = set()
            BOXES = compose_world_boxes(BASE_BOXES, DOORS)
            BOX_RECTS = build_box_rects(BOXES)
            VISIBILITY_SEGMENTS = build_visibility_segments(BOXES)
            print(f"[Door Opened] {open_reason}하여 문이 열렸습니다")

    # 화면 렌더링
    mouse_pos = pygame.mouse.get_pos()
    screen.render_game_screen(
        screen_surface,
        visible_poly,
        BOXES,
        pos_x,
        pos_y,
        enemies,
        bullets,
        mouse_pos,
        font_small,
        SCREEN_WIDTH,
        SCREEN_HEIGHT,
        get_ray_screen_intersections,
        ammo,
        gun_cfg["magazine_size"],
        reload_timer,
        DOORS,
    )