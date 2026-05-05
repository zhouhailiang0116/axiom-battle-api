# axiom_battle.py — 公理对抗赛引擎
# WuDao System · Axiom Battle Engine
# 
# 定位：悟道体系自组织的核心引擎
# axiom8 的 permutation test 是被动的，axiom_battle 是主动的
# ——让最强 axiom 被自己的对抗案例击穿，触发 axiom_X+1 自组织
#
# 用法：
#     battle = AxiomBattle()
#     defendants = battle.list_defendants()
#     result = battle.run_full_cycle(axiom_pair)
#
# 作者：悟道体系·因果层 | 2026-05-05

import json
import time
from enum import IntEnum
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path

# ── 内部模块 ──────────────────────────────────────────────────────────────
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from causal_arbitrator import ConflictResolver, AxiomClaim, ConflictType

# ── 公理元数据 ─────────────────────────────────────────────────────────────
AXIOM_NAMES = {
    1: "生长", 2: "光影", 3: "色彩", 4: "布局",
    5: "叙事", 6: "边界", 7: "自由", 8: "因果"
}

# 公理优先级（数字小=优先）
AXIOM_PRIORITY = {
    "光影": 1, "因果": 2, "边界": 3, "叙事": 4,
    "布局": 5, "色彩": 6, "生长": 7, "自由": 7,
}

# OPPOSITE_PAIRS（来自 causal_arbitrator）
OPPOSITE_PAIRS = {
    frozenset({'focus', 'spread'}): "opposite",
    frozenset({'concentrate', 'dissipate'}): "opposite",
    frozenset({'constrain', 'free'}): "opposite",
    frozenset({'intensify', 'soften'}): "opposite",
    frozenset({'heat_up', 'cool_down'}): "opposite",
    frozenset({'clarify', 'ambiguate'}): "opposite",
    frozenset({'tighten', 'loosen'}): "opposite",
    frozenset({'attract', 'repel'}): "opposite",
    frozenset({'converge', 'diverge'}): "opposite",
    frozenset({'concentrate', 'free'}): "opposite",
}

# ── 判断类型 ───────────────────────────────────────────────────────────────
class Judgment(IntEnum):
    ALIVE = 0      # axiom 存活，无需修改
    STRENGTHENED = 1  # axiom 强化（标准提高）
    MODIFIED = 2   # axiom 修正（加约束条件）
    DEAD = 3       # axiom 死亡（被击穿）
    SUSPENDED = 4  # 悬置（数据不足）


@dataclass
class BattleRecord:
    """一次对抗记录"""
    timestamp: str
    axiom_a_id: int
    axiom_b_id: int
    attack_type: str        # inverse / cross_domain / counterfactual
    adversary_frames: List[dict]
    inverse_ratio: float    # 反向攻击帧比例
    counterfactual_rmse: float  # 反事实残差
    judgment: str
    judgment_reason: str


@dataclass
class CycleResult:
    """完整对抗周期结果"""
    axiom_pair: Tuple[int, int]
    judgment: Judgment
    judgment_reason: str
    strengthen_or_weaken_ratio: float
    arena_before: dict
    arena_after: dict
    battle_record: BattleRecord


