#!/usr/bin/env python3
"""
Traffic Pattern Generators for Elevator Simulation
Generate JSON traffic files for different scenarios with scalable building sizes
From small (1 elevator, 3 floors, 10 people) to large (4 elevators, 12 floors, 200 people)
"""
import json
import math
import os.path
import random
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# 建筑规模配置
BUILDING_SCALES = {
    "small": {
        "floors": (3, 5),
        "elevators": (1, 2),
        "capacity": (6, 8),
        "max_people": (10, 40),
        "duration_range": (120, 240),
        "description": "小型建筑 - 1-2台电梯，3-5楼，10-40人",
    },
    "medium": {
        "floors": (6, 9),
        "elevators": (2, 3),
        "capacity": (8, 12),
        "max_people": (40, 120),
        "duration_range": (200, 400),
        "description": "中型建筑 - 2-3台电梯，6-9楼，40-120人",
    },
    "large": {
        "floors": (10, 12),
        "elevators": (3, 4),
        "capacity": (10, 15),
        "max_people": (120, 200),
        "duration_range": (300, 600),
        "description": "大型建筑 - 3-4台电梯，10-12楼，120-200人",
    },
}


def calculate_intensity_for_scale(base_intensity: float, floors: int, target_people: int, duration: int) -> float:
    """根据建筑规模计算合适的流量强度"""
    # 估算每tick平均产生的人数
    estimated_people_per_tick = base_intensity
    total_estimated = estimated_people_per_tick * duration

    if total_estimated <= 0:
        return base_intensity

    # 调整强度以达到目标人数
    adjustment_factor = target_people / total_estimated
    return min(1.0, base_intensity * adjustment_factor)


def limit_traffic_count(traffic: List[Dict[str, Any]], max_people: int) -> List[Dict[str, Any]]:
    """限制流量中的人数不超过最大值"""
    if len(traffic) <= max_people:
        return traffic

    # 按时间排序，优先保留早期的乘客
    traffic_sorted = sorted(traffic, key=lambda x: x["tick"])
    return traffic_sorted[:max_people]


def generate_up_peak_traffic(
    floors: int = 10, duration: int = 300, intensity: float = 0.6, max_people: int = 100, seed: int = 42
) -> List[Dict[str, Any]]:
    """生成上行高峰流量 - 主要从底层到高层"""
    random.seed(seed)
    traffic = []
    passenger_id = 1

    # 根据目标人数调整强度
    adjusted_intensity = calculate_intensity_for_scale(intensity, floors, max_people, duration)

    for tick in range(duration):
        # 根据时间调整强度 - 早期高峰
        time_factor = 1.0 + 0.5 * math.sin(tick * math.pi / duration)
        current_intensity = adjusted_intensity * time_factor

        if random.random() < current_intensity:
            # 针对小建筑调整比例 - 小建筑大厅使用更频繁
            lobby_ratio = 0.95 if floors <= 5 else 0.9

            if random.random() < lobby_ratio:
                origin = 0
                destination = random.randint(1, floors - 1)
            else:
                # 其他楼层间流量
                if floors > 2:
                    origin = random.randint(1, min(floors - 2, floors - 1))
                    destination = random.randint(origin + 1, floors - 1)
                else:
                    origin = 0
                    destination = floors - 1

            traffic.append({"id": passenger_id, "origin": origin, "destination": destination, "tick": tick})
            passenger_id += 1

    return limit_traffic_count(traffic, max_people)


def generate_down_peak_traffic(
    floors: int = 10, duration: int = 300, intensity: float = 0.6, max_people: int = 100, seed: int = 42
) -> List[Dict[str, Any]]:
    """生成下行高峰流量 - 主要从高层到底层"""
    random.seed(seed)
    traffic = []
    passenger_id = 1

    # 根据目标人数调整强度
    adjusted_intensity = calculate_intensity_for_scale(intensity, floors, max_people, duration)

    for tick in range(duration):
        # 根据时间调整强度 - 后期高峰
        time_factor = 1.0 + 0.5 * math.sin((tick + duration / 2) * math.pi / duration)
        current_intensity = adjusted_intensity * time_factor

        if random.random() < current_intensity:
            # 针对小建筑调整比例 - 小建筑到大厅更频繁
            lobby_ratio = 0.95 if floors <= 5 else 0.9

            if random.random() < lobby_ratio:
                origin = random.randint(1, floors - 1)
                destination = 0
            else:
                # 其他楼层间流量
                if floors > 2:
                    origin = random.randint(2, floors - 1)
                    destination = random.randint(1, origin - 1)
                else:
                    origin = floors - 1
                    destination = 0

            traffic.append({"id": passenger_id, "origin": origin, "destination": destination, "tick": tick})
            passenger_id += 1

    return limit_traffic_count(traffic, max_people)


