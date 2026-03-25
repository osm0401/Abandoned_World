import json
import os
import sys
from datetime import datetime

import pygame


WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 960
CANVAS_WIDTH = 1000
PANEL_X = CANVAS_WIDTH
GRID_SIZE = 40
FPS = 60

BG_COLOR = (30, 32, 38)
GRID_COLOR = (52, 55, 64)
PANEL_COLOR = (24, 26, 32)
TEXT_COLOR = (235, 235, 235)
HINT_COLOR = (170, 170, 170)

TOOL_BOX = "box"
TOOL_DOOR = "door"
TOOL_ENEMY = "enemy"
TOOL_SPAWN = "spawn"
TOOL_ERASE = "erase"

TOOLS = [TOOL_BOX, TOOL_DOOR, TOOL_ENEMY, TOOL_SPAWN, TOOL_ERASE]

TOOL_COLORS = {
    TOOL_BOX: (70, 150, 255),
    TOOL_DOOR: (100, 220, 120),
    TOOL_ENEMY: (240, 80, 80),
    TOOL_SPAWN: (255, 220, 70),
}

ENEMY_TYPES = ["sniper", "shotgun", "smg", "ar", "pistol"]


def clamp(value, minimum, maximum):
    return max(minimum, min(value, maximum))


def snap(value, size):
    return int(round(value / size) * size)


def normalize_rect(a, b):
    x1, y1 = a
    x2, y2 = b
    left = min(x1, x2)
    top = min(y1, y2)
    width = abs(x2 - x1)
    height = abs(y2 - y1)
    return pygame.Rect(left, top, width, height)


def rect_to_dict(rect):
    return {"x": int(rect.x), "y": int(rect.y), "w": int(rect.w), "h": int(rect.h)}


def point_in_canvas(pos):
    x, y = pos
    return 0 <= x < CANVAS_WIDTH and 0 <= y < WINDOW_HEIGHT


def draw_grid(surface, grid_size):
    for x in range(0, CANVAS_WIDTH, grid_size):
        pygame.draw.line(surface, GRID_COLOR, (x, 0), (x, WINDOW_HEIGHT), 1)
    for y in range(0, WINDOW_HEIGHT, grid_size):
        pygame.draw.line(surface, GRID_COLOR, (0, y), (CANVAS_WIDTH, y), 1)


def draw_cross(surface, pos, color, size=12, thickness=2):
    x, y = pos
    pygame.draw.line(surface, color, (x - size, y), (x + size, y), thickness)
    pygame.draw.line(surface, color, (x, y - size), (x, y + size), thickness)


def remove_at_position(map_data, pos):
    x, y = pos

    # Enemy first (easier single-click erase)
    for i in range(len(map_data["enemies"]) - 1, -1, -1):
        e = map_data["enemies"][i]
        dx = x - e["x"]
        dy = y - e["y"]
        radius = e.get("radius", 12)
        if dx * dx + dy * dy <= radius * radius:
            map_data["enemies"].pop(i)
            return True

    # Spawn
    spawn = map_data.get("player_spawn")
    if spawn is not None:
        if abs(x - spawn["x"]) <= 10 and abs(y - spawn["y"]) <= 10:
            map_data["player_spawn"] = None
            return True

    # Door
    for i in range(len(map_data["doors"]) - 1, -1, -1):
        d = map_data["doors"][i]
        if pygame.Rect(d["x"], d["y"], d["w"], d["h"]).collidepoint(pos):
            map_data["doors"].pop(i)
            return True

    # Box
    for i in range(len(map_data["boxes"]) - 1, -1, -1):
        b = map_data["boxes"][i]
        if pygame.Rect(b["x"], b["y"], b["w"], b["h"]).collidepoint(pos):
            map_data["boxes"].pop(i)
            return True

    return False


def build_json_payload(map_data, map_name):
    return {
        "meta": {
            "name": map_name,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "width": CANVAS_WIDTH,
            "height": WINDOW_HEIGHT,
            "grid_size": GRID_SIZE,
        },
        "player_spawn": map_data.get("player_spawn"),
        "boxes": map_data["boxes"],
        "doors": map_data["doors"],
        "enemies": map_data["enemies"],
        "props": map_data["props"],
    }


