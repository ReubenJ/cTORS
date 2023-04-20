from flask_restful import Resource
from flask import current_app, Response

import os
import json

def get_all_layouts():
    layouts_dir = os.path.join(current_app.static_folder, '../../../data')
    if not os.path.exists(layouts_dir):
        current_app.logger.warning("Layouts directory does not exist: %s" % layouts_dir)
        return []
    return sorted(os.listdir(layouts_dir))


def get_layout(layout_id):
    layouts = get_all_layouts()
    if layout_id < 0 or layout_id >= len(layouts):
        return None
    return os.path.join(current_app.static_folder, '../../data', layouts[layout_id])

class Layout(Resource):
    def get(self) -> str:
        layouts = get_all_layouts()
        return Response(json.dumps(layouts), mimetype='application/json')