def generate_inter_floor_traffic(
    floors: int = 10, duration: int = 400, intensity: float = 0.4, max_people: int = 80, seed: int = 42
) -> List[Dict[str, Any]]:
    """生成楼层间流量 - 主要楼层间移动，适合小建筑"""
    random.seed(seed)
    traffic = []
    passenger_id = 1

    # 小建筑更适合这种场景，调整强度
    if floors <= 5:
        adjusted_intensity = calculate_intensity_for_scale(intensity * 1.2, floors, max_people, duration)
    else:
        adjusted_intensity = calculate_intensity_for_scale(intensity, floors, max_people, duration)

    for tick in range(duration):
        # 平稳的流量，轻微波动
        time_variation = 1.0 + 0.2 * math.sin(tick * 2 * math.pi / duration)
        current_intensity = adjusted_intensity * time_variation

        if random.random() < current_intensity:
            if floors <= 3:
                # 超小建筑，允许包含大厅
                origin = random.randint(0, floors - 1)
                destination = random.choice([f for f in range(floors) if f != origin])
            else:
                # 其他建筑，避免大厅
                origin = random.randint(1, floors - 1)
                destination = random.choice([f for f in range(1, floors) if f != origin])

            traffic.append({"id": passenger_id, "origin": origin, "destination": destination, "tick": tick})
            passenger_id += 1

    return limit_traffic_count(traffic, max_people)


def generate_lunch_rush_traffic(
    floors: int = 10, duration: int = 200, intensity: float = 0.7, max_people: int = 60, seed: int = 42
) -> List[Dict[str, Any]]:
    """生成午餐时间流量 - 双向流量，适合中大型建筑"""
    random.seed(seed)
    traffic = []
    passenger_id = 1

    # 小建筑没有餐厅概念，生成简单的双向流量
    if floors <= 5:
        # 小建筑简化为楼层间随机流量
        adjusted_intensity = calculate_intensity_for_scale(intensity * 0.6, floors, max_people, duration)

        for tick in range(duration):
            # 高斯分布的流量强度
            peak_center = duration // 2
            peak_width = duration // 4
            distance_from_peak = abs(tick - peak_center) / peak_width
            current_intensity = adjusted_intensity * max(0.3, math.exp(-distance_from_peak * distance_from_peak))

            if random.random() < current_intensity:
                origin = random.randint(0, floors - 1)
                destination = random.choice([f for f in range(floors) if f != origin])
                traffic.append({"id": passenger_id, "origin": origin, "destination": destination, "tick": tick})
                passenger_id += 1
    else:
        # 中大型建筑，假设1-2楼是餐厅，3+楼是办公室
        restaurant_floors = [1, 2] if floors > 2 else [1]
        office_floors = list(range(max(3, len(restaurant_floors) + 1), floors))

        adjusted_intensity = calculate_intensity_for_scale(intensity, floors, max_people, duration)

        for tick in range(duration):
            # 高斯分布的流量强度
            peak_center = duration // 2
            peak_width = duration // 4
            distance_from_peak = abs(tick - peak_center) / peak_width
            current_intensity = adjusted_intensity * max(0.2, math.exp(-distance_from_peak * distance_from_peak))

            if random.random() < current_intensity:
                if office_floors and random.random() < 0.5:
                    # 去餐厅
                    origin = random.choice(office_floors)
                    destination = random.choice(restaurant_floors)
                else:
                    # 回办公室
                    origin = random.choice(restaurant_floors)
                    destination = random.choice(office_floors) if office_floors else 0

                traffic.append({"id": passenger_id, "origin": origin, "destination": destination, "tick": tick})
                passenger_id += 1

    return limit_traffic_count(traffic, max_people)


def generate_random_traffic(
    floors: int = 10, duration: int = 500, intensity: float = 0.3, max_people: int = 80, seed: int = 42
) -> List[Dict[str, Any]]:
    """生成随机流量 - 均匀分布，适合所有规模建筑"""
    random.seed(seed)
    traffic = []
    passenger_id = 1

    # 根据目标人数调整强度
    adjusted_intensity = calculate_intensity_for_scale(intensity, floors, max_people, duration)

    for tick in range(duration):
        # 添加轻微的时间变化，避免完全平坦
        time_variation = 1.0 + 0.1 * math.sin(tick * 4 * math.pi / duration)
        current_intensity = adjusted_intensity * time_variation

        if random.random() < current_intensity:
            origin = random.randint(0, floors - 1)
            destination = random.choice([f for f in range(floors) if f != origin])

            traffic.append({"id": passenger_id, "origin": origin, "destination": destination, "tick": tick})
            passenger_id += 1

    return limit_traffic_count(traffic, max_people)


