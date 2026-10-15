// Ocean trench — an ambience behind the whole portal (Portalab puts its helpers first: u_res, u_time, hash,
// noise, fbm, over). Premultiplied colour: what is not lit stays see-through.
void main() {
  vec2 uv = gl_FragCoord.xy / u_res;
  float aspect = u_res.x / u_res.y;
  vec2 c = vec2(uv.x * aspect, uv.y);
  float t = u_time;
  vec4 o = vec4(0.0);
  vec3 water = mix(vec3(0.0, 0.01, 0.03), vec3(0.0, 0.07, 0.12), pow(uv.y, 1.6));
  o = over(o, water, 0.9);
  // the last light from far above: slanted shafts, waving
  float shafts = fbm(vec2(c.x * 3.0 - c.y * 0.8 + t * 0.03, t * 0.05));
  o = over(o, vec3(0.2, 0.55, 0.65), smoothstep(0.55, 0.85, shafts) * pow(uv.y, 2.5) * 0.35);
  // marine snow drifting down
  for (int i = 0; i < 40; i++) {
    float fi = float(i);
    vec2 pos = vec2(hash(vec2(fi, 1.0)) * aspect + 0.03 * sin(t * 0.4 + fi), 1.0 - fract(hash(vec2(fi, 2.0)) + t * (0.01 + 0.015 * hash(vec2(fi, 3.0)))));
    o = over(o, vec3(0.7, 0.9, 1.0), smoothstep(0.003, 0.0, length(c - pos)) * 0.6);
  }
  // distant jellyfish pulsing
  for (int k = 0; k < 4; k++) {
    float fk = float(k);
    vec2 at = vec2(hash(vec2(fk, 7.0)) * aspect, fract(hash(vec2(fk, 8.0)) + t * 0.006 * (1.0 + fk)));
    float glow = exp(-length(c - at) * 26.0) * (0.55 + 0.45 * sin(t * 1.5 + fk * 2.0));
    o = over(o, mix(vec3(0.2, 1.0, 0.85), vec3(0.6, 0.45, 1.0), fract(fk * 0.37)), glow * 0.8);
  }
  // the trench's walls, darker at the sides
  float walls = smoothstep(0.35, 0.0, uv.x) + smoothstep(0.65, 1.0, uv.x);
  o = over(o, vec3(0.0, 0.0, 0.01), walls * 0.6 * (0.7 + 0.3 * fbm(c * 6.0)));
  gl_FragColor = o;
}
