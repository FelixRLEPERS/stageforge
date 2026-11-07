extends Node
## StageForge render layer — entry point (see docs/06-compositing-ar.md).
##
## Owns the 1920x1080 transparent SubViewport, wires the optional NDI
## output (vendored godot-ndi addon; skipped cleanly when the NDI
## Runtime is not installed) and validates the scene contract on start.

const NDI_SOURCE_NAME := "StageForge_Godot"
const VIEWPORT_SIZE := Vector2i(1920, 1080)
const FPS_SAMPLE_FRAMES := 120
const FPS_MIN_FPS := 25.0

var _fps_frames := 0
var _fps_elapsed := 0.0
var _fps_reported := false


func _ready() -> void:
	print("StageForge Godot ready, NDI output: StageForge_Godot")
	_validate_scene()
	_setup_ndi()


func _validate_scene() -> void:
	"""Phase 5 smoke contract: viewport config must match the broadcast spec."""
	var host := $ViewportHost as SubViewportContainer
	var viewport := $ViewportHost/SubViewport as SubViewport
	assert(host != null, "ViewportHost (SubViewportContainer) missing")
	assert(viewport != null, "SubViewport missing")
	assert(viewport.transparent_bg, "SubViewport.transparent_bg must be true")
	assert(
		viewport.size == VIEWPORT_SIZE,
		"SubViewport size must be 1920x1080, got %s" % viewport.size
	)
	assert(
		viewport.render_target_update_mode == SubViewport.UPDATE_ALWAYS,
		"SubViewport.render_target_update_mode must be Always (NDI while unfocused)"
	)
	assert($ViewportHost/SubViewport/Scene3D/Cube != null, "Cube placeholder missing")
	assert($ViewportHost/SubViewport/Scene3D/Plate != null, "Plate (stream target) missing")
	assert($ViewportHost/SubViewport/Receiver != null, "Receiver (stream reader) missing")
	print("godot smoke: viewport contract PASS (1920x1080, transparent_bg=true)")


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


func _process(delta: float) -> void:
	"""Average fps over a warm-up window; asserted once (Phase 5, fps >= 25)."""
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
