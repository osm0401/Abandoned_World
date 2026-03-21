# objects.py
# 게임 오브젝트 설정을 모아두는 파일

# 게임 오브젝트 정의
OBJECTS = {
    "player": {
        "start_x": 0,   # 플레이어 시작 X 좌표
        "start_y": 0,   # 플레이어 시작 Y 좌표
    },
    "box": {
        "x": 100,       # 왼쪽 끝
        "x_end": 700,   # 오른쪽 끝 (x_end = 700이면 100~700)
        "y": 200,       # 위쪽 끝
        "y_end": 673,   # 아래쪽 끝
        "image": None,  # 이미지 경로 또는 None (색상 박스로 표시)
        "color": (0, 128, 255),  # (R, G, B)
    },
    "box2": {
        "x": 870,       # 왼쪽 끝
        "x_end": 1100,   # 오른쪽 끝 (x_end = 700이면 100~700)
        "y": 725,       # 위쪽 끝
        "y_end": 900,   # 아래쪽 끝
        "image": None,  # 이미지 경로 또는 None (색상 박스로 표시)
        "color": (0, 128, 255),  # (R, G, B)
    },
}

# 구버전 호환성 유지
BOX = OBJECTS["box"]

# 박스 세그먼트(선분) 정의 (로컬 좌표) - 동적 계산
def get_box_segments(box_width, box_height):
    """주어진 너비와 높이에 맞는 박스 테두리 선분들을 반환"""
    return [
        ((0, 0), (box_width, 0)),
        ((box_width, 0), (box_width, box_height)),
        ((box_width, box_height), (0, box_height)),
        ((0, box_height), (0, 0)),
    ]


_BOX_CONFIG_CACHE = {}

def get_all_boxes_config(screen_width, screen_height):
    """모든 박스 오브젝트의 설정을 반환 (캐시 사용으로 성능 최적화)"""
    key = (screen_width, screen_height)
    if key in _BOX_CONFIG_CACHE:
        return _BOX_CONFIG_CACHE[key]
    
    boxes = []
    for obj_name, obj_data in OBJECTS.items():
        if obj_name.startswith("box"):  # box로 시작하는 모든 오브젝트
            # x, y: 시작점 / x_end, y_end: 끝점
            box_left = obj_data.get("x")
            if box_left is None:
                box_left = (screen_width - (obj_data.get("x_end", 80) - 0)) // 2
            
            box_top = obj_data.get("y")
            if box_top is None:
                box_top = (screen_height - (obj_data.get("y_end", 80) - 0)) // 2
            
            # 너비/높이는 끝점에서 시작점을 뺀 값
            box_width = obj_data.get("x_end", box_left + 80) - box_left
            box_height = obj_data.get("y_end", box_top + 80) - box_top
            
            # 박스 세그먼트 생성 (동적 계산)
            box_segments = get_box_segments(box_width, box_height)
            world_segments = [
                ((box_left + x1, box_top + y1), (box_left + x2, box_top + y2))
                for (x1, y1), (x2, y2) in box_segments
            ]
            
            boxes.append({
                "name": obj_name,
                "width": box_width,
                "height": box_height,
                "left": box_left,
                "top": box_top,
                "rect": (box_left, box_top, box_width, box_height),
                "segments": world_segments,
                "image": obj_data.get("image"),
                "color": obj_data.get("color", (0, 128, 255)),
            })
    
    _BOX_CONFIG_CACHE[key] = boxes
    return boxes

# 구버전 호환성 유지
def get_box_config(screen_width, screen_height):
    """첫 번째 박스 오브젝트의 설정을 반환 (구버전 호환용)"""
    boxes = get_all_boxes_config(screen_width, screen_height)
    return boxes[0] if boxes else None

# 추후 다른 오브젝트나 미션 속성 추가 가능
# ENEMY: 적 오브젝트 정의 (위에 정의됨)
# ITEM: 아이템 오브젝트 정의
# GOAL: 목표 오브젝트 정의
# PLAYER: 플레이어 설정 등
