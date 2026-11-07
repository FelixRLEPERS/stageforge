extends Node3D
## Builds the virtual studio demo: environment, floor, walls, stage lights
## and the presenter plate that receiver.gd feeds. Everything is created
## here so the whole look of the pitch demo lives in one file (plan:
## programmatic over hand-written .tscn).
##
## Light energies are deliberately far above the prompt's 2.0 / 0.8: Godot 4
## scales Omni/Spot lights with inverse-square falloff, so a 2 W key at 6-9 m
## renders black. Values below were tuned against real screenshots.

const FLOOR_SIZE := Vector3(24.0, 0.2, 24.0)
const BACK_WALL_SIZE := Vector3(24.0, 9.0, 0.2)
const SIDE_WALL_SIZE := Vector3(0.2, 9.0, 20.0)
const PLATE_SIZE := Vector2(6.4, 3.6)
const PLATE_POS := Vector3(0.0, 1.8, -4.5)

const KEY_ENERGY := 90.0
const FILL_ENERGY := 45.0
const RIM_ENERGY := 0.7
## Distance from the camera to the wall — the plate sits flush against it,
## so this is the scale reference for framing.
const WALL_DIST := 11.5

var plate: MeshInstance3D


func _ready() -> void:
	_build_environment()
	_build_architecture()
	_build_lights()
	_build_plate()
	print("godot studio: environment + floor/walls + 3 lights + plate built")


# --- environment ----------------------------------------------------------

func _build_environment() -> void:
	"""Sky gives metallic surfaces something to reflect (gl_compatibility
	has no SSR, so an env map is the only source of specular)."""
	var sky_mat := ProceduralSkyMaterial.new()
	sky_mat.sky_top_color = Color(0.01, 0.03, 0.05)
	sky_mat.sky_horizon_color = Color(0.05, 0.11, 0.15)
	sky_mat.ground_bottom_color = Color(0.01, 0.02, 0.03)
	sky_mat.ground_horizon_color = Color(0.05, 0.11, 0.15)
	sky_mat.sun_angle_max = 10.0
	var sky := Sky.new()
	sky.sky_material = sky_mat

	var env := Environment.new()
	env.background_mode = Environment.BG_SKY
	env.sky = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.ambient_light_energy = 1.4
	env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.tonemap_white = 4.0

	var world := WorldEnvironment.new()
	world.name = "WorldEnvironment"
	world.environment = env
	add_child(world)


# --- architecture ---------------------------------------------------------

func _build_architecture() -> void:
	"""Floor: low metallic + high roughness so it reads as a dark stage
	floor with a soft sheen rather than a mirror into the black sky.
	Walls: neutral grey with a faint cool tint — warm key + cool fill is
	enough separation; the old teal emission washed everything green and
	weakened the plate/AR contrast."""
	_surface("Floor", FLOOR_SIZE, Vector3(0, -0.1, 0), Color(0.06, 0.07, 0.085), 0.2, 0.6)
	_surface("BackWall", BACK_WALL_SIZE, Vector3(0, 4.5, -7), Color(0.022, 0.025, 0.03), 0.0, 0.85)
	_surface("SideWallLeft", SIDE_WALL_SIZE, Vector3(-8, 4.5, -3), Color(0.045, 0.05, 0.06), 0.0, 0.85)
	_surface("SideWallRight", SIDE_WALL_SIZE, Vector3(8, 4.5, -3), Color(0.045, 0.05, 0.06), 0.0, 0.85)


func _surface(node_name: String, size: Vector3, pos: Vector3, albedo: Color,
		metallic: float, roughness: float, emission := Color(0, 0, 0),
		emission_energy := 0.0) -> MeshInstance3D:
	var node := MeshInstance3D.new()
	node.name = node_name
	var box := BoxMesh.new()
	box.size = size
	node.mesh = box
	node.material_override = _material(albedo, metallic, roughness, emission, emission_energy)
	node.position = pos
	add_child(node)
	return node


