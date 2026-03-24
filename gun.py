# gun.py
# 총기 설정을 모아두는 파일
#
# ── 구조 설명 ──────────────────────────────────────────────────────
# 총_이름 {
#     image         : 총 이미지 경로 (None = 미사용)
#     job           : 사용 가능 직업 리스트  ["all"] 이면 전부 사용 가능
#     reload_time   : 재장전 시간 (프레임, 60 = 1초)
#     magazine_size : 탄창 크기 (한 번에 장전되는 총알 수)
#     fire_rate     : 발사 딜레이 (프레임, 낮을수록 연사 빠름)
#     recoil        : 반동 (방향에 추가되는 최대 각도 오차, 라디안)
#     auto_fire     : True = 좌클릭 유지 시 연사 / False = 반자동(클릭마다 1발)
#     pellet_count  : 한 번에 나가는 총알 수 (샷건용, 기본 1)
#     spread_angle  : 산탄 퍼짐 범위 (라디안, 샷건용)
#     총알_이름 {
#         name      : 총알 이름
#         speed     : 총알 이동 속도 (px/프레임)
#         image     : 총알 이미지 경로 (None = 색상 원으로 표시)
#         color     : 총알 색상 RGB (image 가 None 일 때 사용)
#         damage    : 적에게 주는 데미지
#         radius    : 총알 반지름 (px)
#         penetrate : True = 벽/적 관통 / False = 첫 충돌에 제거
#         lifetime  : 최대 생존 프레임 (-1 = 무제한, 60 = 1초)
#     }
# }
#
# 새 총을 추가하려면 GUNS 딕셔너리에 항목을 넣고
# CURRENT_GUN 을 원하는 총 이름으로 바꾸면 됩니다.
# ──────────────────────────────────────────────────────────────────

import math
import random
CURRENT_GUN = "smg"
GUNS = {
    "pistol": {
        "name"         : "pistol",
        "image"        : None,               # 총 이미지
        "job"          : ["all"],            # 사용 가능 직업
        "reload_time"  : 90,                 # 재장전 시간 (프레임)
        "magazine_size": 12,                 # 탄창 크기
        "fire_rate"    : 15,                 # 발사 딜레이 (프레임)
        "recoil"       : 0.04,               # 반동 (라디안)
        "auto_fire"    : False,              # 반자동
        "pellet_count" : 1,                  # 발사 총알 수
        "spread_angle" : 0.0,                # 산탄 퍼짐 없음
        "bullet": {
            "name"     : "pistol_bullet",    # 총알 이름
            "speed"    : 14,                 # 총알 속도
            "image"    : None,               # 총알 이미지
            "color"    : (255, 230, 80),     # 총알 색상 (노란색)
            "damage"   : 25,                 # 데미지
            "radius"   : 4,                  # 총알 반지름
            "penetrate": False,              # 관통 여부
            "lifetime" : 120,                # 최대 생존 프레임 (2초)
        },
    },

    "shotgun": {
        "name"         : "shotgun",
        "image"        : None,
        "job"          : ["all"],
        "reload_time"  : 150,                # 느린 재장전 (2.5초)
        "magazine_size": 6,
        "fire_rate"    : 40,                 # 느린 연사
        "recoil"       : 0.0,                # 산탄으로 처리하므로 반동 없음
        "auto_fire"    : False,
        "pellet_count" : 8,                  # 산탄 8발
        "spread_angle" : 0.35,               # 산탄 퍼짐 각도
        "bullet": {
            "name"     : "shotgun_pellet",
            "speed"    : 12,
            "image"    : None,
            "color"    : (255, 140, 0),      # 주황색
            "damage"   : 12,                 # 산탄 1알 데미지
            "radius"   : 3,
            "penetrate": False,
            "lifetime" : 50,                 # 짧은 사거리
        },
    },

    "smg": {
        "name"         : "smg",
        "image"        : None,
        "job"          : ["all"],
        "reload_time"  : 80,
        "magazine_size": 30,                 # 큰 탄창
        "fire_rate"    : 5,                  # 빠른 연사
        "recoil"       : 0.08,
        "auto_fire"    : True,               # 자동 연사
        "pellet_count" : 1,
        "spread_angle" : 0.0,
        "bullet": {
            "name"     : "smg_bullet",
            "speed"    : 16,
            "image"    : None,
            "color"    : (180, 255, 180),    # 연두색
            "damage"   : 12,
            "radius"   : 3,
            "penetrate": False,
            "lifetime" : 100,
        },
    },

    "sniper": {
        "name"         : "sniper",
        "image"        : None,
        "job"          : ["all"],
        "reload_time"  : 180,                # 느린 재장전 (3초)
        "magazine_size": 5,
        "fire_rate"    : 60,                 # 매우 느린 연사
        "recoil"       : 0.01,               # 반동 거의 없음
        "auto_fire"    : False,
        "pellet_count" : 1,
        "spread_angle" : 0.0,
        "bullet": {
            "name"     : "sniper_bullet",
            "speed"    : 28,                 # 매우 빠름
            "image"    : None,
            "color"    : (120, 220, 255),    # 하늘색
            "damage"   : 80,                 # 높은 데미지
            "radius"   : 3,
            "penetrate": True,               # 관통
            "lifetime" : -1,                 # 무제한 (화면 밖에서 제거)
        },
    },
}

# 현재 장착된 총 이름 (GUNS 키와 일치해야 함)



# ── 헬퍼 함수 ──────────────────────────────

def make_bullets(gun_name, origin_x, origin_y, dir_x, dir_y):
    """
    발사 방향(dir_x, dir_y)으로 총알 딕셔너리 리스트를 만들어 반환.
    산탄총처럼 여러 발을 쏘는 경우 여러 개를 반환한다.
    반동(recoil)도 자동 적용된다.
    """
    cfg = GUNS[gun_name]
    bullet_cfg = cfg["bullet"]
    recoil = cfg.get("recoil", 0)
    pellet_count = cfg.get("pellet_count", 1)
    spread = cfg.get("spread_angle", 0)
    base_angle = math.atan2(dir_y, dir_x)

    result = []
    for i in range(pellet_count):
        if pellet_count == 1:
            angle = base_angle + random.uniform(-recoil, recoil)
        else:
            offset = (i / (pellet_count - 1) - 0.5) * spread if pellet_count > 1 else 0
            angle = base_angle + offset + random.uniform(-recoil, recoil)

        result.append({
            "x"        : float(origin_x),
            "y"        : float(origin_y),
            "dx"       : math.cos(angle) * bullet_cfg["speed"],
            "dy"       : math.sin(angle) * bullet_cfg["speed"],
            "radius"   : bullet_cfg["radius"],
            "color"    : bullet_cfg["color"],
            "damage"   : bullet_cfg["damage"],
            "penetrate": bullet_cfg["penetrate"],
            "lifetime" : bullet_cfg["lifetime"],
            "image"    : bullet_cfg["image"],
        })
    return result
