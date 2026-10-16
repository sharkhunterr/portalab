// Portalab — ambient/cosmos: the « cosmos » ambience (spec 028, B2)
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  vec2 q = p * 1.1 + vec2(t * 0.012, t * 0.007);
  vec2 w = vec2(fbm(q * 1.3 + t * 0.02), fbm(q * 1.3 + vec2(3.3, 7.1) - t * 0.015));
  float n = fbm(q + w * 1.9);
  vec3 col = mix(vec3(0.15, 0.02, 0.3), vec3(0.1, 0.35, 0.8), w.x);
  col = mix(col, vec3(0.95, 0.35, 0.6), smoothstep(0.55, 0.85, n));
  float a = smoothstep(0.1, 0.62, n) * 0.6;
  for (int i = 0; i < 2; i++) {
    float fi = float(i);
    vec2 sg = (p + vec2(t * 0.004 * (fi + 1.0), 0.0)) * (70.0 + fi * 90.0);
    float sh = hash(floor(sg) + fi * 31.0);
    float star = step(0.994, sh) * smoothstep(0.45, 0.0, length(fract(sg) - 0.5))
      * (0.55 + 0.45 * sin(t * (1.5 + fi) + sh * 60.0));
    col += vec3(1.0, 0.96, 0.9) * star;
    a = max(a, star * (0.9 - fi * 0.3));
  }
  gl_FragColor = vec4(col * a, a);
}