def save_map(map_data, map_name):
    safe_name = "".join(ch for ch in map_name if ch.isalnum() or ch in ("_", "-"))
    safe_name = safe_name or "untitled_map"
    file_name = f"{safe_name}.json"

    payload = build_json_payload(map_data, safe_name)
    with open(file_name, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return os.path.abspath(file_name)


def main():
    pygame.init()
    pygame.display.set_caption("Map Editor (Standalone)")
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    clock = pygame.time.Clock()

    font = pygame.font.Font(None, 24)
    small_font = pygame.font.Font(None, 20)

    map_data = {
        "player_spawn": None,
        "boxes": [],
        "doors": [],
        "enemies": [],
        "props": [],
    }

    map_name = "my_map"
    current_tool = TOOL_BOX
    current_enemy_type = ENEMY_TYPES[0]
    show_grid = True

    dragging = False
    drag_start = (0, 0)
    drag_end = (0, 0)

    typing_map_name = False
    status_text = "Ready"

    running = True
    while running:
        dt = clock.tick(FPS)
        _ = dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if typing_map_name:
                    if event.key == pygame.K_RETURN:
                        typing_map_name = False
                        status_text = f"Map name set to: {map_name}"
                    elif event.key == pygame.K_ESCAPE:
                        typing_map_name = False
                    elif event.key == pygame.K_BACKSPACE:
                        map_name = map_name[:-1]
                    else:
                        if len(map_name) < 32 and event.unicode.isprintable():
                            map_name += event.unicode
                    continue

                if event.key == pygame.K_1:
                    current_tool = TOOL_BOX
                elif event.key == pygame.K_2:
                    current_tool = TOOL_DOOR
                elif event.key == pygame.K_3:
                    current_tool = TOOL_ENEMY
                elif event.key == pygame.K_4:
                    current_tool = TOOL_SPAWN
                elif event.key == pygame.K_5:
                    current_tool = TOOL_ERASE
                elif event.key == pygame.K_g:
                    show_grid = not show_grid
                elif event.key == pygame.K_n:
                    typing_map_name = True
                elif event.key == pygame.K_e:
                    idx = ENEMY_TYPES.index(current_enemy_type)
                    current_enemy_type = ENEMY_TYPES[(idx + 1) % len(ENEMY_TYPES)]
                    status_text = f"Enemy type: {current_enemy_type}"
                elif event.key == pygame.K_c:
                    map_data = {
                        "player_spawn": None,
                        "boxes": [],
                        "doors": [],
                        "enemies": [],
                        "props": [],
                    }
                    status_text = "Canvas cleared"
                elif event.key == pygame.K_s:
                    try:
                        saved_path = save_map(map_data, map_name)
                        status_text = f"Saved: {saved_path}"
                    except Exception as ex:
                        status_text = f"Save failed: {ex}"
                elif event.key == pygame.K_ESCAPE:
                    running = False

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if not point_in_canvas(event.pos):
                    continue

                x, y = event.pos
                x = clamp(snap(x, GRID_SIZE), 0, CANVAS_WIDTH - GRID_SIZE)
                y = clamp(snap(y, GRID_SIZE), 0, WINDOW_HEIGHT - GRID_SIZE)

                if current_tool in (TOOL_BOX, TOOL_DOOR):
                    dragging = True
                    drag_start = (x, y)
                    drag_end = (x, y)
                elif current_tool == TOOL_ENEMY:
                    map_data["enemies"].append(
                        {
                            "type": current_enemy_type,
                            "x": x,
                            "y": y,
                            "radius": 12,
                            "speed": 2.0,
                            "hp": 100,
                        }
                    )
                elif current_tool == TOOL_SPAWN:
                    map_data["player_spawn"] = {"x": x, "y": y}
                elif current_tool == TOOL_ERASE:
                    if remove_at_position(map_data, (x, y)):
                        status_text = "Deleted object"
                    else:
                        status_text = "Nothing to delete"

            elif event.type == pygame.MOUSEMOTION:
                if dragging:
                    x, y = event.pos
                    x = clamp(snap(x, GRID_SIZE), 0, CANVAS_WIDTH - GRID_SIZE)
                    y = clamp(snap(y, GRID_SIZE), 0, WINDOW_HEIGHT - GRID_SIZE)
                    drag_end = (x, y)

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                if dragging:
                    dragging = False
                    rect = normalize_rect(drag_start, drag_end)
                    if rect.w >= GRID_SIZE and rect.h >= GRID_SIZE:
                        if current_tool == TOOL_BOX:
                            item = rect_to_dict(rect)
                            item.update({"color": [70, 150, 255], "image": None})
                            map_data["boxes"].append(item)
                        elif current_tool == TOOL_DOOR:
                            item = rect_to_dict(rect)
                            item.update({"locked": False, "target_map": ""})
                            map_data["doors"].append(item)
                    else:
                        status_text = "Rect too small"

        screen.fill(BG_COLOR)

        # Canvas
        canvas = pygame.Rect(0, 0, CANVAS_WIDTH, WINDOW_HEIGHT)
        pygame.draw.rect(screen, BG_COLOR, canvas)
        if show_grid:
            draw_grid(screen, GRID_SIZE)

        # Draw boxes
        for b in map_data["boxes"]:
            r = pygame.Rect(b["x"], b["y"], b["w"], b["h"])
            pygame.draw.rect(screen, TOOL_COLORS[TOOL_BOX], r, 0)
            pygame.draw.rect(screen, (20, 20, 20), r, 2)

        # Draw doors
        for d in map_data["doors"]:
            r = pygame.Rect(d["x"], d["y"], d["w"], d["h"])
            pygame.draw.rect(screen, TOOL_COLORS[TOOL_DOOR], r, 0)
            pygame.draw.rect(screen, (20, 20, 20), r, 2)

        # Draw enemies
        for e in map_data["enemies"]:
            pygame.draw.circle(screen, TOOL_COLORS[TOOL_ENEMY], (e["x"], e["y"]), e.get("radius", 12))
            t = small_font.render(e["type"], True, (255, 255, 255))
            screen.blit(t, (e["x"] + 10, e["y"] - 8))

        # Draw spawn
        spawn = map_data.get("player_spawn")
        if spawn:
            draw_cross(screen, (spawn["x"], spawn["y"]), TOOL_COLORS[TOOL_SPAWN], size=14, thickness=3)
            t = small_font.render("SPAWN", True, TOOL_COLORS[TOOL_SPAWN])
            screen.blit(t, (spawn["x"] + 12, spawn["y"] - 10))

        # Drag preview
        if dragging and current_tool in (TOOL_BOX, TOOL_DOOR):
            preview_rect = normalize_rect(drag_start, drag_end)
            color = TOOL_COLORS[current_tool]
            pygame.draw.rect(screen, color, preview_rect, 2)

        # Side panel
        panel = pygame.Rect(PANEL_X, 0, WINDOW_WIDTH - PANEL_X, WINDOW_HEIGHT)
        pygame.draw.rect(screen, PANEL_COLOR, panel)
        pygame.draw.line(screen, (65, 68, 78), (PANEL_X, 0), (PANEL_X, WINDOW_HEIGHT), 2)

        y = 16
        def text_line(message, color=TEXT_COLOR, inc=24):
            nonlocal y
            surf = font.render(message, True, color)
            screen.blit(surf, (PANEL_X + 12, y))
            y += inc

        text_line("MAP EDITOR", (255, 255, 255), 30)
        text_line(f"Map Name: {map_name}")
        if typing_map_name:
            text_line("Typing map name...", (255, 210, 80))

        text_line(f"Tool: {current_tool}", TOOL_COLORS.get(current_tool, TEXT_COLOR), 30)
        text_line(f"Enemy Type: {current_enemy_type}")
        text_line(f"Grid: {'ON' if show_grid else 'OFF'}")

        y += 10
        text_line("Objects", (220, 220, 220))
        text_line(f"Boxes: {len(map_data['boxes'])}", HINT_COLOR)
        text_line(f"Doors: {len(map_data['doors'])}", HINT_COLOR)
        text_line(f"Enemies: {len(map_data['enemies'])}", HINT_COLOR)
        text_line(f"Spawn: {'Yes' if map_data['player_spawn'] else 'No'}", HINT_COLOR)

        y += 10
        text_line("Controls", (220, 220, 220))
        text_line("1 Box / 2 Door / 3 Enemy", HINT_COLOR)
        text_line("4 Spawn / 5 Erase", HINT_COLOR)
        text_line("E Enemy Type", HINT_COLOR)
        text_line("N Rename Map", HINT_COLOR)
        text_line("S Save JSON", HINT_COLOR)
        text_line("C Clear / G Grid", HINT_COLOR)
        text_line("ESC Exit", HINT_COLOR)

        y = WINDOW_HEIGHT - 48
        status_surf = small_font.render(status_text, True, (255, 210, 120))
        screen.blit(status_surf, (PANEL_X + 12, y))

        pygame.display.flip()

    pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
