from random import seed, randint

from flask import Blueprint

from resources.models import ResourceNode, ResourceType, OreType

resources_bp = Blueprint('resources', __name__, template_folder='templates')


@resources_bp.route('/get/wood')
def get_wood():
    pass


@resources_bp.route('/gather/<int:resource_id>')
def gather(resource_id):
    pass


def acquire_new_resource():
    resource = ResourceNode()
    seed()
    resource.available = randint(10, 50)
    resource.type = ResourceType(randint(1, 2))
    if resource.type == ResourceType.ore:
        resource.sub_type = OreType(randint(1, 3))
    else:
        resource.sub_type = OreType.none
    # resource.land_id = land_id
    return resource