def generate_fire_evacuation_traffic(
    floors: int = 10, duration: int = 150, max_people: int = 120, seed: int = 42
) -> List[Dict[str, Any]]:
    """生成火警疏散流量 - 紧急疏散到大厅"""
    random.seed(seed)
    traffic = []
    passenger_id = 1

    # 正常时间段
    normal_duration = duration // 3

    # 正常流量 - 较少
    normal_intensity = 0.15
    for tick in range(normal_duration):
        if random.random() < normal_intensity:
            origin = random.randint(0, floors - 1)
            destination = random.choice([f for f in range(floors) if f != origin])
            traffic.append({"id": passenger_id, "origin": origin, "destination": destination, "tick": tick})
            passenger_id += 1

    # 火警开始 - 大量疏散到大厅
    alarm_tick = normal_duration

    # 根据建筑规模调整每层人数
    if floors <= 5:
        people_per_floor = (2, 4)  # 小建筑每层2-4人
    elif floors <= 9:
        people_per_floor = (3, 6)  # 中建筑每层3-6人
    else:
        people_per_floor = (4, 8)  # 大建筑每层4-8人

    for floor in range(1, floors):
        # 每层随机数量的人需要疏散
        num_people = random.randint(people_per_floor[0], people_per_floor[1])
        for _ in range(num_people):
            # 在10个tick内陆续到达，模拟疏散的紧急性
            arrival_tick = alarm_tick + random.randint(0, min(10, duration - alarm_tick - 1))
            if arrival_tick < duration:
                traffic.append({"id": passenger_id, "origin": floor, "destination": 0, "tick": arrival_tick})  # 疏散到大厅
                passenger_id += 1

    return limit_traffic_count(traffic, max_people)


def generate_mixed_scenario_traffic(
    floors: int = 10, duration: int = 600, max_people: int = 150, seed: int = 42
) -> List[Dict[str, Any]]:
    """生成混合场景流量 - 包含多种模式，适合中大型建筑"""
    random.seed(seed)
    traffic = []
    passenger_id = 1

    # 根据人数目标调整各阶段强度
    target_per_phase = max_people // 4

    # 第一阶段：上行高峰 (0-25%)
    phase1_end = duration // 4
    phase1_intensity = calculate_intensity_for_scale(0.7, floors, target_per_phase, phase1_end)

    for tick in range(phase1_end):
        if random.random() < phase1_intensity:
            lobby_ratio = 0.9 if floors > 5 else 0.95
            if random.random() < lobby_ratio:
                origin = 0
                destination = random.randint(1, floors - 1)
            else:
                if floors > 2:
                    origin = random.randint(0, floors - 2)
                    destination = random.randint(origin + 1, floors - 1)
                else:
                    origin = 0
                    destination = floors - 1

            traffic.append({"id": passenger_id, "origin": origin, "destination": destination, "tick": tick})
            passenger_id += 1

    # 第二阶段：正常流量 (25%-50%)
    phase2_end = duration // 2
    phase2_intensity = calculate_intensity_for_scale(0.3, floors, target_per_phase, phase2_end - phase1_end)

    for tick in range(phase1_end, phase2_end):
        if random.random() < phase2_intensity:
            origin = random.randint(0, floors - 1)
            destination = random.choice([f for f in range(floors) if f != origin])

            traffic.append({"id": passenger_id, "origin": origin, "destination": destination, "tick": tick})
            passenger_id += 1

    # 第三阶段：午餐/中峰流量 (50%-67%)
    phase3_end = phase2_end + duration // 6
    phase3_intensity = calculate_intensity_for_scale(0.6, floors, target_per_phase, phase3_end - phase2_end)

    for tick in range(phase2_end, phase3_end):
        if random.random() < phase3_intensity:
            if floors > 5 and random.random() < 0.6:
                # 餐厅流量 - 仅适用于大型建筑
                if random.random() < 0.5:
                    origin = random.randint(3, floors - 1)
                    destination = random.randint(1, 2)
                else:
                    origin = random.randint(1, 2)
                    destination = random.randint(3, floors - 1)
            else:
                # 其他流量
                origin = random.randint(0, floors - 1)
                destination = random.choice([f for f in range(floors) if f != origin])

            traffic.append({"id": passenger_id, "origin": origin, "destination": destination, "tick": tick})
            passenger_id += 1

    # 第四阶段：下行高峰 (67%-100%)
    phase4_intensity = calculate_intensity_for_scale(0.6, floors, target_per_phase, duration - phase3_end)

    for tick in range(phase3_end, duration):
        if random.random() < phase4_intensity:
            lobby_ratio = 0.85 if floors > 5 else 0.9
            if random.random() < lobby_ratio:
                origin = random.randint(1, floors - 1)
                destination = 0
            else:
                if floors > 2:
                    origin = random.randint(2, floors - 1)
                    destination = random.randint(1, origin - 1)
                else:
                    origin = floors - 1
                    destination = 0

            traffic.append({"id": passenger_id, "origin": origin, "destination": destination, "tick": tick})
            passenger_id += 1

    return limit_traffic_count(traffic, max_people)


