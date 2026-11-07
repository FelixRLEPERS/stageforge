extends CanvasLayer
## Window-only HUD for the pitch demo: topic, measured fps, key map.
## Deliberately outside the SubViewport so it never reaches the broadcast
## output — this is a preview overlay, not part of the programme feed.

const REFRESH_SECONDS := 0.25
const KEYS_TEXT := "1 finance   2 sports   3 weather   4 breaking\nSpace hide AR   Esc quit"

var _topic_label: Label
var _info_label: Label
var _keys_label: Label
var _video_label: Label
var _topic := "none"
var _video := "no stream"
var _elapsed := 0.0


func _ready() -> void:
	layer = 10
	add_to_group("stageforge_hud")
	var panel := PanelContainer.new()
	panel.name = "HUD"
	add_child(panel)
	panel.set_anchors_and_offsets_preset(Control.PRESET_TOP_RIGHT)
	panel.grow_horizontal = Control.GROW_DIRECTION_BEGIN
	panel.offset_left = -360.0
	panel.offset_right = -16.0
	panel.offset_top = 14.0
	panel.offset_bottom = 128.0
	## Translucent so the studio reads through it — a solid block in the
	## corner would fight the frame it is meant to annotate.
	var bg := StyleBoxFlat.new()
	bg.bg_color = Color(0.02, 0.04, 0.06, 0.72)
	bg.corner_radius_top_left = 6
	bg.corner_radius_top_right = 6
	bg.corner_radius_bottom_left = 6
	bg.corner_radius_bottom_right = 6
	bg.content_margin_left = 12.0
	bg.content_margin_right = 12.0
	bg.content_margin_top = 8.0
	bg.content_margin_bottom = 8.0
	panel.add_theme_stylebox_override("panel", bg)

	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 6)
	panel.add_child(box)

	_topic_label = _label(box, 20, Color(0.345, 0.66, 1.0), true)
	_info_label = _label(box, 15, Color(0.78, 0.82, 0.85), false)
	_video_label = _label(box, 13, Color(0.55, 0.6, 0.63), false)
	_keys_label = _label(box, 12, Color(0.55, 0.6, 0.63), false)
	_keys_label.text = KEYS_TEXT

	set_topic("finance")
	print("godot hud: ready (topic, fps, key map)")


func _label(parent: Node, font_size: int, colour: Color, bold: bool) -> Label:
	var label := Label.new()
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	label.add_theme_font_size_override("font_size", font_size)
	label.add_theme_color_override("font_color", colour)
	if bold:
		label.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.6))
		label.add_theme_constant_override("outline_size", 6)
	parent.add_child(label)
	return label


func set_topic(topic: String) -> void:
	_topic = topic
	_topic_label.text = "TOPIC  %s" % topic.to_upper()


## Called from receiver.gd through the stageforge_hud group.
func set_video(text: String) -> void:
	_video = text


func _process(delta: float) -> void:
	_elapsed += delta
	if _elapsed < REFRESH_SECONDS:
		return
	_elapsed = 0.0
	_info_label.text = "FPS %d / 30        Studio demo" % Engine.get_frames_per_second()
	_video_label.text = "video  %s" % _video