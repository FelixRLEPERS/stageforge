extends Node3D
## Pre-flight headless check: does studio_3d_loader.gd load the imported
## studio mesh and spawn camera markers at the expected Godot positions?
## Run: godot --headless --path godot res://preflight_check.tscn

func _ready() -> void:
	# Safety net: never hang the headless pre-flight if a check aborts.
	get_tree().create_timer(30.0).timeout.connect(func() -> void: get_tree().quit(2))
	var ok := true
	var loader_script := load("res://studio_3d_loader.gd") as GDScript
	if loader_script == null or not loader_script.can_instantiate():
		print("PREFLIGHT GODOT: FAIL (studio_3d_loader.gd does not parse)")
		get_tree().quit(1)
		return
	var loader := loader_script.new() as Node3D
	loader.spawn_cameras = true
	add_child(loader)  # triggers loader._ready() -> mesh + cameras + environment

	# 1) Mesh instantiated as an occluder-candidate MeshInstance3D?
	var mesh_node := loader.get_node_or_null("StudioMesh")
	print("mesh instantiated: ", mesh_node != null)
	ok = ok and mesh_node != null
	if mesh_node != null:
		var found_mesh := false
		var stack: Array[Node] = [mesh_node]
		while stack.size() > 0:
			var n: Node = stack.pop_back()
			if n is MeshInstance3D:
				found_mesh = true
				var mi := n as MeshInstance3D
				print("  MeshInstance3D aabb=", mi.get_aabb(), " visible=", mi.visible)
				ok = ok and mi.get_aabb().size.y > 0.0 and mi.visible
			for c: Node in n.get_children():
				stack.append(c)
		print("mesh has MeshInstance3D: ", found_mesh)
		ok = ok and found_mesh

	# 2) Markers at the converted Godot positions
	var expected := {
		"StudioCam_Camera_Angled": Vector3(2, 2, -2),
		"StudioCam_Camera_Identity": Vector3(0, 3, 0),
		"StudioCam_Camera_Scaled": Vector3(-2, 2, 1),
		"StudioCam_Camera_WideFOV": Vector3(1, 1.5, 3),
	}
	for marker_name in expected:
		var m := loader.get_node_or_null(marker_name) as Marker3D
		if m == null:
			print("marker missing: ", marker_name)
			ok = false
			continue
		var want: Vector3 = expected[marker_name]
		var good := m.position.distance_to(want) < 0.001
		print("  marker ", marker_name, " pos=", m.position, " want=", want, " -> ", good)
		ok = ok and good

	# 3) Look directions (the pre-flight bug: identity cam must look DOWN)
	var ident := loader.get_node_or_null("StudioCam_Camera_Identity") as Marker3D
	if ident != null:
		var fwd := -ident.global_transform.basis.z
		var good := fwd.distance_to(Vector3(0, -1, 0)) < 0.001
		print("  Camera_Identity forward=", fwd, " (want (0,-1,0)) -> ", good)
		ok = ok and good
	var angled := loader.get_node_or_null("StudioCam_Camera_Angled") as Marker3D
	if angled != null:
		var fwd := -angled.global_transform.basis.z
		var want := Vector3(-0.612372, -0.5, -0.612372)
		var good := fwd.distance_to(want) < 0.001
		print("  Camera_Angled forward=", fwd, " (want ", want, ") -> ", good)
		ok = ok and good

	# 4) Camera3D children carry the converted FOV (39.6 deg / 110 deg)
	if ident != null:
		var child_names: Array[String] = []
		for c: Node in ident.get_children():
			child_names.append(c.get_class() + "(" + c.name + ")")
		print("  ident children: ", child_names)
		print("  loader.spawn_cameras=", loader.get("spawn_cameras"))
		var cam: Camera3D = null
		for c: Node in ident.get_children():
			if c is Camera3D:
				cam = c as Camera3D
		if cam != null:
			var fov_ok: bool = abs(cam.fov - 39.5978) < 0.01
			print("  Camera3D fov=", cam.fov, " -> ", fov_ok)
			ok = ok and fov_ok
		else:
			print("  Camera3D child missing")
			ok = false

	print("PREFLIGHT GODOT: ", "ALL PASS" if ok else "FAILURES")
	get_tree().quit(0 if ok else 1)