class AxiomArena:
    """
    axiom 竞技场：维护所有 axiom 的强弱排名
    排名依据：存活次数、被击穿次数、平均强度
    """
    
    def __init__(self, log_path: Optional[str] = None):
        self.log_path = log_path or ".axiom_arena.json"
        self.arena: Dict[int, dict] = {}
        self._load()
    
    def _load(self):
        if Path(self.log_path).exists():
            with open(self.log_path) as f:
                data = json.load(f)
                self.arena = {int(k): v for k, v in data.items()}
        else:
            # 初始化 arena
            for id_, name in AXIOM_NAMES.items():
                self.arena[id_] = {
                    "name": name,
                    "alive_count": 0,
                    "death_count": 0,
                    "strengthen_count": 0,
                    "modify_count": 0,
                    "total_battles": 0,
                    "avg_intensity": 1.0,
                    "last_battle": None,
                }
    
    def save(self):
        with open(self.log_path, "w") as f:
            json.dump(self.arena, f, ensure_ascii=False, indent=2)
    
    def record(self, axiom_id: int, event: str, intensity: float = None):
        """记录 axiom 的战斗事件"""
        if axiom_id not in self.arena:
            return
        self.arena[axiom_id]["total_battles"] += 1
        self.arena[axiom_id]["last_battle"] = time.strftime("%Y-%m-%d %H:%M")
        
        if event == "alive":
            self.arena[axiom_id]["alive_count"] += 1
        elif event == "death":
            self.arena[axiom_id]["death_count"] += 1
        elif event == "strengthen":
            self.arena[axiom_id]["strengthen_count"] += 1
        elif event == "modify":
            self.arena[axiom_id]["modify_count"] += 1
        
        if intensity is not None:
            # 滑动平均更新强度
            old = self.arena[axiom_id]["avg_intensity"]
            n = self.arena[axiom_id]["total_battles"]
            self.arena[axiom_id]["avg_intensity"] = (old * (n - 1) + intensity) / n
        
        self.save()
    
    def ranking(self) -> List[Tuple[int, dict]]:
        """返回 axiom 排名（按综合分数）"""
        scored = []
        for id_, data in self.arena.items():
            score = (
                data["alive_count"] * 10
                - data["death_count"] * 5
                + data["strengthen_count"] * 3
                - data["modify_count"] * 2
            )
            scored.append((id_, score, data))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [(id_, data) for id_, score, data in scored]
    
    def top(self, n: int = 3) -> List[int]:
        """返回最强的 n 个 axiom id"""
        return [id_ for id_, _ in self.ranking()[:n]]
    
    def bottom(self, n: int = 3) -> List[int]:
        """返回最弱的 n 个 axiom id"""
        return [id_ for id_, _ in self.ranking()[-n:]]


