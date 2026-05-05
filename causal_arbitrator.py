# -*- coding: utf-8 -*-
"""
wukong_causality/causal_arbitrator.py — 公理冲突仲裁器

公理冲突（axiom之间要求相反）vs 置信度调制（axiom_to_law.py的权重×分数）
是两个不同层次：
  - 置信度调制：单 axiom 内部，score 低 → 强度降低 → 沉默
  - 冲突仲裁：多 axiom 之间，A 和 B 要求完全相反 → 必须裁决谁胜出

悟道核心：冲突不是错误，是约束碰撞的正常状态。
仲裁不是为了消除冲突，而是让冲突被有意识地解决。

用法：
    
    claims = [
        AxiomClaim(5, 'concentrate', 'peak', 0.95),
        AxiomClaim(7, 'dissipate', 'max_freedom', 0.88),
    ]
    resolver = ConflictResolver()
    conflicts = resolver.detect_conflict(claims)
    final = resolver.arbitrate(conflicts)

作者：悟道体系·因果层 | 2026-05-05
"""

from enum import IntEnum
from typing import Dict, List, Optional

# ── 公理名字映射 ──────────────────────────────────────────────────────────
AXIOM_NAMES = {
    1: "生长", 2: "光影", 3: "色彩", 4: "布局",
    5: "叙事", 6: "边界", 7: "自由", 8: "因果"
}

# 公理优先级（数字小=优先，来自 axiom_constants.py）
# 可被师傅修订
AXIOM_PRIORITY: Dict[str, int] = {
    "光影": 1, "因果": 2, "边界": 3, "叙事": 4,
    "布局": 5, "色彩": 6, "生长": 7, "自由": 7,
}


class ConflictType(IntEnum):
    NONE = 0
    OPPOSITE = 1   # 要求完全相反（如聚焦 vs 发散）
    TRADE_OFF = 2  # 存在权衡（如强度 vs 细腻度）


class AxiomClaim:
    """
    单个公理的声明

    参数：
        axiom_id: 公理编号（1-8）
        claim_type: 声明方向（见 OPPOSITE_PAIRS）
        target_value: 目标值（任意类型）
        intensity: 强度 0-1
        reason: 理由（供人工审查）
    """

    def __init__(self, axiom_id: int, claim_type: str,
                 target_value=None, intensity: float = 1.0, reason: str = ""):
        self.axiom_id = axiom_id
        self.axiom_name = AXIOM_NAMES.get(axiom_id, f"axiom{axiom_id}")
        self.claim_type = claim_type
        self.target_value = target_value
        self.intensity = intensity
        self.reason = reason
        self.priority = AXIOM_PRIORITY.get(self.axiom_name, 99)

    def __repr__(self):
        return (f"{self.axiom_name}(强度={self.intensity:.2f}, "
                f"主张={self.claim_type}, 优先级={self.priority})")


class AxiomConflict:
    """检测到的公理冲突"""

    def __init__(self, claim_a: AxiomClaim, claim_b: AxiomClaim,
                 conflict_type: ConflictType, explanation: str):
        self.claim_a = claim_a
        self.claim_b = claim_b
        self.conflict_type = conflict_type
        self.explanation = explanation
        self.winner: Optional[AxiomClaim] = None
        self.loser: Optional[AxiomClaim] = None
        self.arbitration_reason: str = ""

    def __repr__(self):
        return (f"冲突：{self.claim_a.axiom_name} vs {self.claim_b.axiom_name} "
                f"[{self.conflict_type.name}]")

    def report(self) -> str:
        """生成可读的裁决报告"""
        if not self.winner:
            return f"⚠️ 未裁决：{self.arbitration_reason}"
        return (
            f"✓ {self.winner.axiom_name} 胜出\n"
            f"  理由：{self.arbitration_reason}\n"
            f"  {self.loser.axiom_name} 被压制："
            f"({self.loser.intensity:.2f} × 0.30 = {self.loser.intensity*0.3:.3f})"
        )


