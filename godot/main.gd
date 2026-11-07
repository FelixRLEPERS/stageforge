extends Node
## StageForge render layer — entry point (see docs/06-compositing-ar.md).
##
## Owns the 1920x1080 SubViewport holding the virtual studio, routes the
## topic keys to the AR group, wires the optional NDI output (vendored
## godot-ndi addon; skipped cleanly when the NDI Runtime is not installed)
## and validates the scene contract on start.

const NDI_SOURCE_NAME := "StageForge_Godot"
const VIEWPORT_SIZE := Vector2i(1920, 1080)
const FPS_SAMPLE_FRAMES := 120
const FPS_MIN_FPS := 25.0
const CAMERA_TARGET := Vector3(0.0, 2.0, -4.5)
const DEFAULT_TOPIC := "finance"
## Set STAGEFORGE_GODOT_SHOT=<path.png> to render one frame to disk and quit.
## Deterministic screenshot for the report — no editor or remote debugger.
const SHOT_ENV := "STAGEFORGE_GODOT_SHOT"
const SHOT_FRAME := 90
## Set STAGEFORGE_GODOT_KEYS=1 to inject the demo keystrokes at startup:
## proof that _input() routes 1-4 and Space, captured in the run log.
const KEYS_ENV := "STAGEFORGE_GODOT_KEYS"

const ARLoader = preload("res://ar_loader.gd")
const HUD = preload("res://debug_ui.gd")

var _fps_frames := 0
var _fps_elapsed := 0.0
var _fps_reported := false
var _topic := "none"
var _shot_frame := 0
var _shot_started := false


func _ready() -> void:
	print("StageForge Godot ready, NDI output: StageForge_Godot")
	_aim_camera()
	_validate_scene()
	_setup_ndi()
	load_topic(DEFAULT_TOPIC)
	_maybe_self_test_keys()


func _maybe_self_test_keys() -> void:
	"""Inject the real keystrokes through the input system, so the handler
	is exercised end-to-end rather than only read for correctness. Two
	Space presses leave the AR group visible again for the screenshot."""
	if OS.get_environment(KEYS_ENV).is_empty():
		return
	var order: Array[Key] = [KEY_2, KEY_3, KEY_4, KEY_1, KEY_SPACE, KEY_SPACE]
	for code in order:
		var event := InputEventKey.new()
		event.physical_keycode = code
		event.pressed = true
		Input.parse_input_event(event)
	print("godot keys: self-test injected 2,3,4,1,Space,Space")


func _aim_camera() -> void:
	## look_at overrides any pitch/yaw authored in the .tscn — keep it as
	## the single source of truth for framing so a scene tweak stays in sync.
	var camera := $ViewportHost/SubViewport/Scene3D/Camera3D as Camera3D
	if camera != null:
		camera.look_at(CAMERA_TARGET)


func _validate_scene() -> void:
	"""Smoke contract: viewport config must match the broadcast spec."""
	var host := $ViewportHost as SubViewportContainer
	var viewport := $ViewportHost/SubViewport as SubViewport
	assert(host != null, "ViewportHost (SubViewportContainer) missing")
	assert(viewport != null, "SubViewport missing")
	assert(not viewport.transparent_bg, "SubViewport must render opaque (studio demo)")
	assert(
		viewport.size == VIEWPORT_SIZE,
		"SubViewport size must be 1920x1080, got %s" % viewport.size
	)
	assert(
		viewport.render_target_update_mode == SubViewport.UPDATE_ALWAYS,
		"SubViewport.render_target_update_mode must be Always (NDI while unfocused)"
	)
	assert($ViewportHost/SubViewport/Scene3D/VirtualStudio != null, "VirtualStudio missing")
	assert($ViewportHost/SubViewport/Scene3D/ARGroup != null, "ARGroup missing")
	assert($ViewportHost/SubViewport/Receiver != null, "Receiver (stream reader) missing")
	assert($DebugUI != null, "DebugUI missing")
	print("godot smoke: viewport contract PASS (1920x1080, studio opaque)")


func _setup_ndi() -> void:
	"""Attach NDIOutput inside the SubViewport when the addon can load."""
	var viewport: SubViewport = $ViewportHost/SubViewport
	if not ClassDB.class_exists("NDIOutput"):
		push_warning(
			(
				"godot-ndi: NDIOutput unavailable (addon disabled or NDI Runtime "
				+ "not installed) - NDI output off, see godot/README.md"
			)
		)
		print("godot ndi: SKIP (NDI Runtime / addon unavailable)")
		return
	var ndi: Node = ClassDB.instantiate("NDIOutput") as Node
	ndi.name = NDI_SOURCE_NAME
	viewport.add_child(ndi)
	print("godot ndi: OK source '%s'" % NDI_SOURCE_NAME)


# --- topic switcher -------------------------------------------------------

func load_topic(topic: String) -> void:
	if not _ar().load_topic(topic):
		return
	var previous := _topic
	_topic = topic
	_hud().set_topic(topic)
	print("topic changed: %s -> %s" % [previous, topic])


func _input(event: InputEvent) -> void:
	## physical_keycode, not keycode: the demo must answer to the number row
	## regardless of whether the operator has a RU layout active.
	if not (event is InputEventKey and event.pressed and not event.echo):
		return
	match (event as InputEventKey).physical_keycode:
		KEY_1:
			load_topic("finance")
		KEY_2:
			load_topic("sports")
		KEY_3:
			load_topic("weather")
		KEY_4:
			load_topic("breaking")
		KEY_SPACE:
			var group := $ViewportHost/SubViewport/Scene3D/ARGroup
			group.visible = not group.visible
			print("godot ar: %s" % ("shown" if group.visible else "hidden"))
		KEY_ESCAPE:
			get_tree().quit()


func _ar() -> ARLoader:
	return $ViewportHost/SubViewport/Scene3D/ARGroup as ARLoader


func _hud() -> HUD:
	return $DebugUI as HUD


# --- frame accounting -----------------------------------------------------

func _process(delta: float) -> void:
	_track_fps(delta)
	_maybe_capture_shot()


func _track_fps(delta: float) -> void:
	"""Average fps over a warm-up window; asserted once (fps >= 25)."""
	if _fps_reported:
		return
	_fps_frames += 1
	_fps_elapsed += delta
	if _fps_frames < FPS_SAMPLE_FRAMES:
		return
	var fps := _fps_frames / _fps_elapsed
	print("godot fps: avg=%.1f over %d frames (target >= 25)" % [fps, _fps_frames])
	assert(fps >= FPS_MIN_FPS, "fps below 25: %.1f" % fps)
	_fps_reported = true


func _maybe_capture_shot() -> void:
	if _shot_started:
		return
	var path := OS.get_environment(SHOT_ENV)
	if path.is_empty() or DisplayServer.get_name() == "headless":
		return
	_shot_frame += 1
	if _shot_frame < SHOT_FRAME:
		return
	_shot_started = true
	await RenderingServer.frame_post_draw
	var image := get_viewport().get_texture().get_image()
	if image == null or image.is_empty():
		push_warning("godot shot: empty frame")
		return
	var err := image.save_png(path)
	print("godot shot: %s err=%d %dx%d" % [path, err, image.get_width(), image.get_height()])
	get_tree().quit()