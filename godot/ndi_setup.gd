extends Node
## Optional NDI output for the StageForge render layer.
##
## DISABLED for the local demo: the vendored godot-ndi addon crashes Godot
## (signal 11) on shutdown when the NDI Runtime is absent (see godot/README.md),
## and the vendored addon is off-limits to edit. The local demo ships on
## Shared Memory (mmap) through receiver.gd only.
##
## Re-enable on the pilot, once the operator installs the free NDI Runtime
## (<https://ndi.video/tools/ndi-core-suite/>): uncomment the call to
## `attach()` in main.gd `_ready()` and this node will register an
## `NDIOutput` inside the SubViewport when the addon class is available.

const NDI_SOURCE_NAME := "StageForge_Godot"


## Attach NDIOutput inside the SubViewport when the addon can load.
## Safe to call even when the Runtime is missing: it logs SKIP and returns.
func attach(viewport: SubViewport) -> void:
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