func _material(albedo: Color, metallic: float, roughness: float,
		emission: Color, emission_energy: float) -> StandardMaterial3D:
	var mat := StandardMaterial3D.new()
	mat.albedo_color = albedo
	mat.metallic = metallic
	mat.roughness = roughness
	if emission_energy > 0.0:
		mat.emission_enabled = true
		mat.emission = emission
		mat.emission_energy_multiplier = emission_energy
	return mat


# --- lights ---------------------------------------------------------------

func _build_lights() -> void:
	var rig := Node3D.new()
	rig.name = "StudioLights"
	add_child(rig)

	var key := SpotLight3D.new()
	key.name = "KeyLight"
	key.position = Vector3(3, 6, 4)
	key.light_color = Color(1.0, 0.95, 0.85)
	key.light_energy = KEY_ENERGY
	key.spot_range = 26.0
	key.spot_angle = 55.0
	rig.add_child(key)
	key.look_at(Vector3(0, 1, -3))

	var fill := OmniLight3D.new()
	fill.name = "FillLight"
	fill.position = Vector3(-5, 4, 3)
	fill.light_color = Color(0.6, 0.8, 1.0)
	fill.light_energy = FILL_ENERGY
	fill.omni_range = 26.0
	rig.add_child(fill)

	var rim := DirectionalLight3D.new()
	rim.name = "RimLight"
	rim.rotation_degrees = Vector3(-30, 45, 0)
	rim.light_color = Color(0.4, 0.6, 1.0)
	rim.light_energy = RIM_ENERGY
	rim.shadow_enabled = false
	rig.add_child(rim)


# --- presenter plate ------------------------------------------------------

func _build_plate() -> void:
	"""The screen receiver.gd writes into, plus a bezel and a floor stand so
	it reads as studio hardware instead of a rectangle floating in air."""
	plate = MeshInstance3D.new()
	plate.name = "PresenterPlate"
	var quad := QuadMesh.new()
	quad.size = PLATE_SIZE
	plate.mesh = quad
	plate.material_override = _plate_material()
	plate.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	plate.position = PLATE_POS
	add_child(plate)

	var bezel := _box_part("PlateBezel", Vector3(PLATE_SIZE.x + 0.14, PLATE_SIZE.y + 0.14, 0.06),
			Color(0.02, 0.02, 0.025), 0.7, 0.35)
	bezel.position = PLATE_POS + Vector3(0, 0, -0.05)

	var stand := _box_part("PlateStand", Vector3(0.18, PLATE_POS.y - PLATE_SIZE.y * 0.5, 0.18),
			Color(0.03, 0.03, 0.035), 0.7, 0.4)
	stand.position = Vector3(PLATE_POS.x, (PLATE_POS.y - PLATE_SIZE.y * 0.5) * 0.5,
			PLATE_POS.z - 0.05)

	var base := _box_part("PlateBase", Vector3(1.0, 0.07, 0.6), Color(0.03, 0.03, 0.035), 0.7, 0.4)
	base.position = Vector3(PLATE_POS.x, 0.035, PLATE_POS.z - 0.05)


func _plate_material() -> StandardMaterial3D:
	"""Opaque and unshaded: the plate is a monitor, the frame is the video.
	TRANSPARENCY_DISABLED is deliberate — Python's keyed alpha would punch
	holes in a screen that must stay a screen."""
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.transparency = BaseMaterial3D.TRANSPARENCY_DISABLED
	mat.albedo_color = Color.WHITE
	return mat


func _box_part(node_name: String, size: Vector3, albedo: Color,
		metallic: float, roughness: float) -> MeshInstance3D:
	var node := MeshInstance3D.new()
	node.name = node_name
	var box := BoxMesh.new()
	box.size = size
	node.mesh = box
	node.material_override = _material(albedo, metallic, roughness, Color(0, 0, 0), 0.0)
	add_child(node)
	return node