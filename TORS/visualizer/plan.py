from flask_restful import Resource
from flask import Response, current_app
import json
import os

def get_all_plans():
    runs_dir = os.path.join(current_app.static_folder, '../../runs')
    if not os.path.exists(runs_dir):
        current_app.logger.warning("Plans directory does not exist: %s" % runs_dir)
        return []
    return sorted(os.listdir(runs_dir))

def get_plan(ix):
    plans = get_all_plans()
    if ix < 0 or ix >= len(plans): return None
    return os.path.join(current_app.static_folder, '../../runs',plans[ix])

class Plan(Resource):
    
    def get(self) -> str:
        names = get_all_plans()
        return Response(json.dumps(names), mimetype='application/json')