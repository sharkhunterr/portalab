// Portalab — ambient/inferno: the « inferno » ambience (spec 028, B2)
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  vec2 q = vec2(p.x * 2.4, p.y * 1.6 - t * 1.25);
  vec2 warp = vec2(fbm(q * 1.3 + vec2(0.0, -t * 0.6)), fbm(q * 1.7 + vec2(5.2, -t * 0.9)));
  float n = fbm(q + warp * 1.8);
  float tongues = 1.0 - abs(noise(vec2(p.x * 9.0 + warp.x * 3.0, p.y * 3.0 - t * 2.4)) * 2.0 - 1.0);
  n += tongues * 0.18;
  float f = clamp((n * 1.5 + (0.3 - uv.y * 1.9) - 0.42) * 2.6, 0.0, 1.0);
  vec3 col = mix(vec3(0.42, 0.02, 0.0), vec3(1.0, 0.4, 0.03), smoothstep(0.05, 0.5, f));
  col = mix(col, vec3(1.0, 0.72, 0.28), smoothstep(0.55, 1.0, f));
  col *= 0.78 + 0.32 * fbm(q * 3.5 + t * 1.3);
  float a = smoothstep(0.02, 0.4, f) * 0.85;
  // a dim glow above the flames
  float glow = smoothstep(0.55, 0.0, uv.y) * 0.18 * (0.8 + 0.2 * sin(t * 3.0));
  col += vec3(0.6, 0.15, 0.0) * glow;
  a = max(a, glow);
  gl_FragColor = vec4(col * a, a);
}