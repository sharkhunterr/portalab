// Portalab — ambient/whiteout: the « whiteout » ambience (spec 028, B2)
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float aspect = u_res.x / u_res.y;
  vec4 o = vec4(0.0);
  float gust = smoothstep(0.55, 1.0, 0.5 + 0.35 * sin(t * 0.33) + 0.25 * sin(t * 0.91 + 1.0));
  // streetlamps receding along a road, each lighting a cone of snow streaming through it
  for (int i = 0; i < 4; i++) {
    float fi = float(i);
    float x0 = aspect * (0.12 + fi * 0.26);
    float top = 0.62 - fi * 0.05;
    float size = 1.0 - fi * 0.18;
    vec2 lamp = vec2(x0, top);
    o = over(o, vec3(0.05, 0.06, 0.08), step(abs(p.x - x0), 0.004 * size) * step(uv.y, top) * step(0.12, uv.y));
    float cone = smoothstep(0.18 * size, 0.0, abs(p.x - x0) - (top - uv.y) * 0.35) * step(uv.y, top) * step(0.08, uv.y);
    float snowIn = 0.5 + 0.5 * fbm(vec2(p.x * 18.0 - t * 4.0, uv.y * 30.0 + t * 2.0));
    o = over(o, vec3(1.0, 0.85, 0.55), cone * 0.32 * snowIn * size);
    o = over(o, vec3(1.0, 0.88, 0.6), clamp(exp(-length((p - lamp) * vec2(1.0, 1.3)) * 16.0) * 1.1, 0.0, 1.0) * size);
  }
  // veils of blown snow
  vec2 q = vec2(p.x * 1.5 - t * 0.55, p.y * 2.0 + t * 0.12);
  vec2 w = vec2(fbm(q + t * 0.07), fbm(q + vec2(4.4, -t * 0.05)));
  float veil = fbm(q * 1.4 + w * 2.0);
  float drift = smoothstep(0.45, 0.9, veil) * (0.35 + 0.55 * gust);
  o = over(o, vec3(0.82, 0.88, 1.0), drift * 0.55 + gust * 0.1);
  // the ground: a cold glow and snow streaming low
  float ground = smoothstep(0.14, 0.0, uv.y);
  float stream = fbm(vec2(p.x * 3.0 - t * 1.4, uv.y * 30.0));
  o = over(o, vec3(0.7, 0.78, 0.95), ground * (0.35 + 0.35 * smoothstep(0.4, 0.8, stream)));
  gl_FragColor = o;
}