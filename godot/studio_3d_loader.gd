@tool
extends Node3D
## Loads an offline studio reconstruction (GLB mesh + cameras.json) and makes
## it available as a 3D occluder / camera rig. See ADR-0009.
##
## Attach to any node in the scene; assets are resolved with load() so the
## paths can be overridden per-project. Missing files degrade to a warning
## instead of a crash.

@export var mesh_path: String = "res://assets/studio/studio_mesh.glb"
@export var cameras_path: String = "res://assets/studio/cameras.json"
@export var spawn_cameras: bool = false
@export var camera_markers_prefix: String = "StudioCam"

func _ready() -> void:
	_load_mesh()
	_load_cameras()
	_ensure_environment()

func _load_mesh() -> void:
	if not ResourceLoader.exists(mesh_path):
		push_warning("studio_3d_loader: mesh not found, skipping: %s" % mesh_path)
		return
	var scene := load(mesh_path)
	if scene == null:
		push_warning("studio_3d_loader: failed to load mesh resource: %s" % mesh_path)
		return
	var instance := scene.instantiate() if scene is PackedScene else null
	if instance == null:
		push_warning("studio_3d_loader: %s is not a PackedScene" % mesh_path)
		return
	instance.name = "StudioMesh"
	add_child(instance)
	_mark_occluders(self)

func _mark_occluders(node: Node) -> void:
	# Mark every mesh under the imported studio as an occluder candidate so
	# AR sprites/decals can be hidden behind real studio geometry later.
	for child in node.get_children():
		if child is MeshInstance3D:
			child.cast_geometry_into_occlusion_buffer = true
		_mark_occluders(child)

func _load_cameras() -> void:
	if not FileAccess.file_exists(cameras_path):
		push_warning("studio_3d_loader: cameras.json not found, skipping: %s" % cameras_path)
		return
	var text := FileAccess.get_file_as_string(cameras_path)
	var parsed: Variant = JSON.parse_string(text)
	if not (parsed is Array):
		push_warning("studio_3d_loader: cameras.json is not a JSON array")
		return
	for entry in parsed:
		if not (entry is Dictionary):
			continue
		_spawn_camera_marker(entry)

func _spawn_camera_marker(entry: Dictionary) -> void:
	var cam_name := str(entry.get("name", "camera"))
	var marker := Marker3D.new()
	marker.name = "%s_%s" % [camera_markers_prefix, cam_name]
	var pos: Variant = entry.get("position")
	if pos is Array and pos.size() == 3:
		marker.position = Vector3(float(pos[0]), float(pos[1]), float(pos[2]))
	var quat: Variant = entry.get("quaternion")
	if quat is Array and quat.size() == 4:
		marker.quaternion = Quaternion(
			float(quat[0]), float(quat[1]), float(quat[2]), float(quat[3])
		)
	add_child(marker)
	if spawn_cameras:
		var cam := Camera3D.new()
		cam.fov = float(entry.get("fov_deg", 70.0))
		marker.add_child(cam)

func _ensure_environment() -> void:
	if not _find_node_of_type(self, WorldEnvironment) == null:
		return
	var env_node := WorldEnvironment.new()
	env_node.name = "StudioWorldEnvironment"
	var env := Environment.new()
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.35, 0.37, 0.42)
	env.ambient_light_energy = 1.0
	env_node.environment = env
	add_child(env_node)

func _find_node_of_type(root: Node, type) -> Node:
	if root.get_class() == type.new().get_class():
		return root
	for child in root.get_children():
		var found := _find_node_of_type(child, type)
		if found != null:
			return found
	return null