def generate_high_density_traffic(
    floors: int = 10, duration: int = 300, intensity: float = 1.2, max_people: int = 200, seed: int = 42
) -> List[Dict[str, Any]]:
    """生成高密度流量 - 压力测试，适合测试电梯系统极限"""
    random.seed(seed)
    traffic = []
    passenger_id = 1

    # 计算目标强度，确保不超过人数限制
    target_people_per_tick = max_people / duration
    safe_intensity = min(intensity, target_people_per_tick * 1.5)  # 留出一些余量

    for tick in range(duration):
        # 高强度的随机流量，使用高斯分布增加变化
        base_passengers = safe_intensity
        variation = random.gauss(0, safe_intensity * 0.3)  # 30%变化
        num_passengers = max(0, int(base_passengers + variation))

        for _ in range(num_passengers):
            origin = random.randint(0, floors - 1)
            destination = random.choice([f for f in range(floors) if f != origin])

            traffic.append({"id": passenger_id, "origin": origin, "destination": destination, "tick": tick})
            passenger_id += 1

            # 提前检查，避免生成过多乘客
            if len(traffic) >= max_people:
                break

        if len(traffic) >= max_people:
            break

    return limit_traffic_count(traffic, max_people)


def generate_small_building_traffic(
    floors: int = 4, duration: int = 180, intensity: float = 0.4, max_people: int = 25, seed: int = 42
) -> List[Dict[str, Any]]:
    """生成小建筑专用流量 - 简单楼层间移动，适合3-5层建筑"""
    random.seed(seed)
    traffic = []
    passenger_id = 1

    # 小建筑特点：频繁使用大厅，简单的上下楼
    adjusted_intensity = calculate_intensity_for_scale(intensity, floors, max_people, duration)

    for tick in range(duration):
        # 轻微的时间变化
        time_factor = 1.0 + 0.3 * math.sin(tick * 2 * math.pi / duration)
        current_intensity = adjusted_intensity * time_factor

        if random.random() < current_intensity:
            # 80%涉及大厅的移动
            if random.random() < 0.8:
                if random.random() < 0.5:
                    # 从大厅上楼
                    origin = 0
                    destination = random.randint(1, floors - 1)
                else:
                    # 下到大厅
                    origin = random.randint(1, floors - 1)
                    destination = 0
            else:
                # 楼层间移动
                origin = random.randint(1, floors - 1)
                destination = random.choice([f for f in range(1, floors) if f != origin])

            traffic.append({"id": passenger_id, "origin": origin, "destination": destination, "tick": tick})
            passenger_id += 1

    return limit_traffic_count(traffic, max_people)


def generate_medical_building_traffic(
    floors: int = 8, duration: int = 240, intensity: float = 0.5, max_people: int = 80, seed: int = 42
) -> List[Dict[str, Any]]:
    """生成医疗建筑流量 - 模拟医院/诊所的特殊流量模式"""
    random.seed(seed)
    traffic = []
    passenger_id = 1

    # 医疗建筑特点：大厅使用频繁，某些楼层(如手术室)访问较少
    adjusted_intensity = calculate_intensity_for_scale(intensity, floors, max_people, duration)

    # 定义楼层类型权重 - 大厅和低层更频繁
    floor_weights = []
    for floor in range(floors):
        if floor == 0:  # 大厅 - 最高权重
            weight = 3.0
        elif floor <= 2:  # 急诊、门诊 - 高权重
            weight = 2.0
        elif floor <= floors - 2:  # 普通病房 - 中等权重
            weight = 1.0
        else:  # 手术室、ICU - 低权重
            weight = 0.3
        floor_weights.append(weight)

    for tick in range(duration):
        # 医疗建筑通常有明显的时间模式
        time_factor = 1.0 + 0.4 * math.sin((tick + duration * 0.2) * math.pi / duration)
        current_intensity = adjusted_intensity * time_factor

        if random.random() < current_intensity:
            # 85%的移动涉及大厅
            if random.random() < 0.85:
                if random.random() < 0.6:
                    # 从大厅到其他楼层
                    origin = 0
                    # 使用权重选择目标楼层
                    destinations = list(range(1, floors))
                    weights = floor_weights[1:]
                    destination = random.choices(destinations, weights=weights)[0]
                else:
                    # 从其他楼层到大厅
                    origins = list(range(1, floors))
                    weights = floor_weights[1:]
                    origin = random.choices(origins, weights=weights)[0]
                    destination = 0
            else:
                # 楼层间移动（较少）
                floor_candidates = list(range(floors))
                origin = random.choice(floor_candidates)
                destination = random.choice([f for f in floor_candidates if f != origin])

            traffic.append({"id": passenger_id, "origin": origin, "destination": destination, "tick": tick})
            passenger_id += 1

    return limit_traffic_count(traffic, max_people)


