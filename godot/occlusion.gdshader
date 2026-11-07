// Occlusion shell for the backplate (ADR-0006).
//
// The sphere is a point cloud: each vertex carries its equirectangular
// (u, v) so the fragment shader can sample the panorama depth texture
// that scripts/stage_reconstruct.py exported. Depth here is uint8
// 0 = nearest .. 255 = farthest - it only needs to ORDER surfaces so
// virtual props behind the set stay hidden, not measure them.
//
// NOTE on the sampler: a plain `uniform sampler2D depth_tex`, NOT
// `hint_depth_texture` - the Godot hint binds the screen depth buffer,
// which is a completely different thing (and unavailable to this
// material). The varying block is likewise unnecessary: UV already
// reaches us from the point-cloud vertex.

shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_never;

uniform sampler2D depth_tex : source_color, filter_linear;
uniform sampler2D color_tex : source_color, filter_linear;
uniform float sphere_radius = 60.0;
uniform float radius_tol = 1e-3;

varying vec2 equirect_uv;

void vertex() {
	// Point clouds have no UV attribute; recover it from the unit sphere
	// direction (the mesh vertices are radius * this direction).
	vec3 direction = normalize(VERTEX);
	float u = atan(direction.z, direction.x) / (2.0 * PI) + 0.5;
	float v = acos(clamp(direction.y, -1.0, 1.0)) / PI;
	equirect_uv = vec2(fract(u), v);
}

void fragment() {
	float depth = texture(depth_tex, equirect_uv).r;
	vec3 color = texture(color_tex, equirect_uv).rgb;
	ALBEDO = color;
	// Encode the sampled depth into alpha so the quad reads as a shell;
	// a real depth test arrives with the pilot mesh backplate.
	ALPHA = mix(0.35, 1.0, depth);
}