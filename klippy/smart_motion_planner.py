# Global motion planning helpers for vibration-aware trajectory optimization.
#
# This module adds a pre-processing planner that can evaluate a full list of
# motion segments, estimate likely structural excitation, and optimize the
# execution order of commutative microsegments while preserving final geometry.
import math
from dataclasses import dataclass


@dataclass
class TrajectorySegment:
    index: int
    start: tuple
    end: tuple
    feedrate: float
    commanded_jerk: float
    axis_mask: tuple
    extrusion_delta: float
    line: str

    @property
    def delta(self):
        return tuple(b - a for a, b in zip(self.start, self.end))

    @property
    def length(self):
        return math.sqrt(sum(d * d for d in self.delta))


class SmartMotionPlanner:
    def __init__(self, resonance_hz=40.0, time_weight=0.02,
                 max_reorder_distance=0.05, adaptive_jerk_gain=0.35):
        self.resonance_hz = float(resonance_hz)
        self.time_weight = float(time_weight)
        self.max_reorder_distance = float(max_reorder_distance)
        self.adaptive_jerk_gain = float(adaptive_jerk_gain)

    def analyze_gcode_graph(self, segments):
        graph = []
        for i, seg in enumerate(segments):
            prev_seg = segments[i - 1] if i > 0 else None
            next_seg = segments[i + 1] if i + 1 < len(segments) else None
            vibration_energy = self._estimate_vibration_energy(
                seg, prev_seg=prev_seg, next_seg=next_seg)
            adaptive_jerk = self._adaptive_jerk_limit(seg, prev_seg=prev_seg)
            graph.append({
                'segment': seg,
                'index': seg.index,
                'neighbors': [n for n in (i - 1, i + 1)
                              if 0 <= n < len(segments)],
                'vibration_energy': vibration_energy,
                'adaptive_jerk_limit': adaptive_jerk,
                'high_resonance': vibration_energy > 1.0,
            })
        return graph

    def optimize_trajectory(self, graph):
        optimized = [node.copy() for node in graph]
        n = len(optimized)
        for i in range(1, n - 1):
            left = optimized[i - 1]
            center = optimized[i]
            right = optimized[i + 1]
            if not self._is_reorder_candidate(center, right):
                continue
            baseline = self._objective(left, center, right)
            swapped = self._objective(left, right, center)
            if swapped + 1e-9 < baseline:
                optimized[i], optimized[i + 1] = right, center
        return optimized

    def _objective(self, left, center, right):
        cseg = center['segment']
        rseg = right['segment']
        seg_time = 0.0
        if cseg.feedrate > 0:
            seg_time += cseg.length / cseg.feedrate
        if rseg.feedrate > 0:
            seg_time += rseg.length / rseg.feedrate
        vibration = center['vibration_energy'] + right['vibration_energy']
        return vibration + self.time_weight * seg_time

    def _adaptive_jerk_limit(self, seg, prev_seg=None):
        if prev_seg is None or seg.length <= 0.:
            return seg.commanded_jerk
        angle = self._corner_angle(prev_seg, seg)
        angle_factor = max(0.0, min(1.0, abs(angle) / math.pi))
        reduction = self.adaptive_jerk_gain * angle_factor
        return seg.commanded_jerk * (1.0 - reduction)

    def _estimate_vibration_energy(self, seg, prev_seg=None, next_seg=None):
        length = max(seg.length, 1e-9)
        speed = max(seg.feedrate, 1e-9)
        dominant_freq = speed / length
        resonance_ratio = dominant_freq / max(self.resonance_hz, 1e-9)
        resonance_gain = 1.0 / (1.0 + (resonance_ratio - 1.0) ** 2)
        corner_gain = 1.0
        if prev_seg is not None:
            corner_gain += abs(self._corner_angle(prev_seg, seg)) / math.pi
        if next_seg is not None:
            corner_gain += abs(self._corner_angle(seg, next_seg)) / math.pi
        axis_energy = sum(abs(d) for d in seg.delta)
        return resonance_gain * corner_gain * axis_energy

    def _corner_angle(self, a, b):
        ad = a.delta
        bd = b.delta
        ad_norm = math.sqrt(sum(x * x for x in ad))
        bd_norm = math.sqrt(sum(x * x for x in bd))
        if ad_norm <= 1e-9 or bd_norm <= 1e-9:
            return 0.0
        dot = sum(x * y for x, y in zip(ad, bd)) / (ad_norm * bd_norm)
        dot = max(-1.0, min(1.0, dot))
        return math.acos(dot)

    def _is_reorder_candidate(self, a, b):
        sa = a['segment']
        sb = b['segment']
        if sa.extrusion_delta != 0.0 or sb.extrusion_delta != 0.0:
            return False
        if sa.axis_mask != sb.axis_mask:
            return False
        end_distance = math.sqrt(sum((ea - eb) * (ea - eb)
                                     for ea, eb in zip(sa.end, sb.end)))
        return end_distance <= self.max_reorder_distance


def analyze_gcode_graph(segments, planner=None):
    planner = planner or SmartMotionPlanner()
    return planner.analyze_gcode_graph(segments)


def optimize_trajectory(graph, planner=None):
    planner = planner or SmartMotionPlanner()
    return planner.optimize_trajectory(graph)