def generate_meeting_event_traffic(
    floors: int = 6, duration: int = 150, intensity: float = 0.8, max_people: int = 50, seed: int = 42
) -> List[Dict[str, Any]]:
    """生成会议事件流量 - 模拟大型会议开始和结束的流量模式"""
    random.seed(seed)
    traffic = []
    passenger_id = 1

    # 假设会议在某个楼层举行
    meeting_floor = floors // 2 if floors > 2 else 1

    # 会议分为三个阶段：到达、中间、离开
    arrival_end = duration // 3
    departure_start = duration * 2 // 3

    for tick in range(duration):
        should_add_passenger = False
        origin = 0
        destination = 0

        if tick < arrival_end:
            # 到达阶段 - 大量人员前往会议楼层
            phase_progress = tick / arrival_end
            current_intensity = intensity * (1.0 + math.sin(phase_progress * math.pi))

            if random.random() < current_intensity:
                # 主要从大厅到会议楼层
                if random.random() < 0.9:
                    origin = 0
                    destination = meeting_floor
                else:
                    # 少量其他楼层间移动
                    origin = random.randint(0, floors - 1)
                    destination = random.choice([f for f in range(floors) if f != origin])
                should_add_passenger = True

        elif tick >= departure_start:
            # 离开阶段 - 大量人员从会议楼层离开
            phase_progress = (tick - departure_start) / (duration - departure_start)
            current_intensity = intensity * (1.0 + math.sin(phase_progress * math.pi))

            if random.random() < current_intensity:
                # 主要从会议楼层到大厅
                if random.random() < 0.9:
                    origin = meeting_floor
                    destination = 0
                else:
                    # 少量其他移动
                    origin = random.randint(0, floors - 1)
                    destination = random.choice([f for f in range(floors) if f != origin])
                should_add_passenger = True
        else:
            # 中间阶段 - 低流量
            if random.random() < intensity * 0.1:
                origin = random.randint(0, floors - 1)
                destination = random.choice([f for f in range(floors) if f != origin])
                should_add_passenger = True

        if should_add_passenger:
            traffic.append({"id": passenger_id, "origin": origin, "destination": destination, "tick": tick})
            passenger_id += 1

    return limit_traffic_count(traffic, max_people)


def generate_progressive_test_traffic(
    floors: int = 8, duration: int = 400, max_people: int = 100, seed: int = 42
) -> List[Dict[str, Any]]:
    """生成渐进式测试流量 - 从低强度逐渐增加到高强度"""
    random.seed(seed)
    traffic = []
    passenger_id = 1

    # 分为四个阶段，强度逐渐增加
    stage_duration = duration // 4

    for stage in range(4):
        stage_start = stage * stage_duration
        stage_end = min((stage + 1) * stage_duration, duration)
        stage_intensity = 0.2 + stage * 0.25  # 0.2, 0.45, 0.7, 0.95

        stage_target = max_people // 4
        adjusted_intensity = calculate_intensity_for_scale(stage_intensity, floors, stage_target, stage_duration)

        for tick in range(stage_start, stage_end):
            # 每个阶段内部也有变化
            local_progress = (tick - stage_start) / stage_duration
            time_factor = 1.0 + 0.3 * math.sin(local_progress * 2 * math.pi)
            current_intensity = adjusted_intensity * time_factor

            if random.random() < current_intensity:
                origin = random.randint(0, floors - 1)
                destination = random.choice([f for f in range(floors) if f != origin])

                traffic.append({"id": passenger_id, "origin": origin, "destination": destination, "tick": tick})
                passenger_id += 1

    return limit_traffic_count(traffic, max_people)