class AxiomBattle:
    """
    公理对抗赛引擎
    
    三种攻击方式：
    1. 反向攻击（Inverse Attack）：找 A↑ + B↓ 的帧——如果存在且 >10%，A 进入审查
    2. 跨域攻击（Cross-Domain Attack）：把这个 axiom 换到另一个 domain 还能成立吗
    3. 反事实攻击（Counterfactual Attack）：预测"如果 A=0，B 会怎样"，残差最大处是异常
    """
    
    def __init__(self, arena_log_path: str = None):
        self.arena = AxiomArena(log_path=arena_log_path)
        self.conflict_resolver = ConflictResolver()
    
    # ── 第一阶段：列出被告 ────────────────────────────────────────────────
    
    def list_defendants(self) -> List[Dict]:
        """
        从 arena 提取所有 axiom，按综合分数排序
        重点审查：最弱的 axiom（最容易被击穿）
        """
        ranking = self.arena.ranking()
        return [
            {
                "axiom_id": id_,
                "name": data["name"],
                "score": data["alive_count"] * 10 - data["death_count"] * 5,
                "total_battles": data["total_battles"],
                "avg_intensity": round(data["avg_intensity"], 3),
                "status": "HOT" if data["death_count"] > 0 else "SOLID"
            }
            for id_, data in ranking
        ]
    
    # ── 第二阶段：生成对抗样本 ─────────────────────────────────────────────
    
    def generate_adversary(self, axiom_id: int, 
                           domain: str = "default",
                           n_samples: int = 100) -> List[dict]:
        """
        对指定 axiom，生成最可能击穿它的对抗案例
        
        对抗策略：
        1. 找到这个 axiom 的所有 OPPOSITE pair（互为相反的 claim_type）
        2. 生成高强度反向帧（axiom itself 高 + opposite 也高）
        3. 这些帧触发冲突仲裁，且这个 axiom 输了
        
        Args:
            axiom_id: 被攻击的 axiom
            domain: 领域（用于跨域攻击）
            n_samples: 生成样本数
        
        Returns:
            adversary_frames: 对抗样本列表
        """
        axiom_name = AXIOM_NAMES.get(axiom_id, f"axiom{axiom_id}")
        
        # 找这个 axiom 涉及的所有冲突对
        relevant_pairs = []
        for pair, ctype in OPPOSITE_PAIRS.items():
            pair_list = list(pair)
            # 找出这个 axiom 关联的 claim_type
            if len(pair_list) == 2:
                relevant_pairs.append({
                    "my_type": pair_list[0],
                    "opposite_type": pair_list[1],
                    "opposite_axiom_id": self._infer_opposite_axiom(pair_list[1])
                })
        
        # 生成对抗样本
        adversary_frames = []
        for pair_info in relevant_pairs:
            # 对抗帧：高强度自己的 claim + 高强度 opposite
            # → 触发最大冲突，强度低者必然输
            frame = {
                "domain": domain,
                "axiom_id": axiom_id,
                "axiom_name": axiom_name,
                "my_claim_type": pair_info["my_type"],
                "my_intensity": 0.95,  # 高强度（假设）
                "opposite_claim_type": pair_info["opposite_type"],
                "opposite_intensity": 0.95,  # 高强度
                "conflict_detected": True,
                "attack_vector": "inverse",
                "expected_outcome": "axiom_loses"  # 因为 opposite axiom 优先级更高
            }
            adversary_frames.append(frame)
        
        # 如果有跨域样本（来自真实数据），加入跨域攻击
        cross_domain = self._cross_domain_samples(axiom_id, domain)
        adversary_frames.extend(cross_domain)
        
        return adversary_frames[:n_samples]
    
    def _infer_opposite_axiom(self, claim_type: str) -> int:
        """从 claim_type 反推关联的 axiom（启发式）"""
        mapping = {
            "concentrate": 5, "dissipate": 7, "focus": 5, "spread": 7,
            "grow": 1, "shrink": 1,
            "warm_up": 3, "cool_down": 2,
            "structure": 6, "chaos": 7,
            "balance": 4, "tilt": 7,
            "intensify": 5, "soften": 3,
        }
        return mapping.get(claim_type, 7)  # 默认自由 axiom
    
    def _cross_domain_samples(self, axiom_id: int, domain: str) -> List[dict]:
        """
        跨域攻击：从其他 domain 寻找这个 axiom 的反例
        目前是占位符，需要真实数据接入
        """
        # TODO: 接入真实数据（基因数据/宏观经济数据/物理数据）
        # 检查这个 axiom 在新 domain 是否还成立
        return []
    
    # ── 第三阶段：交叉域攻击 ───────────────────────────────────────────────
    
    def cross_domain_attack(self, axiom_id: int, 
                            original_domain: str,
                            new_domain: str) -> Dict:
        """
        跨域击穿测试：这个 axiom 换到 new_domain 还能成立吗？
        
        Args:
            axiom_id: 被测试的 axiom
            original_domain: 原始领域
            new_domain: 新领域
        
        Returns:
            {"still_holds": bool, "evidence": str, "confidence": float}
        """
        axiom_name = AXIOM_NAMES.get(axiom_id, f"axiom{axiom_id}")
        
        # TODO: 真实跨域验证
        # 目前返回占位结果
        return {
            "still_holds": True,  # 待真实数据验证
            "evidence": f"axiom {axiom_name} 在 {new_domain} 域无数据",
            "confidence": 0.3,  # 低置信度——说明需要数据
            "requires_data": True
        }
    
    # ── 第四阶段：反事实测试 ──────────────────────────────────────────────
    
    def counterfactual_test(self, axiom_pair: Tuple[int, int],
                            causal_data: List[dict]) -> Dict:
        """
        反事实测试：
        用线性回归预测"如果 A=0，B 会怎样"
        残差最大的帧就是反事实异常点
        
        Args:
            axiom_pair: (axiom_a_id, axiom_b_id)
            causal_data: [{"A": value, "B": value, "lag": n}, ...]
        
        Returns:
            {"rmse": float, "max_residual_idx": int, "anomaly_frames": [...]}
        """
        if len(causal_data) < 10:
            return {
                "rmse": 0.0,
                "max_residual_idx": -1,
                "anomaly_frames": [],
                "note": "数据不足，无法反事实测试"
            }
        
        # 简单线性回归：预测 B = alpha * A + beta
        n = len(causal_data)
        sum_a = sum(d["A"] for d in causal_data)
        sum_b = sum(d["B"] for d in causal_data)
        sum_aa = sum(d["A"]**2 for d in causal_data)
        sum_ab = sum(d["A"] * d["B"] for d in causal_data)
        
        denom = n * sum_aa - sum_a * sum_a
        if abs(denom) < 1e-10:
            alpha, beta = 0.0, sum_b / n
        else:
            alpha = (n * sum_ab - sum_a * sum_b) / denom
            beta = (sum_aa * sum_b - sum_a * sum_ab) / denom
        
        # 计算残差
        residuals = []
        for i, d in enumerate(causal_data):
            predicted = alpha * d["A"] + beta
            residual = abs(d["B"] - predicted)
            residuals.append((i, residual, d))
        
        # 找最大残差点
        residuals.sort(key=lambda x: x[1], reverse=True)
        max_idx, max_res, anomaly = residuals[0]
        
        # RMSE
        rmse = (sum(r[1]**2 for r in residuals) / n) ** 0.5
        
        return {
            "rmse": round(rmse, 4),
            "max_residual_idx": max_idx,
            "max_residual": round(max_res, 4),
            "anomaly_frame": {
                "index": max_idx,
                "A": anomaly["A"],
                "B": anomaly["B"],
                "predicted_B": round(alpha * anomaly["A"] + beta, 4),
                "residual": round(max_res, 4),
                "lag": anomaly.get("lag", 0)
            },
            "alpha": round(alpha, 4),
            "beta": round(beta, 4),
            "judgment_std": "2-sigma" if max_res > 2 * rmse else "within_2sigma"
        }
    
    # ── 第五阶段：判决 ────────────────────────────────────────────────────
    
    def judge(self, axiom_pair: Tuple[int, int],
              adversary_frames: List[dict],
              inverse_ratio: float,
              counterfactual_rmse: float) -> Tuple[Judgment, str]:
        """
        悟道定理判决：
        
        判决标准：
        - axiom 死亡：反向攻击帧 > 20%，且反事实残差 > 2σ
        - axiom 强化：反向攻击帧 < 5%，r_threshold 0.6 → 0.65
        - axiom 修正：加约束条件（如"仅在 disease_stage > 2 时成立"）
        - axiom 悬置：数据不足，继续收集
        
        Args:
            axiom_pair: (axiom_a_id, axiom_b_id)
            adversary_frames: 对抗样本
            inverse_ratio: 反向攻击帧比例（0-1）
            counterfactual_rmse: 反事实残差
        
        Returns:
            (Judgment, reason_str)
        """
        a_id, b_id = axiom_pair
        
        # 数据不足
        if len(adversary_frames) < 5:
            return Judgment.SUSPENDED, "对抗样本不足，悬置判决"
        
        # axiom 死亡
        if inverse_ratio > 0.20 and counterfactual_rmse > 2.0:
            reason = (
                f"反向攻击帧占比 {inverse_ratio:.1%} > 20%，"
                f"且反事实残差 {counterfactual_rmse:.2f} > 2σ。"
                f"axiom {a_id} 被击穿，判决死亡。"
            )
            return Judgment.DEAD, reason
        
        # axiom 强化
        if inverse_ratio < 0.05:
            reason = (
                f"反向攻击帧占比 {inverse_ratio:.1%} < 5%。"
                f"axiom {a_id} 经受考验，标准提升（r_threshold 0.6 → 0.65）。"
            )
            return Judgment.STRENGTHENED, reason
        
        # axiom 修正
        if inverse_ratio > 0.05:
            reason = (
                f"反向攻击帧占比 {inverse_ratio:.1%}，处于灰色地带。"
                f"axiom {a_id} 需要加约束条件（如 domain 或 threshold）。"
            )
            return Judgment.MODIFIED, reason
        
        # axiom 存活
        return Judgment.ALIVE, f"反向攻击帧 {inverse_ratio:.1%}，axiom {a_id} 存活"
    
    # ── 完整周期 ─────────────────────────────────────────────────────────
    
    def run_full_cycle(self, axiom_pair: Tuple[int, int],
                       causal_data: List[dict] = None) -> CycleResult:
        """
        运行完整对抗周期：
        1. 列出被告（已选定）
        2. 生成对抗样本
        3. 反事实测试
        4. 判决
        5. 更新 arena
        6. 记录 battle log
        
        Args:
            axiom_pair: (axiom_a_id, axiom_b_id)
            causal_data: 可选的因果数据（用于反事实测试）
        
        Returns:
            CycleResult: 完整对抗结果
        """
        a_id, b_id = axiom_pair
        arena_before = dict(self.arena.arena)
        
        # Step 1: 生成对抗样本
        adversary_frames = self.generate_adversary(a_id)
        
        # Step 2: 计算反向攻击比例
        # 反向帧：axiom_a 高强度 且 axiom_b 也高强度 → 冲突触发，弱方输
        # 简化：所有生成的对抗帧都是反向帧
        inverse_ratio = len(adversary_frames) / max(1, len(adversary_frames) + 1)
        
        # Step 3: 反事实测试
        if causal_data and len(causal_data) > 0:
            cf_result = self.counterfactual_test(axiom_pair, causal_data)
            counterfactual_rmse = cf_result["rmse"]
        else:
            # 模拟数据
            counterfactual_rmse = 1.5  # 模拟值
        
        # Step 4: 判决
        judgment, reason = self.judge(axiom_pair, adversary_frames, inverse_ratio, counterfactual_rmse)
        
        # Step 5: 更新 arena
        self.arena.record(a_id, judgment.name.lower(), intensity=1 - inverse_ratio)
        self.arena.record(b_id, "alive", intensity=1.0)
        
        # Step 6: 记录 battle log
        battle_record = BattleRecord(
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            axiom_a_id=a_id,
            axiom_b_id=b_id,
            attack_type="inverse",
            adversary_frames=adversary_frames[:5],  # 只记录前5个
            inverse_ratio=round(inverse_ratio, 4),
            counterfactual_rmse=round(counterfactual_rmse, 3),
            judgment=judgment.name,
            judgment_reason=reason,
        )
        
        self._save_battle_log(battle_record)
        
        # Step 7: 快照 arena_after
        arena_after = dict(self.arena.arena)
        
        return CycleResult(
            axiom_pair=axiom_pair,
            judgment=judgment,
            judgment_reason=reason,
            strengthen_or_weaken_ratio=round(inverse_ratio, 3),
            arena_before=arena_before,
            arena_after=arena_after,
            battle_record=battle_record
        )
    
    def _save_battle_log(self, record: BattleRecord):
        """保存 battle log 到 jsonl 文件"""
        log_path = ".axiom_battle_log.jsonl"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
    
    # ── 快速入口 ─────────────────────────────────────────────────────────
    
    def auto_battle(self) -> List[CycleResult]:
        """
        自动对抗：选择最弱的 axiom 和它的对手，运行完整周期
        """
        ranking = self.arena.ranking()
        
        # 选择最弱的 axiom
        weakest_id, weakest_data = ranking[-1]
        
        # 找它的对手（根据 OPPOSITE_PAIRS）
        # 简化：选择优先级最高的 axiom 作为对手
        opponent_id = min(
            [i for i in AXIOM_NAMES.keys() if i != weakest_id],
            key=lambda i: AXIOM_PRIORITY.get(AXIOM_NAMES[i], 99)
        )
        
        pair = (weakest_id, opponent_id)
        result = self.run_full_cycle(pair)
        
        return [result]
    
    def status(self) -> Dict:
        """当前状态总览"""
        ranking = self.arena.ranking()
        return {
            "total_axioms": len(ranking),
            "top3": [{"id": id_, "name": data["name"]} for id_, data in ranking[:3]],
            "bottom3": [{"id": id_, "name": data["name"]} for id_, data in ranking[-3:]],
            "total_battles": sum(data["total_battles"] for _, data in ranking),
            "deaths": sum(data["death_count"] for _, data in ranking),
        }


