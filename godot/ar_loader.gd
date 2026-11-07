extends Node3D
## AR holograms for the active storylink topic (godot/ar_config.json).
##
## The generated PNGs are square (1024x1024) on a solid black background.
## Two material settings work together:
##
##   BLEND_MODE_ADD  — black contributes nothing (src.rgb * src.a = 0), so
##     the picture glows like a hologram over a bright wall instead of
##     stacking on top of it (which would blow the highlights white).
##   TRANSPARENCY_ALPHA with albedo_color.a — one fade channel: the initial
##     0 ramps to 1 over FADE_SECONDS on load, and _process() drives it on
##     hide/show. No second property to keep in sync.
##
## Converting the PNGs to a true alpha channel is a separate, deferred task.

const CONFIG_PATH := "res://ar_config.json"
const ASSET_DIR := "res://assets/ar/"
const FADE_SECONDS := 0.5
const FLOAT_SPEED := 1.5

var _topics: Dictionary = {}
var _current := ""
var _mesh: MeshInstance3D
var _base_y := 0.0
var _amplitude := 0.1
var _fade := 1.0
var _time := 0.0

@export var face_camera := true


func _ready() -> void:
	_topics = _load_topics()
	print("godot ar: %d topic(s) loaded from %s" % [_topics.size(), CONFIG_PATH])


func _load_topics() -> Dictionary:
	var file := FileAccess.open(CONFIG_PATH, FileAccess.READ)
	if file == null:
		push_warning("godot ar: %s missing - no holograms" % CONFIG_PATH)
		return {}
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	file.close()
	if not (parsed is Dictionary):
		push_warning("godot ar: %s is not a JSON object" % CONFIG_PATH)
		return {}
	var backplate: Variant = (parsed as Dictionary).get("backplate", "")
	if backplate is String and not (backplate as String).is_empty():
		print("godot ar: backplate '%s' declared (loader not wired yet)" % backplate)
	return (parsed as Dictionary).get("topics", {}) as Dictionary


func topic_names() -> Array:
	return _topics.keys()


func current_topic() -> String:
	return _current


func load_topic(topic: String) -> bool:
	if not _topics.has(topic):
		push_warning("godot ar: unknown topic '%s' (%s)" % [topic, _topics.keys()])
		return false
	var spec := _topics[topic] as Dictionary
	_clear()
	_current = topic
	_amplitude = float(spec.get("float_amplitude", 0.1))
	var pos := spec.get("position", [0.0, 2.0, -3.0]) as Array
	_base_y = float(pos[1])
	_mesh = _build(spec.get("asset", "") as String)
	_mesh.position = Vector3(float(pos[0]), _base_y, float(pos[2]))
	_mesh.scale = Vector3.ONE * float(spec.get("scale", 1.0))
	add_child(_mesh)
	_fade = 0.0
	return true


func set_visible_ar(shown: bool) -> void:
	visible = shown


func _build(asset: String) -> MeshInstance3D:
	var node := MeshInstance3D.new()
	node.name = "AR_" + asset.get_basename()
	var quad := QuadMesh.new()
	var path := ASSET_DIR + asset
	## All seven assets are square (1024x1024), so a unit quad is
	## already correct — no aspect correction needed.
	quad.size = Vector2.ONE
	node.mesh = quad

	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	mat.albedo_color = Color(1, 1, 1, 0)

	if ResourceLoader.exists(path):
		mat.albedo_texture = load(path)
	else:
		push_warning("godot ar: %s missing - copy assets/generated/ar-*.png here" % path)

	node.material_override = mat
	node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	return node


func _clear() -> void:
	for child in get_children():
		remove_child(child)
		child.queue_free()
	_mesh = null
	_time = 0.0


func _process(delta: float) -> void:
	if not is_instance_valid(_mesh):
		return
	_time += delta
	var pos := _mesh.position
	pos.y = _base_y + sin(_time * FLOAT_SPEED) * _amplitude
	_mesh.position = pos
	if _fade < 1.0:
		_fade = minf(1.0, _fade + delta / FADE_SECONDS)
		var mat := _mesh.material_override as StandardMaterial3D
		if mat != null:
			var colour := mat.albedo_color
			colour.a = _fade
			mat.albedo_color = colour
	if face_camera:
		_face_camera()


func _face_camera() -> void:
	"""Yaw only: the quad normal is +Z, so turning it toward the camera's
	XZ position keeps charts and scoreboards readable as the view moves."""
	var camera := get_viewport().get_camera_3d()
	if camera == null:
		return
	var to_camera := camera.global_position - _mesh.global_position
	if Vector2(to_camera.x, to_camera.z).length_squared() < 0.0001:
		return
	_mesh.rotation.y = atan2(to_camera.x, to_camera.z)