# 按建筑规模分类的场景配置
TRAFFIC_SCENARIOS = {
    # 经典场景 - 适用于所有规模，会根据建筑规模自动调整
    "up_peak": {
        "generator": generate_up_peak_traffic,
        "description": "上行高峰 - 主要从底层到高层",
        "scales": {
            "small": {"intensity": 0.5, "max_people": 20},
            "medium": {"intensity": 0.6, "max_people": 80},
            "large": {"intensity": 0.7, "max_people": 150},
        },
        "suitable_scales": ["small", "medium", "large"],
    },
    "down_peak": {
        "generator": generate_down_peak_traffic,
        "description": "下行高峰 - 主要从高层到底层",
        "scales": {
            "small": {"intensity": 0.5, "max_people": 20},
            "medium": {"intensity": 0.6, "max_people": 80},
            "large": {"intensity": 0.7, "max_people": 150},
        },
        "suitable_scales": ["small", "medium", "large"],
    },
    "inter_floor": {
        "generator": generate_inter_floor_traffic,
        "description": "楼层间流量 - 适合小建筑",
        "scales": {
            "small": {"intensity": 0.6, "max_people": 30},
            "medium": {"intensity": 0.4, "max_people": 60},
            "large": {"intensity": 0.3, "max_people": 80},
        },
        "suitable_scales": ["small", "medium", "large"],
    },
    "lunch_rush": {
        "generator": generate_lunch_rush_traffic,
        "description": "午餐时间流量 - 双向流量，适合中大型建筑",
        "scales": {
            "small": {"intensity": 0.4, "max_people": 25},
            "medium": {"intensity": 0.7, "max_people": 60},
            "large": {"intensity": 0.8, "max_people": 100},
        },
        "suitable_scales": ["medium", "large"],
    },
    "random": {
        "generator": generate_random_traffic,
        "description": "随机流量 - 均匀分布，适合所有规模",
        "scales": {
            "small": {"intensity": 0.4, "max_people": 25},
            "medium": {"intensity": 0.3, "max_people": 80},
            "large": {"intensity": 0.25, "max_people": 120},
        },
        "suitable_scales": ["small", "medium", "large"],
    },
    "fire_evacuation": {
        "generator": generate_fire_evacuation_traffic,
        "description": "火警疏散 - 紧急疏散到大厅",
        "scales": {"small": {"max_people": 20}, "medium": {"max_people": 70}, "large": {"max_people": 120}},
        "suitable_scales": ["small", "medium", "large"],
    },
    "mixed_scenario": {
        "generator": generate_mixed_scenario_traffic,
        "description": "混合场景 - 包含多种流量模式，适合中大型建筑",
        "scales": {"medium": {"max_people": 100}, "large": {"max_people": 180}},
        "suitable_scales": ["medium", "large"],
    },
    "high_density": {
        "generator": generate_high_density_traffic,
        "description": "高密度流量 - 压力测试",
        "scales": {
            "small": {"intensity": 0.8, "max_people": 35},
            "medium": {"intensity": 1.0, "max_people": 120},
            "large": {"intensity": 1.2, "max_people": 200},
        },
        "suitable_scales": ["small", "medium", "large"],
    },
    # 新增的专用场景
    "small_building": {
        "generator": generate_small_building_traffic,
        "description": "小建筑专用 - 简单楼层间移动",
        "scales": {"small": {"intensity": 0.4, "max_people": 25}},
        "suitable_scales": ["small"],
    },
    "medical": {
        "generator": generate_medical_building_traffic,
        "description": "医疗建筑 - 特殊流量模式",
        "scales": {"medium": {"intensity": 0.5, "max_people": 80}, "large": {"intensity": 0.6, "max_people": 120}},
        "suitable_scales": ["medium", "large"],
    },
    "meeting_event": {
        "generator": generate_meeting_event_traffic,
        "description": "会议事件 - 集中到达和离开",
        "scales": {
            "small": {"intensity": 0.6, "max_people": 30},
            "medium": {"intensity": 0.8, "max_people": 50},
            "large": {"intensity": 1.0, "max_people": 80},
        },
        "suitable_scales": ["small", "medium", "large"],
    },
    "progressive_test": {
        "generator": generate_progressive_test_traffic,
        "description": "渐进式测试 - 强度逐渐增加",
        "scales": {"small": {"max_people": 40}, "medium": {"max_people": 100}, "large": {"max_people": 150}},
        "suitable_scales": ["small", "medium", "large"],
    },
}


def determine_building_scale(floors: int, elevators: int) -> str:
    """根据楼层数和电梯数确定建筑规模"""
    if floors <= 5 and elevators <= 2:
        return "small"
    elif floors <= 9 and elevators <= 3:
        return "medium"
    else:
        return "large"


