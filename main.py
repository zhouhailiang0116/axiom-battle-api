"""
axiom-battle-api — WuDao Axiom Battle REST API
"""
from flask import Flask, jsonify, request
from causal_arbitrator import ConflictResolver, AxiomClaim
from axiom_battle import AxiomBattle
import os

app = Flask(__name__)
resolver = ConflictResolver()
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
    axiom_a = data.get("axiom_a", 5)
    axiom_b = data.get("axiom_b", 7)
    attack_type = data.get("attack_type", "inverse")

    try:
        axiom_a = int(axiom_a)
        axiom_b = int(axiom_b)
    except (ValueError, TypeError):
        return jsonify({"error": "axiom_a and axiom_b must be integers (1-8)"}), 400

    result = ab.run_full_cycle((axiom_a, axiom_b))
    return jsonify({
        "axiom_pair": list(result.axiom_pair),
        "judgment": result.judgment.name,
        "judgment_reason": result.judgment_reason,
        "strengthen_or_weaken_ratio": result.strengthen_or_weaken_ratio,
    })


@app.route("/arena", methods=["GET"])
def arena():
    return jsonify(ab.status())


@app.route("/health", methods=["GET"])
def health():
    return "OK", 200, {"Content-Type": "text/plain"}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
