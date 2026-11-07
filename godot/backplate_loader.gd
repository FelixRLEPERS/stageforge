extends Node3D
## Loads an equirectangular backplate (colour + depth PNG) and builds the
## occlusion sphere from the sidecar metadata written by
## scripts/stage_reconstruct.py (ADR-0006).
##
## The panorama/depth PNGs live in godot/assets/backplates/ (gitignored):
## copy them there by hand after running the Python export. With no
## backplate present the node stays inert and the studio renders as before.

const BACKPLATE_DIR := "res://assets/backplates/"
const META_SUFFIX := "_backplate.json"
const DEPTH_SUFFIX := "_depth.png"
const SPHERE_RADIUS := 60.0
const SPHERE_POINTS := 100_000
const SPHERE_RADIUS_TOL := 1e-3

var _meta_path := ""
var _depth_texture: Texture2D
var _color_texture: Texture2D
var _mesh: MeshInstance3D


func _ready() -> void:
	_meta_path = _find_meta()
	if _meta_path.is_empty():
		print("godot backplate: no *_backplate.json in %s (loader idle)" % BACKPLATE_DIR)
		return
	_load()


func _find_meta() -> String:
	var dir := DirAccess.open(BACKPLATE_DIR)
	if dir == null:
		return ""
	dir.list_dir_begin()
	var name := dir.get_next()
	while name != "":
		if not dir.current_is_dir() and name.ends_with(META_SUFFIX):
			dir.list_dir_end()
			return BACKPLATE_DIR + name
		name = dir.get_next()
	dir.list_dir_end()
	return ""


func _load() -> void:
	var file := FileAccess.open(_meta_path, FileAccess.READ)
	if file == null:
		push_warning("godot backplate: cannot open %s" % _meta_path)
		return
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	file.close()
	if not (parsed is Dictionary):
		push_warning("godot backplate: %s is not a JSON object" % _meta_path)
		return
	var meta := parsed as Dictionary
	var depth_png := str(meta.get("depth_png", ""))
	## Sidecar stores a repo-relative path; resolve it inside res://.
	depth_png = "res://" + depth_png.replace("\\", "/").lstrip("./")
	_color_texture = _load_texture(_meta_path.trim_suffix(META_SUFFIX) + ".png")
	_depth_texture = _load_texture(depth_png)
	if _depth_texture == null:
		push_warning("godot backplate: depth texture missing (%s)" % depth_png)
		return
	_mesh = _build_sphere()
	add_child(_mesh)
	print("godot backplate: loaded %s (points=%d radius=%.1f)" % [
		_meta_path.get_file(), SPHERE_POINTS, SPHERE_RADIUS
	])


func _load_texture(path: String) -> Texture2D:
	if not ResourceLoader.exists(path):
		return null
	return load(path) as Texture2D


func _build_sphere() -> MeshInstance3D:
	"""A point-cloud sphere: one vertex per lattice sample, billboarded
	in the shader so the depth quad reads as a shell around the studio."""
	var node := MeshInstance3D.new()
	node.name = "BackplateSphere"
	var mesh := ArrayMesh.new()
	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	var vertices := PackedVector3Array()
	var uvs := PackedVector2Array()
	var xyz: PackedFloat32Array = _sphere_xyz()
	var uv_flat: PackedFloat32Array = _sphere_uv()
	var count := xyz.size() / 3
	vertices.resize(count)
	uvs.resize(count)
	for i in count:
		vertices[i] = Vector3(xyz[i * 3], xyz[i * 3 + 1], xyz[i * 3 + 2]) * SPHERE_RADIUS
		uvs[i] = Vector2(uv_flat[i * 2], uv_flat[i * 2 + 1])
	arrays[Mesh.ARRAY_VERTEX] = vertices
	arrays[Mesh.ARRAY_TEX_UV] = uvs
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_POINTS, arrays)
	node.mesh = mesh
	node.material_override = _material()
	node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	return node


func _sphere_xyz() -> PackedFloat32Array:
	## Fibonacci lattice, same formula as project_depth_to_sphere() -
	## kept in sync by ADR-0006 so no sidecar blob is needed.
	var out := PackedFloat32Array()
	out.resize(SPHERE_POINTS * 3)
	var golden := PI * (1.0 + sqrt(5.0))
	for i in SPHERE_POINTS:
		var idx := float(i) + 0.5
		var phi := acos(1.0 - 2.0 * idx / float(SPHERE_POINTS))
		var theta := golden * idx
		var sin_phi := sin(phi)
		out[i * 3] = sin_phi * cos(theta)
		out[i * 3 + 1] = cos(phi)
		out[i * 3 + 2] = sin_phi * sin(theta)
	return out


func _sphere_uv() -> PackedFloat32Array:
	var out := PackedFloat32Array()
	out.resize(SPHERE_POINTS * 2)
	var golden := PI * (1.0 + sqrt(5.0))
	for i in SPHERE_POINTS:
		var idx := float(i) + 0.5
		var phi := acos(1.0 - 2.0 * idx / float(SPHERE_POINTS))
		var theta := golden * idx
		var x := sin(phi) * cos(theta)
		var z := sin(phi) * sin(theta)
		out[i * 2] = fposmod(atan2(z, x) / (2.0 * PI) + 1.0, 1.0)
		out[i * 2 + 1] = phi / PI
	return out


func _material() -> ShaderMaterial:
	var mat := ShaderMaterial.new()
	var shader := load("res://occlusion.gdshader") as Shader
	if shader == null:
		push_warning("godot backplate: occlusion.gdshader missing - blue sphere")
		mat.shader = null
		return mat
	mat.shader = shader
	mat.set_shader_parameter("depth_tex", _depth_texture)
	mat.set_shader_parameter("color_tex", _color_texture)
	mat.set_shader_parameter("sphere_radius", SPHERE_RADIUS)
	mat.set_shader_parameter("radius_tol", SPHERE_RADIUS_TOL)
	return mat