def generate_traffic_file(scenario: str, output_file: str, scale: Optional[str] = None, **kwargs: Any) -> int:
    """生成单个流量文件，支持规模化配置"""
    if scenario not in TRAFFIC_SCENARIOS:
        raise ValueError(f"Unknown scenario: {scenario}. Available: {list(TRAFFIC_SCENARIOS.keys())}")

    config: Dict[str, Any] = TRAFFIC_SCENARIOS[scenario]

    # 确定建筑规模
    if scale is None:
        floors = kwargs.get("floors", 6)  # 默认中等规模
        elevators = kwargs.get("elevators", 2)
        scale = determine_building_scale(floors, elevators)

    # 检查场景是否适合该规模
    if scale not in config["suitable_scales"]:
        print(
            f"Warning: Scenario '{scenario}' not recommended for scale '{scale}'. Suitable scales: {config['suitable_scales']}"
        )
        # 选择最接近的适合规模
        if "medium" in config["suitable_scales"]:
            scale = "medium"
        else:
            scale = config["suitable_scales"][0]

    # 获取规模特定的参数
    scale_params = config["scales"].get(scale, {})

    # 合并参数：kwargs > scale_params > building_scale_defaults
    assert scale is not None  # scale should be determined by this point
    building_scale = BUILDING_SCALES[scale]
    params = {}

    # 设置默认参数
    params["floors"] = kwargs.get("floors", building_scale["floors"][0])
    params["elevators"] = kwargs.get("elevators", building_scale["elevators"][0])
    params["elevator_capacity"] = kwargs.get("elevator_capacity", building_scale["capacity"][0])

    # 设置场景相关参数
    params["duration"] = kwargs.get("duration", building_scale["duration_range"][0])
    params["intensity"] = scale_params.get("intensity", 0.5)
    params["max_people"] = scale_params.get("max_people", building_scale["max_people"][0])
    params["seed"] = kwargs.get("seed", 42)

    # 允许kwargs完全覆盖
    params.update(kwargs)

    # 生成流量数据 - 只传递生成器函数需要的参数
    import inspect

    generator_func: Callable[..., List[Dict[str, Any]]] = config["generator"]
    generator_signature = inspect.signature(generator_func)
    generator_params = {k: v for k, v in params.items() if k in generator_signature.parameters}
    traffic_data = generator_func(**generator_params)

    # 准备building配置
    num_elevators = params["elevators"]
    building_config = {
        "floors": params["floors"],
        "elevators": num_elevators,
        "elevator_capacity": params["elevator_capacity"],
        "elevator_energy_rates": [1.0] * num_elevators,  # 每台电梯的能耗率，默认为1.0
        "scenario": scenario,
        "scale": scale,
        "description": f"{config['description']} ({scale}规模)",
        "expected_passengers": len(traffic_data),
        "duration": params["duration"],
    }

    # 组合完整的数据结构
    complete_data = {"building": building_config, "traffic": traffic_data}

    # 写入文件
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(complete_data, f, indent=2, ensure_ascii=False)

    print(f"Generated {len(traffic_data)} passengers for scenario '{scenario}' ({scale}) -> {output_file}")
    return len(traffic_data)


def generate_scaled_traffic_files(
    output_dir: str,
    scale: str = "medium",
    seed: int = 42,
    generate_all_scales: bool = False,
    custom_building: Optional[Dict[str, Any]] = None,
) -> None:
    """生成按规模分类的流量文件"""
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    if generate_all_scales:
        # 生成所有规模的文件
        for scale_name in ["small", "medium", "large"]:
            scale_dir = output_path / scale_name
            scale_dir.mkdir(exist_ok=True)
            _generate_files_for_scale(scale_dir, scale_name, seed)
    else:
        # 只生成指定规模
        if custom_building:
            floors = custom_building.get("floors", BUILDING_SCALES[scale]["floors"][0])
            elevators = custom_building.get("elevators", BUILDING_SCALES[scale]["elevators"][0])
            _elevator_capacity = custom_building.get("capacity", BUILDING_SCALES[scale]["capacity"][0])

            # 重新确定规模
            detected_scale = determine_building_scale(floors, elevators)
            if detected_scale != scale:
                print(f"Note: Building config suggests {detected_scale} scale, but {scale} was requested")
                scale = detected_scale

        _generate_files_for_scale(output_path, scale, seed, custom_building)


