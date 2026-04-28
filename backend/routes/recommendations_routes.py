"""
Routes de recommandation : 3 morceaux par appel + endpoint de debug.
"""
from flask import Blueprint, jsonify, g, request

from ..auth import login_required
from ..recommender import recommend, explain


bp = Blueprint("recommendations", __name__, url_prefix="/api/recommendations")


@bp.get("")
@login_required
def get_recommendations():
    n = int(request.args.get("n", 3))
    n = max(1, min(n, 10))
    return jsonify({"recommendations": recommend(g.user["id"], n=n)})


@bp.get("/explain")
@login_required
def explain_taste():
    return jsonify(explain(g.user["id"]))
