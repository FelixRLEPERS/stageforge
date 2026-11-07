extends Node
## Reads the RGBA stream published by stageforge.output.GodotOutputSink
## (file-backed shared buffer, seqlock protocol) and feeds the plate
## texture in Scene3D. Transport is documented in
## docs/06-compositing-ar.md (§ "Python → Godot: RGBA stream").
##
## Not fatal when absent: with no pipeline running the plate simply
## stays transparent and the scene keeps rendering.

const DEFAULT_PATH := "res://../out/godot_frame.rgba"
const HEADER_BYTES := 40
const MAGIC := "SGFRM01\n"
const SEQ_OFFSET := 16
const FORMAT_RGBA8 := 0
const MAX_DIM := 8192
const LOG_EVERY_FRAMES := 300

var _path := ""
var _texture: ImageTexture
var _last_seq := -1
var _frames := 0
var _missing_logged := false

@onready var plate: MeshInstance3D = $"../Scene3D/Plate"


func _ready() -> void:
	_path = _resolve_path()
	print("godot receiver: watching %s" % _path)


func _resolve_path() -> String:
	var env := OS.get_environment("STAGEFORGE_GODOT_SHM")
	if not env.is_empty():
		return env
	return ProjectSettings.globalize_path(DEFAULT_PATH).simplify_path()


func _process(_delta: float) -> void:
	var file := FileAccess.open(_path, FileAccess.READ)
	if file == null:
		if not _missing_logged:
			_missing_logged = true
			print("godot receiver: no stream yet at %s (pipeline not running?)" % _path)
		return
	_missing_logged = false
	_read_frame(file)
	file.close()


func _read_frame(file: FileAccess) -> void:
	"""Seqlock read: header → payload → header; drop anything torn."""
	if file.get_length() < HEADER_BYTES:
		return
	if file.get_buffer(8).get_string_from_ascii() != MAGIC:
		return
	var width := file.get_32()
	var height := file.get_32()
	var seq := file.get_64()
	if width == 0 or height == 0 or width > MAX_DIM or height > MAX_DIM:
		return
	if (seq & 1) == 1 or seq == _last_seq:
		return  # writer mid-frame (odd) or nothing new since last time
	file.seek(32)
	if file.get_32() != FORMAT_RGBA8:
		return
	file.seek(HEADER_BYTES)
	var pixels := file.get_buffer(width * height * 4)
	if pixels.size() != width * height * 4:
		return
	file.seek(SEQ_OFFSET)
	if file.get_64() != seq:
		return  # rewritten while we read — next frame will land cleanly
	_last_seq = seq
	_publish(width, height, pixels)


func _publish(width: int, height: int, pixels: PackedByteArray) -> void:
	var img := Image.create_from_data(width, height, false, Image.FORMAT_RGBA8, pixels)
	if img.is_empty():
		push_warning("godot receiver: bad image %dx%d" % [width, height])
		return
	if _texture == null or _texture.get_size() != Vector2(width, height):
		_texture = ImageTexture.create_from_image(img)
		var mat := plate.material_override as StandardMaterial3D
		if mat != null:
			mat.albedo_texture = _texture
		else:
			push_warning("godot receiver: Plate has no StandardMaterial3D override")
	else:
		_texture.update(img)
	_frames += 1
	if _frames == 1 or _frames % LOG_EVERY_FRAMES == 0:
		print("godot receiver: frame #%d %dx%d seq=%d" % [_frames, width, height, _last_seq])
