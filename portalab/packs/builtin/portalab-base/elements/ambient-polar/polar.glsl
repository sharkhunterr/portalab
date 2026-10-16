// Portalab — ambient/polar: the « polar » ambience (spec 028, B2)
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  vec2 sg = p * 110.0;
  float sh = hash(floor(sg));
  float star = step(0.995, sh) * smoothstep(0.45, 0.0, length(fract(sg) - 0.5)) * (0.6 + 0.4 * sin(t * 2.5 + sh * 50.0));
  vec3 col = vec3(0.9, 0.95, 1.0) * star;
  float a = star * 0.8;
  for (int i = 0; i < 3; i++) {
    float fi = float(i);
    float x = p.x * (1.1 + fi * 0.45) + t * 0.035 * (1.0 + fi);
    float base = 0.5 + 0.11 * fi + 0.1 * sin(x * 2.0 + t * 0.25 + fi) + 0.08 * fbm(vec2(x * 2.0, t * 0.08 + fi));
    float yd = uv.y - base;
    float band = smoothstep(-0.01, 0.03, yd) * exp(-max(yd, 0.0) * (3.5 + fi * 2.0));
    float rays = 0.55 + 0.45 * fbm(vec2(x * 14.0, t * 0.25 + fi * 3.0));
    float light = band * rays * (0.85 - fi * 0.2);
    vec3 tint = mix(vec3(0.12, 1.0, 0.55), vec3(0.6, 0.32, 1.0), clamp(yd * 2.6 + fi * 0.3, 0.0, 1.0));
    col += tint * light;
    a = max(a, light * 0.85);
  }
  gl_FragColor = vec4(col * a, a);
}