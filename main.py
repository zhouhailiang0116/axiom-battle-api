"""
axiom-battle-api — WuDao Axiom Battle REST API
"""
from flask import Flask, jsonify, request
from causal_arbitrator import CausalArbitrator
from axiom_battle import AxiomBattle
import os

app = Flask(__name__)
ca = CausalArbitrator()
ab = AxiomBattle()

@app.route("/")
def index():
    return jsonify({
        "name": "WuDao Axiom Battle API",
        "version": "1.0",
        "endpoints": ["/battle", "/arena", "/health"]
    })

@app.route("/battle", methods=["POST"])
def battle():
    data = request.get_json() or {}
    axiom_a = data.get("axiom_a", "\u5叙事")
    axiom_b = data.get("axiom_b", "\u81自由")
    attack_type = data.get("attack_type", "reverse")

    attacker = ab.axioms.get(axiom_a)
    defender = ab.axioms.get(axiom_b)

    if not attacker or not defender:
        return jsonify({"error": "Axiom not found"}), 400

    result = ab.battle(attacker, defender, attack_type)
    return jsonify({
        "attacker": axiom_a,
        "defender": axiom_b,
        "attack_type": attack_type,
        "verdict": result.verdict.value,
        "attack_frame": result.attack_frame,
        "defense_frame": result.defense_frame,
        "causal_chain": result.causal_chain
    })

@app.route("/arena", methods=["GET"])
def arena():
    return jsonify(ab.get_arena_state())

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