class ConflictResolver:
    """
    公理冲突仲裁器

    规则：
    1. OPPOSITE 冲突：优先级高的公理胜出，低的强度 × 0.3
    2. 同优先级冲突：报告需师傅裁决（不自动裁决）
    3. 裁决理由可追溯

    OPPOSITE claim_type 对（frozenset → 对立方向标签）：
      focus ↔ spread
      concentrate ↔ dissipate
      constrain ↔ free
      intensify ↔ soften
      heat_up ↔ cool_down
      clarify ↔ ambiguate
      tighten ↔ loosen
      attract ↔ repel
      converge ↔ diverge
    """

    # frozenset 作为 dict key 避免顺序问题
    OPPOSITE_PAIRS: Dict[frozenset, ConflictType] = {
        frozenset({'focus', 'spread'}): ConflictType.OPPOSITE,
        frozenset({'concentrate', 'dissipate'}): ConflictType.OPPOSITE,
        frozenset({'constrain', 'free'}): ConflictType.OPPOSITE,
        frozenset({'intensify', 'soften'}): ConflictType.OPPOSITE,
        frozenset({'heat_up', 'cool_down'}): ConflictType.OPPOSITE,
        frozenset({'clarify', 'ambiguate'}): ConflictType.OPPOSITE,
        frozenset({'tighten', 'loosen'}): ConflictType.OPPOSITE,
        frozenset({'attract', 'repel'}): ConflictType.OPPOSITE,
        frozenset({'converge', 'diverge'}): ConflictType.OPPOSITE,
        # P5 补充：叙事聚焦 vs 自由最大化（高潮时刻核心冲突）
        frozenset({'concentrate', 'free'}): ConflictType.OPPOSITE,
    }

    def detect_conflict(self, claims: List[AxiomClaim]) -> List[AxiomConflict]:
        """
        检测所有公理声明之间的冲突

        Returns：
            冲突列表
        """
        conflicts = []
        for i in range(len(claims)):
            for j in range(i + 1, len(claims)):
                a, b = claims[i], claims[j]
                pair_key = frozenset({a.claim_type, b.claim_type})
                ctype = self.OPPOSITE_PAIRS.get(pair_key)
                if ctype:
                    exp = (f"{a.axiom_name} 要求「{a.claim_type}」，"
                           f"{b.axiom_name} 要求「{b.claim_type}」，两者方向相反")
                    conflicts.append(AxiomConflict(a, b, ctype, exp))
        return conflicts

    def arbitrate(self, conflicts: List[AxiomConflict]) -> Dict[int, float]:
        """
        裁决所有冲突，返回每个 axiom_id 的最终强度系数

        Returns：
            {axiom_id: final_intensity_multiplier}
        """
        final_intensity: Dict[int, float] = {}
        all_claims = []
        for cf in conflicts:
            all_claims.extend([cf.claim_a, cf.claim_b])
        for c in all_claims:
            if c.axiom_id not in final_intensity:
                final_intensity[c.axiom_id] = 1.0

        for cf in conflicts:
            a, b = cf.claim_a, cf.claim_b
            if cf.conflict_type == ConflictType.OPPOSITE:
                if a.priority < b.priority:
                    winner, loser = a, b
                elif b.priority < a.priority:
                    winner, loser = b, a
                else:
                    cf.arbitration_reason = "⚠️ 同优先级冲突，需师傅裁决"
                    continue

                cf.winner = winner
                cf.loser = loser
                cf.arbitration_reason = (
                    f"优先级裁决：{winner.axiom_name}(优先级={winner.priority}) "
                    f"< {loser.axiom_name}(优先级={loser.priority})，"
                    f"{winner.axiom_name} 胜出；{loser.axiom_name} 被压制 "
                    f"({loser.intensity:.2f} × 0.30 = {loser.intensity*0.3:.3f})"
                )
                final_intensity[loser.axiom_id] *= 0.3

        return final_intensity

    def resolve(self, claims: List[AxiomClaim]) -> Dict[int, float]:
        """
        一次性完成：检测 + 仲裁

        用法：
            final = ConflictResolver().resolve([
                AxiomClaim(5, 'concentrate', 'peak', 0.95),
                AxiomClaim(7, 'dissipate', 'max_freedom', 0.88),
            ])
        """
        conflicts = self.detect_conflict(claims)
        return self.arbitrate(conflicts)