# ── CLI 入口 ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="悟道体系·公理对抗赛")
    parser.add_argument("--auto", action="store_true", help="自动对抗（选择最弱 axiom）")
    parser.add_argument("--list", action="store_true", help="列出所有 axiom 状态")
    parser.add_argument("--status", action="store_true", help="显示竞技场状态")
    parser.add_argument("--pair", nargs=2, type=int, metavar=("A", "B"), help="指定对抗 axiom pair")
    args = parser.parse_args()
    
    battle = AxiomBattle()
    
    if args.status:
        s = battle.status()
        print("\n=== Axiom Arena 状态 ===")
        print(f"总 axiom 数: {s['total_axioms']}")
        print(f"总战斗次数: {s['total_battles']}")
        print(f"累计死亡: {s['deaths']}")
        print(f"\nTOP 3: {[d['name'] for d in s['top3']]}")
        print(f"BOTTOM 3: {[d['name'] for d in s['bottom3']]}")
    
    elif args.list:
        defendants = battle.list_defendants()
        print("\n=== Axiom 被告列表 ===")
        for d in defendants:
            print(f"  [{d['axiom_id']}] {d['name']} | score={d['score']} | "
                  f"battles={d['total_battles']} | intensity={d['avg_intensity']} | {d['status']}")
    
    elif args.pair:
        result = battle.run_full_cycle((args.pair[0], args.pair[1]))
        print(f"\n=== 对抗结果 ===")
        print(f"Axiom Pair: {result.axiom_pair}")
        print(f"判决: {result.judgment.name}")
        print(f"理由: {result.judgment_reason}")
        print(f"反向攻击比例: {result.strengthen_or_weaken_ratio:.1%}")
    
    elif args.auto:
        results = battle.auto_battle()
        for r in results:
            print(f"\n=== 自动对抗 ===")
            print(f"Axiom Pair: {r.axiom_pair}")
            print(f"判决: {r.judgment.name}")
            print(f"理由: {r.judgment_reason}")
    
    else:
        parser.print_help()
        print("\n示例:")
        print("  python axiom_battle.py --list")
        print("  python axiom_battle.py --pair 5 7")
        print("  python axiom_battle.py --auto")
        print("  python axiom_battle.py --status")