def _generate_files_for_scale(
    output_path: Path, scale: str, seed: int, custom_building: Optional[Dict[str, Any]] = None
) -> None:
    """为指定规模生成所有适合的场景文件"""
    building_config = BUILDING_SCALES[scale]
    total_passengers = 0
    files_generated = 0

    # 确定建筑参数
    if custom_building:
        floors = custom_building.get("floors", building_config["floors"][0])
        elevators = custom_building.get("elevators", building_config["elevators"][0])
        elevator_capacity = custom_building.get("capacity", building_config["capacity"][0])
    else:
        # 使用规模的默认配置
        floors = building_config["floors"][0]
        elevators = building_config["elevators"][0]
        elevator_capacity = building_config["capacity"][0]

    print(f"\nGenerating {scale} scale traffic files:")
    print(f"Building: {floors} floors, {elevators} elevators, capacity {elevator_capacity}")

    for scenario_name, scenario_config in TRAFFIC_SCENARIOS.items():
        # 检查场景是否适合该规模
        config_dict: Dict[str, Any] = scenario_config
        if scale not in config_dict["suitable_scales"]:
            continue

        filename = f"{scenario_name}.json"
        file_path = output_path / filename

        # 准备参数
        params = {
            "floors": floors,
            "elevators": elevators,
            "elevator_capacity": elevator_capacity,
            "seed": seed + hash(scenario_name) % 1000,  # 为每个场景使用不同的seed
        }

        # 生成流量文件
        try:
            passenger_count = generate_traffic_file(scenario_name, str(file_path), scale=scale, **params)
            total_passengers += passenger_count
            files_generated += 1
        except Exception as e:
            print(f"Error generating {scenario_name}: {e}")

    print(f"Generated {files_generated} traffic files for {scale} scale in {output_path}")
    print(f"Total passengers: {total_passengers}")
    print(
        f"Average per scenario: {total_passengers/files_generated:.1f}" if files_generated > 0 else "No files generated"
    )


def generate_all_traffic_files(
    output_dir: str,
    floors: int = 6,
    elevators: int = 2,
    elevator_capacity: int = 8,
    seed: int = 42,
) -> None:
    """生成所有场景的流量文件 - 保持向后兼容"""
    scale = determine_building_scale(floors, elevators)
    custom_building = {"floors": floors, "elevators": elevators, "capacity": elevator_capacity}

    generate_scaled_traffic_files(output_dir=output_dir, scale=scale, seed=seed, custom_building=custom_building)


def main() -> None:
    """主函数 - 命令行接口"""
    import argparse

    parser = argparse.ArgumentParser(description="Generate scalable elevator traffic files")
    parser.add_argument(
        "--scale",
        type=str,
        choices=["small", "medium", "large"],
        help="Building scale (overrides individual parameters)",
    )
    parser.add_argument(
        "--all-scales", action="store_true", help="Generate files for all scales in separate directories"
    )
    parser.add_argument("--floors", type=int, help="Number of floors")
    parser.add_argument("--elevators", type=int, help="Number of elevators")
    parser.add_argument("--elevator-capacity", type=int, help="Elevator capacity")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--output-dir", type=str, default=None, help="Output directory (default: current directory)")

    args = parser.parse_args()

    output_dir = args.output_dir or os.path.dirname(__file__)

    if args.all_scales:
        # 生成所有规模的文件
        generate_scaled_traffic_files(output_dir=output_dir, generate_all_scales=True, seed=args.seed)
    elif args.scale:
        # 生成指定规模的文件
        custom_building = None
        if args.floors or args.elevators or args.elevator_capacity:
            custom_building = {}
            if args.floors:
                custom_building["floors"] = args.floors
            if args.elevators:
                custom_building["elevators"] = args.elevators
            if args.elevator_capacity:
                custom_building["capacity"] = args.elevator_capacity

        generate_scaled_traffic_files(
            output_dir=output_dir, scale=args.scale, seed=args.seed, custom_building=custom_building
        )
    else:
        # 向后兼容模式：使用旧的参数
        floors = args.floors or 6
        elevators = args.elevators or 2
        elevator_capacity = args.elevator_capacity or 8

        generate_all_traffic_files(
            output_dir=output_dir,
            floors=floors,
            elevators=elevators,
            elevator_capacity=elevator_capacity,
            seed=args.seed,
        )

    print("\nUsage examples:")
    print("  # Generate all scales:")
    print("  python generators.py --all-scales")
    print("  # Generate small scale:")
    print("  python generators.py --scale small")
    print("  # Custom building (auto-detect scale):")
    print("  python generators.py --floors 3 --elevators 1")
    print("  # Force scale with custom config:")
    print("  python generators.py --scale large --floors 12 --elevators 4")


if __name__ == "__main__":
    main()
